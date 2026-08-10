PY ?= python3

.PHONY: smoke
smoke: ## run the offline import + behavior smoke test (no network/AWS/DB/psycopg2/boto3)
	PYTHONPATH=python $(PY) tests/smoke.py
