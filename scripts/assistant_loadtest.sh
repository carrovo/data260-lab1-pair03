#!/bin/sh
# Assistant endpoint load test (Part 5): 5, 10, 20 and 50 concurrent users, p50/p95/p99 + error rate.
# Needs the stack running AND a model (Ollama) reachable by the assistant service, and the demo
# students seeded. Run it on the machine where the assistant answers (Xuanhua's laptop).
#   sh scripts/assistant_loadtest.sh <label>        (label only names the result files, e.g. local)
# Results: assistant_loadtest_output.txt, loadtest/assistant_<label>_<n>.jtl, summary in
# loadtest/summary_assistant_<label>.md
LABEL=${1:-local}
OUT=assistant_loadtest_output.txt
{
  echo "== date / label"; date; echo "$LABEL"
  echo "== smoke test before the load starts"
  python scripts/smoke.py
  cd loadtest
  for n in 5 10 20 50; do
    echo "== $n concurrent users"
    rm -f assistant_${LABEL}_$n.jtl
    jmeter -n -t assistant.jmx -Jusers=$n -Jrampup=5 -Jloops=3 -Jthink_ms=500 -l assistant_${LABEL}_$n.jtl 2>&1 | grep -E "summary =" | tail -1
    awk -F, 'NR>1 && $8=="false"{c[$3" "$4]++} END{for(k in c)print "  failures:",c[k],k}' assistant_${LABEL}_$n.jtl | sort -rn | head -5
    sleep 5
  done
  cd ..
  python3 loadtest/summarize.py assistant "$LABEL"
} > "$OUT" 2>&1
echo "done: results are in $OUT"
