#!/bin/sh
# One-command check of the running Compose stack. Writes everything to verify_output.txt
# (git-ignored) so it can be read without copying terminal output around.
#   sh scripts/verify_stack.sh            (run from the repo root, stack already up)
OUT=verify_output.txt
COMPOSE="docker compose --env-file .env.compose"
{
  echo "== date";            date
  echo "== PERSISTENCE";      grep -E '^PERSISTENCE=' .env.compose || echo "PERSISTENCE not set (sql)"
  echo "== smoke";            python scripts/smoke.py
  echo "== jmeter 5-user trial"
  ( cd loadtest && rm -f trial_verify.jtl && jmeter -n -t handshake.jmx -Jusers=5 -Jloops=2 -l trial_verify.jtl 2>&1 | grep -E "summary =|end of run" )
  echo "== failed requests (expect none)"
  awk -F, 'NR>1 && $8=="false" {print $3, $4, $5}' loadtest/trial_verify.jtl
  echo "== status codes per request"
  awk -F, 'NR>1 {c[$3" "$4]++} END{for(k in c) print c[k], k}' loadtest/trial_verify.jtl | sort -k2
  sleep 8
  echo "== mongo counts"
  docker exec p03-mongo mongosh p03_handshake --quiet --eval 'printjson({companies: db.companies.countDocuments({}), jobs: db.jobs.countDocuments({}), events: db.events.countDocuments({}), registrations: db.registrations.countDocuments({}), processed_events: db.processed_events.countDocuments({})})'
  echo "== mongo registrations (sample)"
  docker exec p03-mongo mongosh p03_handshake --quiet --eval 'printjson(db.registrations.find().limit(5).toArray())'
  echo "== kafka: messages per topic (end offsets)"
  for t in application.created event.registration_created job.created; do
    printf "%s " "$t"
    docker exec p03-kafka /opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server p03-kafka:9092 --topic "$t" 2>&1 | tail -1
  done
  echo "== event-worker log (last 25)"
  $COMPOSE logs --no-log-prefix --tail 25 p03-event-worker 2>&1 | cut -c1-220
  echo "== publisher errors in application/event services (expect 0)"
  $COMPOSE logs --no-log-prefix --tail 2000 p03-application-service p03-event-service 2>&1 | grep -ci "could not\|traceback"
  echo "== docker ps"
  docker ps --format "table {{.Names}}\t{{.Status}}"
} > "$OUT" 2>&1
echo "done: results are in $OUT"
