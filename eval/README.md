# Scoring evaluation

How well do the app's estimated scores agree with trained human raters? This folder holds the calibration data,
the protocol, and the results. **Numbers from `demo` rows are pipeline tests only — never report them.**

## 1. Collect responses

| Source (`source` column) | What | Where it lives |
|---|---|---|
| `ets-sample` | Scored sample responses from official ETS materials (scoring guide for teachers, practice tests) | `eval/private/` only — **never commit or share** |
| `volunteer` | Responses written/recorded by volunteers in the app | `eval/data/` (text) / `eval/private/audio/` (voices) |
| `self` | Your own responses | `eval/data/` |
| `demo` | Developer-written examples to test the pipeline | `eval/data/demo.csv` |

Volunteers: get written consent to store and rate their responses for research; don't collect names in the data;
let them withdraw. Voice recordings are personal data — keep them in `eval/private/` (git-ignored).

Targets for a credible result: **≥ 50 responses per task**, spread across levels (aim for every score 1–5 to
appear), with **≥ 30 % double-rated**.

## 2. Rate them (blind)

Use the in-app rating page (`/rate`): raters see the prompt, the paraphrased rubric and the response (or audio),
but **never the AI score**. Each rater enters a name; the same response is shown to a second rater until it has
two ratings. Then **Export** writes `eval/private/data/app_<task>.csv` (git-ignored, because it contains volunteers' answers).

Rater protocol:
1. Read `docs/RUBRICS_2026.md` and the official ETS scoring guides (`docs/ets/`).
2. Calibrate together on 5 responses (discuss, don't count them), then rate independently.
3. Rate holistically: pick the band that best fits the whole response.
4. Never look at the app's score before rating.

You can also write CSV rows by hand (format below), e.g. for ETS samples whose prompts are not in the app: put the
prompt into `eval/private/prompts/*.yaml` using the same YAML format as `content/items/`.

## 3. CSV format

`id, task, item_id, response_text, audio_file, transcript_json, rater1, rater2, source, notes`

- `task`: `write-an-email`, `academic-discussion`, `take-an-interview`, `listen-and-repeat`
- `item_id`: an item in `content/items/` or `eval/(private/)prompts/`
- writing → `response_text`; speaking → `audio_file` (path from repo root) and/or `transcript_json`
- `rater1` required, `rater2` optional (integers 0–5); gold = their mean, rounded half up

Check the data: `make eval-check`

## 4. Run

```bash
make eval TASK=write-an-email PROVIDER=openai MODEL=gpt-4.1-mini
make eval TASK=write-an-email PROVIDER=anthropic MODEL=claude-sonnet-4-5
make eval TASK=listen-and-repeat           # rules-based, no LLM
make eval-compare                          # → eval/results/COMPARISON.md
make eval-tune-lr                          # tune Listen & Repeat thresholds on a held-out split
```
Add `ARGS="--repeats 2"` to measure test–retest consistency, `ARGS="--include-demo"` to smoke-test with demo rows.
Speaking transcripts are cached so every provider is compared on identical transcripts.

## 5. What gets reported (per task × scorer)

- **QWK** (quadratic weighted kappa) vs gold, with a bootstrap 95 % CI — the standard metric for automated essay
  scoring; **human–human QWK** on double-rated rows is the practical ceiling.
- Exact and within-±1 agreement, Pearson r, mean bias (machine − human), MAE, confusion matrix.
- Consistency: spread between scoring passes, low-confidence rate, test–retest agreement.
- Cost per response and latency; results by source; the largest disagreements (read these!).

Interpretation guide: QWK ≥ 0.7 is commonly treated as acceptable for automated scoring, and the machine should be
within ~0.1 of human–human agreement. Report the confidence interval — with 50 responses it is wide.
