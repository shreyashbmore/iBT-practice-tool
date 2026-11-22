# iBT Practice (TOEFL iBT 2026 format)

Local-first practice & estimated-scoring app (practice, not tutoring) for the January-2026 TOEFL iBT format.
Bring your own LLM key (OpenAI, Anthropic, Gemini, Groq, Mistral, OpenRouter, or local Ollama). Speech uses Deepgram (STT + TTS).

> Not affiliated with or endorsed by ETS. TOEFL is a registered trademark of ETS. All scores shown are estimates.

- Plan: [PLAN.md](PLAN.md)
- Scoring spec: [docs/RUBRICS_2026.md](docs/RUBRICS_2026.md)

## Requirements
- Python 3.10+
- Node 20+

## Quick start
```bash
make setup     # creates api/.venv and installs web deps
make dev       # API on http://127.0.0.1:8000, web on http://localhost:3000
```
Then open http://localhost:3000/settings, pick your LLM provider, paste keys, and press **Test**.
Use http://localhost:3000/mic-check to verify Deepgram speech-to-text and text-to-speech.

## What works so far
| Page | What it does |
|---|---|
| `/settings` | LLM provider/model/key + Deepgram key, with **Test** buttons |
| `/mic-check` | Deepgram TTS playback, record → transcript + speaking-rate/pause/filler metrics |
| `/practice/build-a-sentence` | Timed 10-item set, click-to-place chunks, instant 0/1 scoring with explanations |
| `/practice/write-an-email` | 7-min timed email, auto-submit at time-out, then **0–5 rubric score** with per-dimension evidence, errors, next-band tips and a stronger rewrite |
| `/practice/academic-discussion` | 10-min timed discussion post, word counter, same rubric feedback |
| `/practice/listen-and-repeat` | Hear a sentence (Deepgram TTS), beep, auto-record; scored 0–5 by a deterministic word-alignment scorer with a colour-coded diff |
| `/practice/take-an-interview` | 4 spoken questions, 45 s answers; transcript, pause/filler/pace metrics and 0–5 rubric feedback |
| `/practice/complete-the-words`, `read-daily-life`, `read-academic-passage` | Reading practice: C-test gaps, everyday texts, academic passages; instant scoring with explanations |
| `/practice/listen-*` | Listening practice: choose-a-response, conversations, announcements, lectures (multi-voice Deepgram TTS, played once; transcript after) |
| `/test/reading-form-01`, `/test/listening-form-01` | **Adaptive section tests**: module 1 routes you to an easier or harder module 2, like the 2026 test |
| `/review` | Generate new original items with your LLM → automatic validation + independent re-solve QA → approve/discard |
| `/mock/mock-01` | **Full mock test**: Reading → Listening → Writing → Speaking, resumable; ends with estimated section bands, overall band (mean, nearest 0.5), CEFR and comparable 0–120 |
| `/progress` | Mock-test band history and per-task trends |
| `/rate` | Blind human rating of saved responses (two raters each) → export to the calibration set |
| `/history` → `/report/[id]` | All saved attempts (SQLite at `data/practice.db`); reopen or re-score any report |

### How writing is scored
Deterministic checks first (blank, not English, copied from the prompt → 0). Otherwise your chosen LLM gets the task,
the paraphrased 2026 rubric, measured text features and your response; it returns per-dimension judgements with
quotes, a holistic 0–5 score, errors and a rewrite. Extra cheap score-only passes (Settings → *Scoring passes*) give a
median score and flag disagreement as *low confidence*. Quotes the model invents are dropped. Every score stores the
model, rubric version and prompt version.

### How bands are estimated
`content/band_tables.yaml`: section % → old 0–30 scale → ETS's published old↔new comparison table → 1–6 band.
Adaptive sections weight an easier module 2 down (`lower_module_weight`). Overall = mean of section bands rounded to
the nearest 0.5; comparable total = midpoint of ETS's 0–120 range for that band. Always labelled as an estimate.

Practice content lives in `content/items/` (YAML, original items). Run `make validate` after editing.

## Measuring scoring accuracy
See [eval/README.md](eval/README.md): collect responses, rate them blind on `/rate`, then
`make eval TASK=write-an-email PROVIDER=… MODEL=…` → QWK (with 95% CI), exact / ±1 agreement, bias, consistency,
cost and latency vs human raters; `make eval-compare` builds the provider comparison table.

## Where keys are stored
Keys are saved in your OS keychain (macOS Keychain / Windows Credential Manager / Secret Service) under the service
`ibt-practice`. If no keychain is available they fall back to `data/secrets.json` (chmod 600). Environment variables
(see `.env.example`) override both. The API only listens on 127.0.0.1 and never returns saved keys to the browser.

## Tests
```bash
make test
```
