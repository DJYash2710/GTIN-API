.PHONY: setup up down build logs restart test seed shell health dev docker-setup

COMPOSE = docker compose
API_PORT ?= 8000
API_PUBLISH_PORT ?= 8000
MYSQL_PUBLISH_PORT ?= 3307

setup:
	@if [ ! -f .env ]; then cp .env.example .env && echo "Created .env from .env.example"; else echo ".env already exists"; fi

docker-setup: setup
	$(COMPOSE) up --build -d

up: setup
	$(COMPOSE) up --build -d
	@echo ""
	@echo "Local:   http://127.0.0.1:$(API_PUBLISH_PORT)"
	@echo "LAN:     http://<this-pc-ip>:$(API_PUBLISH_PORT)  (ipconfig / ifconfig)"
	@echo "Health:  http://127.0.0.1:$(API_PUBLISH_PORT)/health"
	@echo "MySQL:   127.0.0.1:$(MYSQL_PUBLISH_PORT) (user gtin / pass gtin)"
	@echo "API key: $${API_KEY:-dev-local-key} (set in .env)"

up-fg: setup
	$(COMPOSE) up --build

down:
	$(COMPOSE) down

build:
	$(COMPOSE) build

logs:
	$(COMPOSE) logs -f

restart:
	$(COMPOSE) restart api

seed:
	$(COMPOSE) exec api python scripts/seed_samples_to_db.py

shell:
	$(COMPOSE) exec api sh

health:
	curl -s http://127.0.0.1:$(API_PUBLISH_PORT)/health

dev:
	uvicorn app.main:app --reload --host $${API_HOST:-0.0.0.0} --port $(API_PORT)

test:
	python -m pytest tests/ -q

test-docker:
	$(COMPOSE) exec api python -m pytest tests/ -q
