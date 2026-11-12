#!/bin/sh
# Rolls the Kubernetes pods onto the freshly built p03-*:dev images and checks them.
# Docker Desktop shares its image store with Compose, so no push is needed.
# Stops the Compose stack first (same local ports). Results: verify_k8s_output.txt
#   sh scripts/verify_k8s.sh
OUT=verify_k8s_output.txt
{
  echo "== date"; date
  echo "== stop compose (frees ports 9030-9035)"
  docker compose --env-file .env.compose down 2>&1 | tail -3
  echo "== apply manifests (the db-init Job is immutable, so it is deleted and recreated)"
  kubectl -n p03 delete job p03-db-init --ignore-not-found 2>&1
  kubectl apply -k k8s 2>&1 | grep -v unchanged
  echo "== wait for databases and Kafka to be ready again"
  for sts in mysql mongo kafka; do kubectl -n p03 rollout status statefulset/p03-$sts --timeout=240s 2>&1 | tail -1; done
  kubectl -n p03 wait --for=condition=complete job/p03-db-init job/p03-kafka-init --timeout=300s 2>&1
  echo "== restart deployments onto the new images and wait for every rollout"
  kubectl -n p03 rollout restart deployment 2>&1 | wc -l
  for d in $(kubectl -n p03 get deploy -o name); do kubectl -n p03 rollout status $d --timeout=240s 2>&1 | tail -1; done
  sleep 10
  kubectl -n p03 get pods 2>&1
  echo "== client libraries inside the pods (expect pymongo and confluent_kafka versions)"
  kubectl -n p03 exec deploy/p03-event-service -- python -c "import pymongo, confluent_kafka; print('event', pymongo.version, confluent_kafka.version())" 2>&1
  kubectl -n p03 exec deploy/p03-application-service -- python -c "import pymongo, confluent_kafka; print('application', pymongo.version, confluent_kafka.version())" 2>&1
  kubectl -n p03 exec deploy/p03-job-service -- python -c "import pymongo; print('job', pymongo.version)" 2>&1
  echo "== port-forwards + smoke"
  for p in company:9030 student:9031 job:9032 application:9033 event:9034 assistant:9035; do
    kubectl -n p03 port-forward svc/p03-${p%%:*}-service ${p##*:}:${p##*:} >/dev/null 2>&1 &
  done
  sleep 8
  python scripts/smoke.py 2>&1
  echo "== 5-user JMeter trial against Kubernetes"
  ( cd loadtest && rm -f trial_k8s.jtl && jmeter -n -t handshake.jmx -Jusers=5 -Jloops=2 -l trial_k8s.jtl 2>&1 | grep -E "summary =|end of run" )
  awk -F, 'NR>1 && $8=="false" {print "FAILED:", $3, $4}' loadtest/trial_k8s.jtl
  sleep 6
  echo "== kafka offsets in the cluster"
  for t in application.created event.registration_created; do
    printf "%s " "$t"; kubectl -n p03 exec p03-kafka-0 -- /opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server localhost:9092 --topic "$t" 2>&1 | tail -1
  done
  echo "== event-worker log"
  kubectl -n p03 logs deploy/p03-event-worker --tail=8 2>&1 | cut -c1-200
  kill $(jobs -p) 2>/dev/null
  echo "== resource use"
  kubectl top pods -n p03 2>&1 | head -3
} > "$OUT" 2>&1
pkill -f "kubectl -n p03 port-forward" 2>/dev/null
echo "done: results are in $OUT"
