.PHONY: setup up down seed seed-full test lint wait-for-fhir

setup:
	uv sync --extra ml --extra safety --extra assistant

up:
	docker compose up -d --build
	$(MAKE) wait-for-fhir
	uv run python scripts/bootstrap_db.py

down:
	docker compose down

wait-for-fhir:
	@echo "Waiting for HAPI FHIR to be ready on :8210..."
	@for i in $$(seq 1 90); do \
		if curl -sf http://localhost:8210/fhir/metadata > /dev/null; then \
			echo "HAPI FHIR is up."; \
			exit 0; \
		fi; \
		sleep 2; \
	done; \
	echo "HAPI FHIR did not become ready in time" >&2; exit 1

seed:
	uv run python fhir/seed/load.py --count 300

seed-full:
	uv run python fhir/seed/load.py --count 2000

test:
	uv run pytest

lint:
	uv run ruff check .
