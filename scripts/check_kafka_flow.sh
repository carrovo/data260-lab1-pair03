#!/bin/sh
# Proves the Kafka flow end to end with a brand-new student, so no 409 can hide a
# missing message: sign up, register for an event, apply to a job, replace its
# resume, then compare topic offsets before and after. Works for Compose and Kubernetes (both
# publish the gateway on localhost:9036). Results: kafka_flow_output.txt
#   sh scripts/check_kafka_flow.sh
OUT=kafka_flow_output.txt
G=${G:-http://localhost:9036}
TOPICS="p03.application.created p03.application.updated p03.event.registration_created application.created application.updated event.registration_created"
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
off() { # number of messages on one topic
  if command -v kubectl >/dev/null 2>&1 && kubectl -n p03 get pod p03-kafka-0 >/dev/null 2>&1; then
    kubectl -n p03 exec p03-kafka-0 -- /opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server localhost:9092 --topic $1 2>&1 | tail -1 | awk -F: '{print $3+0}'
  else
    docker exec p03-kafka /opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server p03-kafka:9092 --topic $1 2>&1 | tail -1 | awk -F: '{print $3+0}'
  fi
}
processed() { # lines "processed event_id" a worker logged in the last 90 s (0 if the worker is missing)
  if command -v kubectl >/dev/null 2>&1 && kubectl -n p03 get pod p03-kafka-0 >/dev/null 2>&1; then
    kubectl -n p03 logs deploy/p03-$1 --since=90s 2>/dev/null | grep -c "processed event_id"
  else
    docker logs --since 90s p03-$1 2>&1 | grep -c "processed event_id"
  fi
}
field() { python3 -c "import sys,json;print(json.load(sys.stdin)['$1'])"; }
{
  echo "== date"; date
  B_AC=$(off p03.application.created); B_AU=$(off p03.application.updated); B_ER=$(off p03.event.registration_created)
  B_OLD=$(( $(off application.created) + $(off application.updated) + $(off event.registration_created) ))
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
  APPLICATION=$(curl -s -X POST $G/gw/jobs/1/applications -H "Authorization: Bearer $TOKEN" -F "resume=@loadtest/resume.pdf;type=application/pdf")
  APPLICATION_ID=$(echo "$APPLICATION" | field id 2>/dev/null)
  [ -n "$APPLICATION_ID" ] && echo "  application $APPLICATION_ID created" || { echo "  application failed: $APPLICATION" | cut -c1-300; }
  echo "== replace the application resume (expect 200)"
  curl -s -o /dev/null -w "  %{http_code}\n" -X PUT $G/gw/applications/$APPLICATION_ID/resume -H "Authorization: Bearer $TOKEN" -F "resume=@loadtest/resume.pdf;type=application/pdf"
  sleep 8
  echo "== offsets after (the p03.* topics must each be +1; the old ones must not move)"; offsets
  echo "== event worker log"
  if command -v kubectl >/dev/null 2>&1 && kubectl -n p03 get pod p03-kafka-0 >/dev/null 2>&1; then
    kubectl -n p03 logs deploy/p03-event-worker --tail=3 2>&1 | cut -c1-200
  else
    docker logs --tail 3 p03-event-worker 2>&1 | cut -c1-200
  fi
  echo "== application worker log"
  if command -v kubectl >/dev/null 2>&1 && kubectl -n p03 get pod p03-kafka-0 >/dev/null 2>&1; then
    kubectl -n p03 logs deploy/p03-application-worker --tail=5 2>&1 | cut -c1-200
  else
    docker logs --tail 5 p03-application-worker 2>&1 | cut -c1-200
  fi
  echo "== verdict (each check must pass; a stale or missing worker fails it)"
  A_AC=$(off p03.application.created); A_AU=$(off p03.application.updated); A_ER=$(off p03.event.registration_created)
  A_OLD=$(( $(off application.created) + $(off application.updated) + $(off event.registration_created) ))
  FAIL=0
  chk() { if [ "$2" = "ok" ]; then echo "  PASS  $1"; else echo "  FAIL  $1"; FAIL=1; fi; }
  [ $((A_AC - B_AC)) -eq 1 ] && chk "p03.application.created +1" ok || chk "p03.application.created +1 (got $((A_AC - B_AC)))" no
  [ $((A_AU - B_AU)) -eq 1 ] && chk "p03.application.updated +1" ok || chk "p03.application.updated +1 (got $((A_AU - B_AU)))" no
  [ $((A_ER - B_ER)) -eq 1 ] && chk "p03.event.registration_created +1" ok || chk "p03.event.registration_created +1 (got $((A_ER - B_ER)))" no
  [ "$A_OLD" -eq "$B_OLD" ] && chk "unprefixed topics did not move" ok || chk "unprefixed topics moved" no
  [ "$(processed event-worker)" -ge 1 ] && chk "event worker processed the registration (last 90 s)" ok || chk "event worker processed nothing in the last 90 s (stale or missing)" no
  [ "$(processed application-worker)" -ge 2 ] && chk "application worker processed created + updated (last 90 s)" ok || chk "application worker processed fewer than 2 events in the last 90 s (stale or missing)" no
  if [ $FAIL -eq 0 ]; then echo "RESULT: PASS"; else echo "RESULT: FAIL"; fi
} > "$OUT" 2>&1
tail -9 "$OUT"
echo "done: results are in $OUT"
