# iBT Practice — Project Plan

**Goal:** a local-first, rubric-grounded TOEFL iBT (2026 format) practice & scoring tool. Users bring their own LLM API key; speech uses Deepgram (STT + TTS). Built to be genuinely useful *and* to show measurable engineering/ML rigor for an MS application.

Stack (decided): **Next.js (TypeScript) frontend + FastAPI (Python) backend**, runs locally. Keys stored on the user's machine only.

Rubric/format spec: see [`docs/RUBRICS_2026.md`](docs/RUBRICS_2026.md) (verified against ETS docs, Nov 2026).

---

## 1. What makes this more than "ChatGPT grades my essay"

1. **Exact 2026 format** — the new task types (Build a Sentence, Write an Email, Listen and Repeat, Take an Interview, Complete the Words, etc.), timers, and the 1–6 band scale with CEFR + comparable 0–120.
2. **Hybrid scoring** — deterministic scorers where possible (Listen & Repeat alignment, Build a Sentence, MC), LLM only where judgment is needed, and the LLM is given measured features (WER, pause stats, error counts) rather than guessing.
3. **Evidence-based feedback** — every score cites spans of the user's own response for each rubric dimension, plus a concrete "how to reach the next band" rewrite.
4. **Speech analytics from Deepgram word timestamps/confidence** — WPM, articulation rate, pause count/length, filler rate, low-confidence words (pronunciation proxy).
5. **Measured reliability** — a calibration set and an eval harness reporting Quadratic Weighted Kappa (QWK), exact/adjacent agreement, and score variance per LLM provider. *This is the headline for the MS application.*

---

## 2. Architecture

```
┌──────────────── Next.js (web, :3000) ────────────────┐
│ Mock test runner · Task practice · Feedback report   │
│ Progress dashboard · Settings (keys, models, voice)  │
│ Audio: MediaRecorder (webm/opus) → upload            │
│        (phase 2: WebSocket live captions)            │
└───────────────┬──────────────────────────────────────┘
                │ REST + WS (localhost only)
┌───────────────▼────────── FastAPI (:8000) ───────────┐
│ api/        routers: tests, attempts, scoring, items, settings
│ providers/  speech/ (SpeechProvider → DeepgramProvider)
│             llm/    (LLMProvider → LiteLLMProvider)
│ scoring/    writing_email · writing_discussion · build_sentence
│             listen_repeat · interview · mc · aggregate(bands)
│ features/   text (LanguageTool, MTLD, sentence stats)
│             speech (pauses, WPM, fillers, confidence)
│ content/    item bank loader, generator, validator, TTS cache
│ secrets/    keyring-backed key store
│ eval/       calibration harness (QWK etc.)
│ db: SQLite (SQLModel) · files: ./data/audio, ./data/tts_cache
└──────────────────────────────────────────────────────┘
```

### 2.1 Provider abstraction (so we can expand later)

```python
class SpeechProvider(Protocol):
    async def transcribe(self, audio: bytes, mime: str, opts: STTOptions) -> Transcript   # words[{w,start,end,conf}], fillers
    async def stream(self, ws_in, opts) -> AsyncIterator[TranscriptEvent]                 # phase 2
    async def synthesize(self, text: str, voice: str, fmt="mp3") -> bytes

class LLMProvider(Protocol):
    async def complete_json(self, messages, schema: type[BaseModel], *, temperature=0, seed=None) -> BaseModel
    async def validate_key(self) -> KeyCheck
```

- **Speech (now): Deepgram only.**
  - STT: pre-recorded `/v1/listen` with the current Nova model, `punctuate`, `filler_words=true`, word-level timestamps + confidence. For Listen & Repeat use **verbatim** settings (no smart_format/numerals) so we score what was actually said.
  - TTS: `/v1/speak` with Aura voices — generates all listening/speaking stimuli and interviewer prompts; cached by `hash(text+voice)` so each item is synthesized once.
  - Pin model names in config (`DEEPGRAM_STT_MODEL`, `DEEPGRAM_TTS_VOICE`) and verify against Deepgram docs at build time.
  - Later: Whisper/AssemblyAI/Azure/ElevenLabs just add another class.
- **LLM: LiteLLM** behind our interface → OpenAI, Anthropic, Google Gemini, Mistral, Groq, OpenRouter, Azure, and local Ollama with one code path. Settings page = choose provider → paste key → pick model → "Test key" button.
  - Enforce structured output (JSON schema / tool call) → pydantic validation → 1 repair retry → fail loudly.
  - Maintain a `models.yaml` allow-list of models known to follow the scoring schema well (from our eval results).

### 2.2 Key handling (local-only)

- Stored via Python `keyring` (macOS Keychain / Windows Credential Manager / Secret Service). Fallback: `.env` for headless/dev.
- Backend binds to `127.0.0.1` only; frontend never receives a saved key back (masked `sk-…1234`).
- Keys never logged; request logging redacts `Authorization`/`api_key`.
- Per-session cost/token counter shown in UI (users are paying).

---

## 3. Scoring engine (per task)

| Task | Method | Output |
|---|---|---|
| Complete the Words, Read in Daily Life, Academic Passage, all Listening | Deterministic key match | correct/incorrect, explanation (LLM-generated at item-creation time, stored) |
| Build a Sentence | Exact match + accepted alternates | 0/1 |
| Write an Email / Academic Discussion | **Features + LLM rubric judge** | 0–5, per-dimension judgement, evidence spans, errors list, next-band rewrite |
| Listen and Repeat | **Deterministic alignment** (+ LLM only for friendly explanation) | 0–5, aligned diff (missing/changed/extra words, content vs function), low-confidence words |
| Take an Interview | **Speech features + transcript + LLM rubric judge** | 0–5, fluency/intelligibility/language/relevance notes, filler & pause timeline |

### 3.1 LLM judge design (writing + interview)

1. Pre-compute features → passed to the prompt as facts:
   - Text: word count, sentence count & length variance, MTLD lexical diversity, LanguageTool grammar/spelling hits (run locally via `language_tool_python`), overlap with stimulus (copying check), register markers (email).
   - Speech: speaking time, WPM, articulation rate, # pauses > 0.5 s / > 1 s, mean pause, filler count/min, mean & low word confidence, % of question words reused.
2. Prompt = task stimulus + paraphrased rubric (from `docs/RUBRICS_2026.md`) + features + **anchor examples** (1 per band, from our calibration set) + response.
3. Two-step: (a) judge each dimension with evidence quotes, (b) assign holistic score consistent with them. Holistic is what counts, as in ETS.
4. Reliability: temperature 0, `n=3` samples → median; if spread ≥ 2 → show "low confidence" badge.
5. Hard guards before LLM: empty/non-English/copied-from-prompt → score 0 deterministically.
6. Honest limitation shown in UI: text-only LLMs cannot hear intonation; pronunciation is approximated from STT confidence. (Expansion: audio-capable models as an optional judge.)

### 3.2 Listen & Repeat aligner

normalize (lowercase, expand contractions, strip punctuation) → token alignment (Levenshtein with backtrace) → tag tokens content/function via spaCy → classify edits (missing, substituted-synonym via WordNet/embedding sim, inflection change via lemma match, transposition) → rule table in RUBRICS_2026.md §6 → score. Unit-tested with hand-written cases for every band.

### 3.3 Bands

Raw → band via `band_tables.yaml` (editable), overall = mean of sections rounded to 0.5, plus CEFR and comparable 0–120 (ETS table). Always labelled **"Estimated"**.

---

## 4. Content (item bank)

- Items stored as versioned YAML/JSON in `content/items/<task>/…` with schema validation (pydantic). Fields: id, task, difficulty (A1–C2), stimulus, audio refs, key/alternates, explanations, source.
- **Generation pipeline:** LLM drafts items to spec → validator (length, CEFR vocab level via word-frequency lists, answer uniqueness check by asking a second model to solve it) → TTS audio via Deepgram → human review flag in an admin page.
- Multistage adaptive mock: router module → lower/upper module by router % correct (mirrors the 2026 blueprint).
- **Do not copy ETS practice items into the bank.** Use official practice tests only offline for format checks and calibration.

---

## 5. User features

**MVP**
1. Settings: LLM provider/key/model, Deepgram key, voice, mic test.
2. Task practice for all 12 task types with real timers.
3. Feedback report per response (score, rubric dimensions, evidence highlights, audio playback with pauses/fillers marked, next-band rewrite).
4. Full mock test (≈2 h) with section bands, overall band, CEFR, 0–120 comparable.
5. History & progress charts per task/dimension.

**Phase 2**
6. Weakness-driven study plan (target band + test date → daily tasks).
7. Error notebook + spaced repetition (grammar errors, vocab, mispronounced words re-generated as Listen & Repeat drills via TTS).
8. Live captions while speaking (Deepgram streaming).
9. Shadowing mode (TTS model answer → user repeats → alignment score).
10. Export PDF report.

---

## 6. Evaluation (the MS-application centerpiece)

- **Calibration set:** ~150–300 responses across Email, Discussion, Interview, Listen & Repeat:
  - ETS sample responses with official scores (scoring guide for teachers / practice tests) — kept local, not redistributed.
  - Self-collected responses from volunteers, each scored by 2 trained human raters using the ETS guides (record inter-rater agreement as the ceiling).
- **Metrics:** QWK, exact & ±1 agreement, Pearson r, mean bias, score SD across repeated runs, latency, cost per response.
- **Experiments to report:** LLM-only vs. LLM+features; with/without anchors; provider comparison (GPT / Claude / Gemini / Llama-local); Listen&Repeat rule scorer vs LLM.
- `make eval PROVIDER=… MODEL=…` → writes `eval/results/<date>.md` with tables. Prompt + rubric versions are hashed into every stored score so results are reproducible.

---

## 7. Data model (SQLite)

`profile` (target band, test date) · `item` (id, task, version) · `attempt` (mock or practice, started/finished) · `response` (attempt_id, item_id, text | audio_path, transcript_json, duration) · `score` (response_id, scorer, provider, model, prompt_version, rubric_version, score, dimensions_json, features_json, confidence, cost) · `section_result` · `error_note`.

---

## 8. Repo layout

```
TOEFL-coach/
  PLAN.md  README.md  docker-compose.yml  Makefile  .env.example
  docs/RUBRICS_2026.md   docs/ets/ (git-ignored official PDFs)
  web/                      # Next.js + Tailwind + shadcn/ui
    app/(practice)/[task]/  app/mock/  app/report/[id]/  app/settings/
    components/recorder/ timer/ audio-player/ feedback/
  api/                      # FastAPI
    app/main.py  app/routers/  app/providers/{speech,llm}/
    app/scoring/  app/features/  app/content/  app/secrets/  app/db/
    tests/  eval/
  content/items/<task>/*.yaml   content/band_tables.yaml   content/models.yaml
  data/ (git-ignored: sqlite, audio, tts_cache)
```

---

## 9. Roadmap (≈ 8 weeks part-time)

| Week | Deliverable |
|---|---|
| 1 | Repo scaffold, FastAPI + Next.js, settings page, keyring store, LiteLLM "test key", Deepgram STT/TTS smoke tests |
| 2 | Item schema + loader; Writing tasks UI (Build a Sentence, Email, Discussion) with timers; Build-a-Sentence scorer |
| 3 | Writing LLM judge + text features + feedback report UI |
| 4 | Recorder; Listen & Repeat (TTS stimuli, aligner scorer, unit tests); Interview (TTS interviewer, speech features, LLM judge) |
| 5 | Reading & Listening tasks (MC engine, adaptive router), content generation pipeline + review page |
| 6 | Full mock test, band aggregation, history dashboard |
| 7 | Calibration set + eval harness; tune thresholds/prompts; provider comparison |
| 8 | Polish, README with eval results, demo video, short write-up (method, results, limitations) for the application |

---

## 10. Risks & guardrails

- **Trademark/copyright:** "TOEFL" is an ETS trademark → the app is named "iBT Practice" (practice + estimated scoring, not tutoring), add "not affiliated with or endorsed by ETS", don't redistribute ETS PDFs/items, paraphrase rubrics.
- **Score honesty:** always "estimated"; show confidence; publish eval numbers.
- **LLM variance/cost:** temp 0, median of 3, caching, per-session cost display, cheap-model option.
- **Audio quality:** mic check, minimum duration, re-record option; Deepgram failure → clear error, retry.
- **Privacy:** everything local; audio never leaves the machine except to Deepgram/LLM provider chosen by the user (disclose this in Settings).

## 11. Open decisions

- Single local user vs. multiple local profiles.
- Ship a starter item bank (generated + reviewed) vs. generate on demand.
- Whether to add an optional audio-native LLM judge for Interview in phase 2.
