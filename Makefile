.PHONY: test smoke up down ps seed kafka-demos k8s-secret k8s-up k8s-seed k8s-status k8s-down

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

smoke:
	python scripts/smoke.py $(SMOKE_ARGS)

# Kafka failure demos (duplicate, restart/replay, poison -> DLQ); needs the stack up
kafka-demos:
	bash scripts/kafka_demos.sh all

# ---- Kubernetes (namespace p03). Needs kubectl pointing at a cluster, and the
# images built locally (docker compose build) for Docker Desktop Kubernetes.
k8s-secret:
	kubectl apply -f k8s/namespace.yaml
	kubectl -n p03 create secret generic p03-secrets --from-env-file=.env.compose --dry-run=client -o yaml | kubectl apply -f -

k8s-up: k8s-secret
	kubectl -n p03 delete job p03-db-init p03-kafka-init --ignore-not-found
	kubectl apply -k k8s

k8s-seed:
	kubectl -n p03 delete job p03-seed --ignore-not-found
	kubectl apply -f k8s/optional/seed-job.yaml
	kubectl -n p03 wait --for=condition=complete job/p03-seed --timeout=300s
	kubectl -n p03 logs job/p03-seed | tail -12

k8s-status:
	kubectl -n p03 get pods,svc,jobs,pvc

k8s-down:
	kubectl delete namespace p03
