.PHONY: test smoke up down ps seed

ENVFILE ?= .env.compose
COMPOSE = docker compose --env-file $(ENVFILE)

test:
	python -m pytest backend/tests -q

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

ps:
	$(COMPOSE) ps

seed:
	$(COMPOSE) --profile seed run --rm p03-seed

# Until Xuanhua's branch is merged: make smoke SMOKE_ARGS="--skip student"
smoke:
	python scripts/smoke.py $(SMOKE_ARGS)
