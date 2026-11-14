#!/bin/sh
# Publishes the six services (and the frontend) on localhost:9030-9036 through
# Docker Desktop's LoadBalancer support, which can carry real load (unlike
# `kubectl port-forward`). Needs the Compose stack stopped (same ports).
# Live change only: re-applying k8s/ puts the services back to ClusterIP.
docker compose --env-file .env.compose down 2>&1 | tail -1
pkill -f "kubectl -n p03 port-forward" 2>/dev/null
for s in company student job application event assistant frontend; do
  kubectl -n p03 patch svc p03-$s-service -p '{"spec":{"type":"LoadBalancer"}}' >/dev/null 2>&1 \
  || kubectl -n p03 patch svc p03-$s -p '{"spec":{"type":"LoadBalancer"}}' >/dev/null 2>&1
done
sleep 8
kubectl -n p03 get svc 2>&1 | grep -i "loadbalancer" | awk '{print $1, $4, $5}'
printf "frontend gateway: "; curl -s -m 5 http://localhost:9036/healthz || echo "not reachable"
