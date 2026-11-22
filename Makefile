.PHONY: setup api web dev test validate eval eval-check eval-compare eval-tune-lr

setup:
	cd api && python3 -m venv .venv && .venv/bin/pip install -U pip && .venv/bin/pip install -e ".[dev]"
	cd web && npm install

api:
	cd api && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

web:
	cd web && npm run dev

dev:
	$(MAKE) -j2 api web

test:
	cd api && .venv/bin/pytest -q

validate:
	cd api && .venv/bin/python -m app.content.validate

eval-check:
	cd api && .venv/bin/python -m app.evals.dataset

eval:
	cd api && .venv/bin/python -m app.evals.run --task $(TASK) $(if $(PROVIDER),--provider $(PROVIDER)) $(if $(MODEL),--model $(MODEL)) $(ARGS)

eval-compare:
	cd api && .venv/bin/python -m app.evals.compare

eval-tune-lr:
	cd api && .venv/bin/python -m app.evals.tune_lr $(ARGS)
