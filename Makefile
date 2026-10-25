.PHONY: up down test audit e2e load lint verify

up:
	docker compose -f deploy/docker-compose.yml up -d

down:
	docker compose -f deploy/docker-compose.yml down

test:
	PYTHONPATH=backend/src pytest backend/tests frontend/tests -v

audit:
	python3 ../../tools/audit_fakes.py --project .

e2e:
	PYTHONPATH=backend/src pytest backend/tests -v

load:
	PYTHONPATH=backend/src python3 -m pytest backend/tests -k "load or benchmark or stress" || true

lint:
	python3 -m ruff check backend/ || true

verify: audit test
