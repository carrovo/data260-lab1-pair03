#!/bin/sh
# Lab 2 Part 2: the three Kafka failure cases, run against the Kubernetes stack (ns p03).
# Uses the job-index-worker (topic p03.job.created). Needs the stack running
# (scripts/verify_k8s.sh passes first). Result: kafka_failures_output.txt
#   sh scripts/kafka_failure_demo.sh
OUT=kafka_failures_output.txt
NS="kubectl -n p03"
W=deploy/p03-job-index-worker
T="python -m backend.workers.demo_tools"
RUN=$(date +%s)
pod() { $NS get pod -l app.kubernetes.io/name=p03-job-index-worker --no-headers | awk '$2=="1/1" && $3=="Running" {print $1}' | head -1; }
settle() { for i in $(seq 1 30); do [ "$($NS get pod -l app.kubernetes.io/name=p03-job-index-worker --no-headers | wc -l | tr -d ' ')" = "1" ] && break; sleep 3; done; sleep 8; }
{
echo "== date"; date
echo "== turn on the demo hooks (env DEMO_FAILURE_HOOKS=1, DEMO_SLOW_SECONDS=25) and wait for the new worker pod"
$NS set env $W DEMO_FAILURE_HOOKS=1 DEMO_SLOW_SECONDS=25 >/dev/null
$NS rollout status $W --timeout=120s
settle

echo
echo "################ CASE 1: the same event published twice with the same key"
J1="demo-dup-$RUN"
EID=$($NS exec $(pod) -- $T publish "$J1" "DEMO duplicate $RUN" --twice | tail -1)
echo "published event_id=$EID twice, key=$J1"
sleep 10
$NS exec deploy/p03-event-worker -- $T count "$J1" "$EID"
echo "-- worker log for this event:"
$NS logs $(pod) --tail=40 | grep "$EID" | cut -c1-170
echo "EXPECT: 1 job_index doc, 1 processed_events record, one 'processed' line and one 'duplicate skipped' line"

echo
echo "################ CASE 2: kill the worker while it is processing"
J2="demo-kill-$RUN"
EID2=$($NS exec $(pod) -- $T publish "$J2" "DEMO-SLOW kill $RUN" | tail -1)
echo "published event_id=$EID2 (the handler sleeps 25 s before its database write)"
P=$(pod)
for i in 1 2 3 4 5 6 7 8 9 10; do
  $NS logs $P --tail=30 2>/dev/null | grep -q "slow handler started event_id=$EID2" && break
  sleep 2
done
echo "-- worker has started the event; now killing $P"
$NS delete pod $P --grace-period=0 --force 2>&1 | tail -1
echo "-- right after the kill (nothing was written yet):"
$NS exec deploy/p03-event-worker -- $T count "$J2" "$EID2" 2>&1 | tail -1
settle_new() { sleep 3; }
settle_new
echo "-- waiting for the replacement pod to pick the event up again (up to 150 s)"
for i in $(seq 1 30); do
  $NS logs $(pod) --tail=40 2>/dev/null | grep -q "processed event_id=$EID2" && break
  sleep 5
done
$NS logs $(pod) --tail=40 | grep "$EID2" | cut -c1-170
echo "-- after the restart:"
$NS exec deploy/p03-event-worker -- $T count "$J2" "$EID2"
echo "-- consumer group offsets (LAG 0 means the offset was committed after the write):"
$NS exec p03-kafka-0 -- /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group job-index-worker 2>&1 | grep -E "GROUP|p03.job.created "
echo "EXPECT: 0 docs right after the kill, 1 doc after the restart: the event was not lost, it was processed again (at-least-once)"

echo
echo "################ CASE 3: poison message, bounded retries, dead-letter topic"
echo "-- (a) a message that is not valid JSON"
$NS exec $(pod) -- $T raw "not-json {{{ poison $RUN"
echo "-- (b) a valid event whose handler always fails (3 attempts, then dead letter)"
$NS exec $(pod) -- $T publish "demo-fail-$RUN" "DEMO-FAIL poison $RUN" >/dev/null
echo "-- (c) a good event published right after both"
J3="demo-after-$RUN"
EID3=$($NS exec $(pod) -- $T publish "$J3" "DEMO after poison $RUN" | tail -1)
sleep 15
echo "-- worker log:"
$NS logs $(pod) --tail=60 | grep -E "poison|attempt|dead-lettered|$EID3" | grep "$RUN\|dead-lettered\|attempt\|$EID3" | cut -c1-190 | tail -12
echo "-- dead-letter topic p03.job.created.dlq:"
$NS exec $(pod) -- $T dlq "$RUN"
echo "-- the good event after the poison messages:"
$NS exec deploy/p03-event-worker -- $T count "$J3" "$EID3"
echo "EXPECT: invalid JSON -> dead letter (attempts 0); DEMO-FAIL -> 3 attempts then dead letter; the good event is processed (1/1)"

echo
echo "== turn the demo hooks off again"
$NS set env $W DEMO_FAILURE_HOOKS- DEMO_SLOW_SECONDS- >/dev/null
$NS rollout status $W --timeout=120s
} > "$OUT" 2>&1
echo "done: results are in $OUT"
