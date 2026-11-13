#!/bin/sh
# Proves the Kafka flow end to end with a brand-new student, so no 409 can hide a
# missing message: sign up, register for an event, apply to a job with a PDF, then
# compare topic offsets before and after. Works for Compose and Kubernetes (both
# publish the gateway on localhost:9036). Results: kafka_flow_output.txt
#   sh scripts/check_kafka_flow.sh
OUT=kafka_flow_output.txt
G=http://localhost:9036
TOPICS="p03.application.created p03.event.registration_created application.created event.registration_created"
offsets() {
  for t in $TOPICS; do
    if command -v kubectl >/dev/null 2>&1 && kubectl -n p03 get pod p03-kafka-0 >/dev/null 2>&1; then
      o=$(kubectl -n p03 exec p03-kafka-0 -- /opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server localhost:9092 --topic $t 2>&1 | tail -1)
    else
      o=$(docker exec p03-kafka /opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server p03-kafka:9092 --topic $t 2>&1 | tail -1)
    fi
    echo "  $o"
  done
}
field() { python3 -c "import sys,json;print(json.load(sys.stdin)['$1'])"; }
{
  echo "== date"; date
  echo "== offsets before"; offsets
  EMAIL="flow$(date +%s)@demo.p03.example.com"
  echo "== sign up a new student ($EMAIL)"
  RESP=$(curl -s -X POST $G/gw/auth/signup -H 'Content-Type: application/json' \
    -d "{\"email\":\"$EMAIL\",\"password\":\"Flowtest!2026x\",\"full_name\":\"Flow Test\",\"city\":\"San Jose\",\"college_name\":\"San Jose State University\",\"major\":\"Data Science\",\"state\":\"California\",\"skills\":\"Python\"}")
  TOKEN=$(echo "$RESP" | field access_token 2>/dev/null)
  [ -n "$TOKEN" ] && echo "  signup ok" || { echo "  signup failed: $RESP" | cut -c1-300; }
  echo "== register for event 1 (expect 201)"
  curl -s -o /dev/null -w "  %{http_code}\n" -X POST $G/gw/events/1/registrations -H "Authorization: Bearer $TOKEN"
  echo "== apply to job 1 with a PDF (expect 201)"
  curl -s -o /dev/null -w "  %{http_code}\n" -X POST $G/gw/jobs/1/applications -H "Authorization: Bearer $TOKEN" -F "resume=@loadtest/resume.pdf;type=application/pdf"
  sleep 8
  echo "== offsets after (the p03.* topics must each be +1; the old ones must not move)"; offsets
  echo "== event worker log"
  if command -v kubectl >/dev/null 2>&1 && kubectl -n p03 get pod p03-kafka-0 >/dev/null 2>&1; then
    kubectl -n p03 logs deploy/p03-event-worker --tail=3 2>&1 | cut -c1-200
  else
    docker logs --tail 3 p03-event-worker 2>&1 | cut -c1-200
  fi
} > "$OUT" 2>&1
echo "done: results are in $OUT"
