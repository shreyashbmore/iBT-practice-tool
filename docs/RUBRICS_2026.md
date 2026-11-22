# TOEFL iBT 2026 — Task Formats & Scoring Spec (for the scoring engine)

> Source of truth: ETS official documents (verified 21 Nov 2026). Descriptors below are **paraphrased** for engineering use.
> Download the originals into `docs/ets/` (git-ignored) and keep them as the reference — do not redistribute ETS material.
>
> - Test content page: https://www.ets.org/toefl/test-takers/ibt/about/content.html
> - Test specifications 2026 (blueprint): https://www.ets.org/content/dam/ets-org/pdfs/toefl/toefl-ibt-test-specifications-2026.pdf
> - Writing scoring guide (Email + Academic Discussion): https://www.ets.org/content/dam/ets-org/pdfs/toefl/writing-rubrics.pdf
> - Speaking scoring guide (Listen & Repeat + Interview): https://www.ets.org/content/dam/ets-org/pdfs/toefl/speaking-rubrics.pdf
> - Scoring guide for teachers: https://www.ets.org/content/dam/ets-org/pdfs/toefl/toefl-ibt-scoring-guide-for-teachers.pdf
> - Score scale / comparison table: https://www.ets.org/toefl/test-takers/ibt/scores/understand-scores.html
> - Official practice tests (for format + calibration only): linked from https://www.ets.org/toefl/teachers-advisors-agents/ibt/teaching/preparing-students.html

---

## 1. Test blueprint (from the 2026 specification document)

| Section | Task types | Items | Scoring | Raw pts | Time |
|---|---|---|---|---|---|
| Reading | Complete the Words · Read in Daily Life · Read an Academic Passage | 50 (30 + 20) | machine (MC / fill) | 35 | ~30 min, multistage adaptive (router → lower/upper module) |
| Listening | Listen and Choose a Response · Listen to a Conversation · Listen to an Announcement · Listen to an Academic Talk | 47 | machine | 35 | ~29 min, multistage adaptive |
| Writing | Build a Sentence (10) · Write an Email (1) · Write for an Academic Discussion (1) | 12 | Build a Sentence = machine, 1 pt each; Email & Discussion = AI-scored, 0–5 each | 20 | ~23 min |
| Speaking | Listen and Repeat (7) · Take an Interview (4) | 11 | AI-scored, 0–5 each | 55 | ~8 min |

Total ≈ 2 h incl. directions. Item counts/time vary because the test adapts.

## 2. Score reporting (since 21 Jan 2026)

- Each section reported on a **1–6 band scale in 0.5 steps**, aligned to CEFR.
- **Overall = mean of the 4 section bands, rounded to nearest 0.5.**
- For a 2-year transition, a comparable 0–120 total is also reported.
- ETS comparison table (old → new), useful for the "comparable 0–120" display:

| Band | Reading | Listening | Speaking | Writing | Total (0–120) |
|---|---|---|---|---|---|
| 6 | 29–30 | 28–30 | 28–30 | 29–30 | 114+ |
| 5.5 | 27–28 | 26–27 | 27 | 27–28 | 107+ |
| 5 | 24–26 | 22–25 | 25–26 | 24–26 | 95+ |
| 4.5 | 22–23 | 20–21 | 23–24 | 21–23 | 86+ |
| 4 | 18–21 | 17–19 | 20–22 | 17–20 | 72+ |
| 3.5 | 12–17 | 13–16 | 18–19 | 15–16 | 58+ |
| 3 | 6–11 | 9–12 | 16–17 | 13–14 | 44+ |
| 2.5 | 4–5 | 6–8 | 13–15 | 11–12 | 34+ |
| 2 | 3 | 4–5 | 10–12 | 7–10 | 24+ |
| 1.5 | 2 | 2–3 | 5–9 | 3–6 | 12+ |
| 1 | 0–1 | 0–1 | 0–4 | 0–2 | 0+ |

> Raw → band conversion is IRT-based and not published. Our app shows an **estimated** band from a configurable
> lookup (`scoring/band_tables.yaml`), calibrated against official practice-test results. Always label it "estimate".

---

## 3. Writing — Write an Email (0–5)

Dimensions the scorer must judge (from ETS guide): **communicative purpose/elaboration**, **syntactic variety & word choice (idiomatic precision)**, **social conventions** (politeness, register, organization, how requests/refusals/complaints are formulated), **lexical/grammatical accuracy**.

| Score | Label | Paraphrased descriptor |
|---|---|---|
| 5 | Fully successful | Effective, clear, consistent facility. Elaboration fully supports the purpose; varied syntax; precise, idiomatic vocabulary; consistently appropriate social conventions; at most typo-level errors expected of a competent writer under time pressure. |
| 4 | Generally successful | Mostly effective, easy to understand. Adequate elaboration; some syntactic variety, appropriate vocabulary; mostly appropriate conventions; few errors. |
| 3 | Partially successful | Generally accomplishes the task, but language limits make parts unclear. Partial elaboration; moderate range of syntax/vocab; noticeable errors in structure, word forms, idiom and/or social conventions. |
| 2 | Mostly unsuccessful | Attempts the task but mostly ineffective; message limited or hard to interpret. Limited/irrelevant elaboration; some connected sentence-level language with limited range; accumulated errors. |
| 1 | Unsuccessful | Ineffective; message may be close to unintelligible. Little elaboration; telegraphic/disconnected phrases; serious frequent errors; mostly copied from the stimulus. |
| 0 | — | Blank, off-topic, not English, copied entirely from prompt, unrelated, or random keystrokes. |

## 4. Writing — Academic Discussion (0–5)

Dimensions: **relevance & contribution to the discussion**, **elaboration (explanations, examples, details)**, **syntactic variety**, **precise/idiomatic word choice**, **accuracy**.

| Score | Label | Paraphrased descriptor |
|---|---|---|
| 5 | Fully successful | Relevant, very clearly expressed contribution; consistent facility. Well-elaborated explanations/examples; varied syntax; precise idiomatic vocabulary; at most typo-level errors. |
| 4 | Generally successful | Relevant contribution; easy to follow. Adequately elaborated; variety of structures; appropriate vocabulary; few errors. |
| 3 | Partially successful | Mostly relevant and understandable; some facility. Parts of explanation missing, unclear or irrelevant; some variety; noticeable errors. |
| 2 | Mostly unsuccessful | Attempt to contribute, but language makes ideas hard to follow. Poorly elaborated / partly relevant; limited range; accumulated errors. |
| 1 | Unsuccessful | Ineffective attempt; language may prevent expression of ideas. Few/no coherent ideas; severely limited range; serious frequent errors; mostly borrowed from stimulus. |
| 0 | — | Same as Email 0. |

## 5. Writing — Build a Sentence (0/1)

Reorder given chunks into a correct sentence answering a social/interpersonal prompt. 1 point if exactly correct, else 0. Engine: exact match against the key (+ list of accepted alternative orders).

---

## 6. Speaking — Listen and Repeat (0–5)

Hear a sentence (campus/academic scenario with an image), repeat it exactly. Increasing length/complexity across 7 items.

| Score | Paraphrased descriptor | Engine rule (deterministic first draft) |
|---|---|---|
| 5 | Exact, fully intelligible repetition. | WER = 0 on normalized text AND mean word confidence ≥ τ_high |
| 4 | Meaning fully captured, not exact: e.g. 1–2 function words missing/changed, a content word missing in long stimuli or swapped for a related word, tense/aspect/number marker wrong, two words transposed, or 1–2 content words unclear; self-correction allowed. | ≤ 2 function-word edits, ≤ 1 content-word edit/swap, meaning-preserving |
| 3 | Essentially full sentence but meaning not accurate: majority of content words present; several function words changed/missing, ≥1 content word missing/changed; occasional intelligibility issues. | ≥ 50% content words matched, full clause produced |
| 2 | Significant part missing and/or highly inaccurate: big chunk left out (e.g. only first part, then stops/fills), not a standalone sentence, low intelligibility. | ≥ 1/3 content words but < 50%, OR ≥ 50% without reaching the end of the sentence |
| 1 | Very little of the prompt or largely unintelligible: a few words only, recognisable attempt. | < 1/3 content words, some overlap |
| 0 | No response, unintelligible, no English, unrelated, or only "I don't know"-type phrases. | empty transcript / no overlap |

Implemented in `api/app/scoring/listen_repeat.py` (`listen-repeat-rules-v1`): content vs. function words via a closed-class function-word list (no model download); inflection = same stem; transposition = a missing word said elsewhere; repeated words/self-corrections and fillers are ignored; 'full sentence' = one of the last two content words was said; 'unclear' = Deepgram word confidence < 0.5. A content-word miss can still be a 4 only when the sentence has ≥ 6 content words. Thresholds are constants to be tuned on calibration data (week 7).

## 7. Speaking — Take an Interview (0–5)

Simulated interviewer (video/audio) asks 4 questions; respond immediately (~45 s each — confirm against official practice test).

Dimensions: **task/topic relevance & elaboration**, **fluency & pace (pauses, fillers)**, **intelligibility (pronunciation, rhythm, intonation)**, **grammar & vocabulary range/accuracy**.

| Score | Label | Paraphrased descriptor |
|---|---|---|
| 5 | Fully successful | Fully addresses the question, clear and fluent. On topic and well elaborated; natural pace with appropriate pauses; easily intelligible; accurate, varied grammar/vocabulary conveying precise meaning. |
| 4 | Generally successful | Addresses the question, reasonably clear. Elaborated but connectors may be weak; good pace with some pauses affecting flow; occasional words need minor listener effort; grammar/vocab adequate for general meanings. |
| 3 | Partially successful | Addresses question with limited elaboration and/or clarity. Frequent/long pauses, choppy, frequent fillers; intelligibility sometimes affected at word or stress level; limited range/accuracy restricts precision. |
| 2 | Mostly unsuccessful | Attempt, but not meaningfully/intelligibly supported. Minimal connection to the question or reuse of question language; meaning often hard to discern; very limited grammar/vocab. |
| 1 | Unsuccessful | Minimally addresses the question; very limited control. Vaguely connected; mostly unintelligible; isolated words/phrases. |
| 0 | — | No response, unintelligible, no English, unrelated, or only "I don't know"-type phrases. |

---

## 8. Section-level aggregation (our estimate)

```
writing_raw  = sum(build_sentence[0..9]) + email(0-5) + discussion(0-5)          # max 20
speaking_raw = sum(listen_repeat[0..6]) + sum(interview[0..3])                   # max 55
reading_raw / listening_raw = weighted correct (max 35 each)
section_band = lookup(band_tables.yaml[section], raw / max)                       # 1.0–6.0, step 0.5
overall_band = round_half(mean(4 section bands))
comparable_0_120 = midpoint of ETS comparison row for overall_band
cefr = {6:C2, 5–5.5:C1, 4–4.5:B2, 3–3.5:B1, 2–2.5:A2, 1–1.5:A1}   # verify against ETS score-scale page
```
