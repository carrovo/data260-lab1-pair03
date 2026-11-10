.PHONY: test smoke up down ps seed kafka-demos

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

# Kafka failure demos (duplicate, restart/replay, poison -> DLQ); needs the stack up
kafka-demos:
	bash scripts/kafka_demos.sh all
