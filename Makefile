# Convenience targets. On Windows without make, run the commands by hand
# (they are listed in README "Quick start").

PY ?= python3
VENV := backend/.venv
ifeq ($(OS),Windows_NT)
  BIN := $(VENV)/Scripts
else
  BIN := $(VENV)/bin
endif

# Requests proxied from the web container reach the API from the Docker bridge.
TRUSTED_PROXIES ?= 127.0.0.1,::1,172.16.0.0/12
# Docker Desktop forwards host.docker.internal to 127.0.0.1. On Linux, bind the
# docker0 bridge address instead (API_HOST=172.17.0.1) so only containers can reach it.
API_HOST ?= 127.0.0.1

.PHONY: help sandbox images venv api web up down test test-unit lint frontend-check clean

help:
	@echo "make images   - build the sandbox and web images"
	@echo "make venv     - create backend/.venv with the API dependencies"
	@echo "make api      - run the API on the host (port 8000)"
	@echo "make web      - serve the UI on http://localhost:5173"
	@echo "make up       - images + venv + web, then run the API in the foreground"
	@echo "make test     - backend tests (Docker integration tests included when available)"

sandbox:
	docker build -t optlens-sandbox:latest sandbox

images:
	docker compose --profile build build

venv:
	$(PY) -m venv $(VENV)
	$(BIN)/python -m pip install -q -e "backend[dev]"

api:
	cd backend && OPTLENS_TRUSTED_PROXIES=$(TRUSTED_PROXIES) \
		../$(BIN)/python -m uvicorn optlens.main:app --host $(API_HOST) --port 8000

web:
	docker compose up -d web

up: images venv web api

down:
	docker compose down

test:
	cd backend && ../$(BIN)/python -m pytest -q

test-unit:
	cd backend && ../$(BIN)/python -m pytest -q -m "not integration"

lint:
	cd backend && ../$(BIN)/ruff check .

frontend-check:
	cd frontend && npm ci && npm run lint && npm run build

clean:
	rm -rf frontend/dist backend/data
