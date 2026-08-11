PY ?= python3

# SAM Makefile build for the CommonLayer. Runs inside the arm64 build container
# (sam build --use-container). Produces a correctly-structured Lambda layer:
#   $(ARTIFACTS_DIR)/python/compass_common/...   (our module)
#   $(ARTIFACTS_DIR)/python/psycopg2/...         (pip deps at the same level)
# The previous python3.12 BuildMethod double-nested the source under
# python/python/, so `import compass_common` failed at runtime.
.PHONY: build-CommonLayer
build-CommonLayer:
	mkdir -p "$(ARTIFACTS_DIR)/python"
	cp -r python/compass_common "$(ARTIFACTS_DIR)/python/compass_common"
	$(PY) -m pip install -r requirements.txt -t "$(ARTIFACTS_DIR)/python"

.PHONY: smoke
smoke: ## run the offline import + behavior smoke test (no network/AWS/DB/psycopg2/boto3)
	PYTHONPATH=python $(PY) tests/smoke.py
