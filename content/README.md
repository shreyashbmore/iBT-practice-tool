# Content

Every `*.yaml` under `items/` is one practice set, validated by `api/app/content/models.py` at startup.
All items here are **original**. Do not paste ETS practice-test items into this folder.

Check your edits with:
```bash
cd api && .venv/bin/python -m app.content.validate
```

Timing notes: Email (7 min) and Academic Discussion (10 min) follow the ETS format. The Build a Sentence
set time is an approximation derived from the ~23-minute Writing section; adjust if official guidance differs.

## Layout
- `items/<section>/*.yaml` — practice sets (hand-written). `items/<section>/generated/` — LLM-generated sets you approved on `/review`.
- `forms/*.yaml` — adaptive section tests: `router` sets, then `lower` or `upper` sets depending on router % ≥ `upper_threshold`.
- `drafts/` — generated sets waiting for review (git-ignored, never served for practice).

Multiple-choice options are shuffled deterministically when shown, so the position of the correct answer in the YAML
doesn't matter. Listening scripts are never sent to the browser before the answers are submitted.
