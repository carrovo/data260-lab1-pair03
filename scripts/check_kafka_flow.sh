#!/bin/sh
# Proves the Kafka flow end to end with a brand-new student, so no 409 can hide a
# missing message: sign up, register for an event, apply to a job, replace its
# resume, then compare topic offsets before and after and look up the exact MongoDB
# documents (registration, application, processed_events) that this run created. Works for Compose and Kubernetes (both
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
mq() { # run one mongosh expression in the p03_handshake database and print its output
  if command -v kubectl >/dev/null 2>&1 && kubectl -n p03 get pod p03-kafka-0 >/dev/null 2>&1; then
    kubectl -n p03 exec p03-mongo-0 -- mongosh --quiet p03_handshake --eval "$1" 2>/dev/null
  else
    docker exec p03-mongo mongosh --quiet p03_handshake --eval "$1" 2>/dev/null
  fi
}
verify_documents() { # looks up the exact registration and application THIS run created (up to 30 s)
  JS="var reg=db.registrations.findOne({_id:'$REG_ID'}); var app=db.applications.findOne({_id:'$APPLICATION_ID'});
function n(c,t,e){return t?db.processed_events.countDocuments({consumer:c,trace_id:t,event_type:e}):0}
print(JSON.stringify({reg:reg,app:app,reg_done:n('event-worker',reg&&reg.trace_id,'event.registration_created'),
app_done:app?db.processed_events.countDocuments({_id:'application-worker:'+app.last_event_id}):0}))"
  i=0
  while [ $i -lt 10 ]; do
    mq "$JS" | SID="$SID" REG_ID="$REG_ID" APP_ID="$APPLICATION_ID" python3 -c "
import sys, json, os
try:
    d = json.loads(sys.stdin.read())
except ValueError:
    print('  FAIL  could not read the MongoDB answer'); sys.exit(1)
sid, reg_id, app_id = os.environ['SID'], os.environ['REG_ID'], os.environ['APP_ID']
reg, app = d.get('reg'), d.get('app')
checks = [
  ('registrations document %s is for student %s, event 1' % (reg_id, sid), bool(reg) and reg.get('student_id') == sid and reg.get('event_id') == '1'),
  ('event worker recorded this registration event in processed_events (same trace_id)', d.get('reg_done') == 1),
  ('applications document %s is for student %s, job 1' % (app_id, sid), bool(app) and app.get('student_id') == sid and app.get('job_id') == '1'),
  ('application worker recorded this application last event in processed_events', d.get('app_done') == 1),
  ('both application events were applied (created_at differs from updated_at)', bool(app) and bool(app.get('created_at')) and app.get('created_at') != app.get('updated_at')),
]
for text, ok in checks:
    print(('  PASS  ' if ok else '  FAIL  ') + text)
sys.exit(0 if all(ok for _, ok in checks) else 1)
" > /tmp/p03_verify.txt && return 0
    i=$((i + 1)); sleep 3
  done
  return 1
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
  SID=$(echo "$RESP" | python3 -c "import sys,json;print(json.load(sys.stdin)['student']['id'])" 2>/dev/null)
  [ -n "$TOKEN" ] && echo "  signup ok" || { echo "  signup failed: $RESP" | cut -c1-300; }
  echo "== register for event 1 (expect 201)"
  REG=$(curl -s -w '\n%{http_code}' -X POST $G/gw/events/1/registrations -H "Authorization: Bearer $TOKEN")
  echo "  $(echo "$REG" | tail -1)"
  REG_ID=$(echo "$REG" | sed '$d' | field id 2>/dev/null)
  [ -n "$REG_ID" ] && echo "  registration $REG_ID created" || echo "  registration id not found in the response"
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
  echo "== exact documents created by this run (MongoDB)"
  if verify_documents; then cat /tmp/p03_verify.txt; else cat /tmp/p03_verify.txt 2>/dev/null; FAIL=1; fi
  if [ $FAIL -eq 0 ]; then echo "RESULT: PASS"; else echo "RESULT: FAIL"; fi
} > "$OUT" 2>&1
tail -9 "$OUT"
echo "done: results are in $OUT"
