#!/usr/bin/env bash
# Pair 03: Kafka failure demos against the running Compose stack.
#
#   bash scripts/kafka_demos.sh duplicate   same event twice  -> processed once
#   bash scripts/kafka_demos.sh restart     worker down, then back, then replay
#   bash scripts/kafka_demos.sh poison      bad messages      -> job.created.dlq
#   bash scripts/kafka_demos.sh all         the three, in a safe order
#
# Needs: docker compose stack up (p03-kafka, p03-mongo, p03-job-index-worker).
# Writes only demo documents (job ids 9100000+, 9200000+ and 9003) into the p03 Mongo database.
set -u

KAFKA=p03-kafka
MONGO=p03-mongo
WORKER=p03-job-index-worker
BOOT=p03-kafka:9092
TOPIC=job.created
KBIN=/opt/kafka/bin

say() { printf '\n=== %s\n' "$*"; }

uuid() { uuidgen | tr 'A-Z' 'a-z'; }

event() {  # event <event_id> <trace_id> <job_id> <title>
  printf '{"event_id":"%s","event_type":"job.created","trace_id":"%s","occurred_at":"%s","producer":"job","payload":{"job_id":%s,"company_id":51,"title":"%s"}}' \
    "$1" "$2" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$3" "$4"
}

send() {  # send <line>... ; one Kafka message per argument
  printf '%s\n' "$@" | docker exec -i "$KAFKA" \
    "$KBIN/kafka-console-producer.sh" --bootstrap-server "$BOOT" --topic "$TOPIC" 2>/dev/null
}

mongo() { docker exec "$MONGO" mongosh p03_handshake --quiet --eval "$1"; }

logs() { docker logs "$WORKER" --tail "${1:-8}" 2>&1; }

# wait_until <seconds> <command...>: poll until the command succeeds.
# A restarted consumer can wait up to ~45 s for Kafka to drop the old member
# of its group (session timeout), so the demos poll instead of sleeping once.
wait_until() {
  local limit=$1; shift
  local i=0
  while [ "$i" -lt "$limit" ]; do
    "$@" >/dev/null 2>&1 && return 0
    sleep 3; i=$((i + 3))
  done
  return 1
}
event_processed() { [ "$(mongo "db.processed_events.countDocuments({event_id:'$1'})")" = "1" ]; }
now_utc() { date -u +%Y-%m-%dT%H:%M:%SZ; }
new_logs() { docker logs "$WORKER" --since "$SINCE" 2>&1; }   # needs SINCE set first
worker_skipped_dup() { new_logs | grep -q "duplicate skipped"; }
two_dead_letters() { [ "$(new_logs | grep -c 'dead-lettered')" -ge 2 ]; }

counts() {  # counts <job_id> <event_id>
  echo "job_index docs for job $1:        $(mongo "db.job_index.countDocuments({_id:'$1'})")"
  [ -n "${2:-}" ] && echo "processed_events for this event: $(mongo "db.processed_events.countDocuments({event_id:'$2'})")"
}

demo_duplicate() {
  say "DEMO 1: duplicate delivery (same event_id sent twice)"
  local id trace job; id=$(uuid); trace=demo-duplicate-1; job=$((9100000 + RANDOM))
  local msg; msg=$(event "$id" "$trace" "$job" "Duplicate Demo Job")
  echo "event_id=$id  job_id=$job"
  send "$msg" "$msg"
  sleep 6
  echo "--- worker log"; logs 6 | grep -E "$id|duplicate|processed" | tail -4
  echo "--- database"; counts "$job" "$id"
  echo "EXPECTED: one 'processed', one 'duplicate skipped', both counts = 1"
}

demo_restart() {
  say "DEMO 2: worker down, event sent, worker restarted (no loss), then replay"
  local id job; id=$(uuid); job=$((9200000 + RANDOM))
  docker stop "$WORKER" >/dev/null && echo "worker stopped"
  send "$(event "$id" demo-restart-1 "$job" "Restart Demo Job")"
  sleep 2
  echo "while the worker is down: job_index docs for $job = $(mongo "db.job_index.countDocuments({_id:'$job'})")  (expected 0)"
  docker start "$WORKER" >/dev/null && echo "worker started (can take up to ~45 s to rejoin the group)"
  wait_until 90 event_processed "$id" || echo "WARNING: not processed after 90 s, check: docker logs $WORKER"
  echo "--- after restart"; counts "$job" "$id"
  echo "EXPECTED: both counts = 1 (event waited in Kafka; offset was not committed before the write)"

  say "DEMO 2b: replay from the start (offsets reset to earliest)"
  local before after
  before=$(mongo "db.processed_events.countDocuments({consumer:'job-index-worker'})")
  docker stop "$WORKER" >/dev/null
  echo "resetting offsets (Kafka needs the group to be empty first, retrying up to ~60 s)"
  local out="" try
  for try in 1 2 3 4 5 6 7 8 9 10; do
    out=$(docker exec "$KAFKA" "$KBIN/kafka-consumer-groups.sh" --bootstrap-server "$BOOT" \
      --group job-index-worker --topic "$TOPIC" --reset-offsets --to-earliest --execute 2>&1)
    echo "$out" | grep -q "Error" || break
    sleep 6
  done
  echo "$out" | tail -4
  if echo "$out" | grep -q "Error"; then
    echo "WARNING: offsets were NOT reset, so this replay did not happen"
  fi
  SINCE=$(now_utc)
  docker start "$WORKER" >/dev/null
  wait_until 90 worker_skipped_dup || echo "WARNING: no duplicate seen after 90 s"
  sleep 3
  after=$(mongo "db.processed_events.countDocuments({consumer:'job-index-worker'})")
  echo "processed_events before replay: $before   after replay: $after"
  echo "--- worker log since the restart"; new_logs | tail -8
  echo "EXPECTED: many 'duplicate skipped' lines and before = after"
}

demo_poison() {
  say "DEMO 3: poison messages go to $TOPIC.dlq"
  local trace=demo-poison-1
  local bad_json='this is not json'
  local missing; missing=$(printf '{"event_id":"%s","event_type":"job.created","trace_id":"%s","occurred_at":"%s","producer":"job","payload":{"job_id":9003}}' \
    "$(uuid)" "$trace" "$(date -u +%Y-%m-%dT%H:%M:%SZ)")
  SINCE=$(now_utc)
  send "$bad_json" "$missing"
  wait_until 90 two_dead_letters || echo "WARNING: fewer than 2 dead letters after 90 s"
  echo "--- worker log"; new_logs | grep -E "poison|dead-lettered"
  echo "--- messages now in $TOPIC.dlq"
  docker exec "$KAFKA" "$KBIN/kafka-console-consumer.sh" --bootstrap-server "$BOOT" \
    --topic "$TOPIC.dlq" --from-beginning --timeout-ms 8000 2>/dev/null
  echo "--- main topic keeps flowing: job 9003 must NOT be indexed"
  echo "job_index docs for 9003 = $(mongo "db.job_index.countDocuments({_id:'9003'})")  (expected 0)"
  echo "EXPECTED: two DLQ entries with an 'error' and 'attempts' field; worker still running"
}

case "${1:-all}" in
  duplicate) demo_duplicate ;;
  restart)   demo_restart ;;
  poison)    demo_poison ;;
  all)       demo_duplicate; demo_restart; demo_poison ;;
  *) echo "usage: $0 duplicate|restart|poison|all" >&2; exit 2 ;;
esac
