#!/bin/sh
# Switches the Kubernetes deployment between MongoDB and MySQL persistence for
# companies, jobs and events, reseeds, and checks it.
#   sh scripts/k8s_mongo.sh on      (PERSISTENCE=mongo)
#   sh scripts/k8s_mongo.sh off     (back to PERSISTENCE=sql)
# The repo's k8s/config.yaml is never edited; the value is changed while applying.
# Results: k8s_mongo_output.txt
MODE=${1:-on}
[ "$MODE" = "on" ] && V=mongo || V=sql
OUT=k8s_mongo_output.txt
{
  echo "== date / target"; date; echo "PERSISTENCE=$V"
  kubectl -n p03 delete job p03-db-init --ignore-not-found 2>&1
  kubectl kustomize k8s | sed "s/^  PERSISTENCE: .*/  PERSISTENCE: $V/" | kubectl apply -f - 2>&1 | grep -v unchanged
  kubectl -n p03 wait --for=condition=complete job/p03-db-init --timeout=300s 2>&1
  echo "== reseed (SEED=3)"
  kubectl -n p03 delete job p03-seed --ignore-not-found 2>&1
  kubectl apply -f k8s/optional/seed-job.yaml 2>&1
  kubectl -n p03 wait --for=condition=complete job/p03-seed --timeout=300s 2>&1
  kubectl -n p03 logs job/p03-seed 2>&1 | tail -10
  echo "== restart services onto the new setting"
  kubectl -n p03 rollout restart deployment 2>&1 | wc -l
  for d in $(kubectl -n p03 get deploy -o name); do kubectl -n p03 rollout status $d --timeout=240s 2>&1 | tail -1; done
  sleep 10
  echo "== setting seen by a pod"
  kubectl -n p03 exec deploy/p03-event-service -- printenv PERSISTENCE
  echo "== expose + smoke"
  sh scripts/k8s_expose.sh
  python scripts/smoke.py
  echo "== 5-user trial"
  ( cd loadtest && rm -f trial_k8s_$V.jtl && jmeter -n -t handshake.jmx -Jusers=5 -Jloops=2 -l trial_k8s_$V.jtl 2>&1 | grep -E "summary =" | tail -1 )
  awk -F, 'NR>1 && $8=="false"{print "FAILED:",$3,$4}' loadtest/trial_k8s_$V.jtl
  sleep 6
  echo "== Mongo contents"
  kubectl -n p03 exec p03-mongo-0 -- mongosh p03_handshake --quiet --eval 'printjson({companies: db.companies.countDocuments({}), jobs: db.jobs.countDocuments({}), events: db.events.countDocuments({}), registrations: db.registrations.countDocuments({})})' 2>&1
  echo "== Kafka offsets"
  for t in application.created event.registration_created; do
    printf "%s " $t; kubectl -n p03 exec p03-kafka-0 -- /opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server localhost:9092 --topic $t 2>&1 | tail -1
  done
  echo "== errors in event-service / application-service logs (expect 0)"
  kubectl -n p03 logs deploy/p03-event-service deploy/p03-application-service --since=10m 2>&1 | grep -ci "traceback"
} > "$OUT" 2>&1
echo "done: results are in $OUT"
