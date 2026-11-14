#!/bin/sh
# JMeter load test against the Kubernetes deployment (100 / 200 / 300 / 400 / 500 users).
#   sh scripts/k8s_loadtest.sh sql      (label only names the result files)
#   sh scripts/k8s_loadtest.sh mongo
#   LEVELS="75:300:30" sh scripts/k8s_loadtest.sh sql   (only some levels; users-per-scenario:total:rampup)
# Results: k8s_loadtest_output.txt, loadtest/k8s_<label>_<n>.jtl, loadtest/report_k8s_<label>_<n>/
LABEL=${1:-sql}
OUT=k8s_loadtest_output.txt
{
  echo "== date / label"; date; echo "$LABEL"
  echo "== persistence in the cluster"
  kubectl -n p03 get cm p03-config -o jsonpath='{.data.PERSISTENCE}{"\n"}'
  echo "== expose services on localhost"
  sh scripts/k8s_expose.sh
  python scripts/smoke.py
  echo "== pods before"
  kubectl -n p03 get pods --no-headers | awk '{print $1, $2, $3, $4}'
  cd loadtest
  for n in ${LEVELS:-25:100:20 50:200:25 75:300:30 100:400:30 125:500:30}; do
    u=${n%%:*}; rest=${n#*:}; total=${rest%%:*}; ramp=${rest##*:}
    echo "== $total users ($LABEL)"
    rm -rf report_k8s_${LABEL}_$total k8s_${LABEL}_$total.jtl
    jmeter -n -t handshake.jmx -Jusers=$u -Jrampup=$ramp -Jloops=30 -l k8s_${LABEL}_$total.jtl -e -o report_k8s_${LABEL}_$total 2>&1 | grep -E "summary =" | tail -1
    echo "failures by request:"
    awk -F, 'NR>1 && $8=="false"{c[$3" "$4]++} END{for(k in c)print "  ",c[k],k}' k8s_${LABEL}_$total.jtl | sort -rn | head -8
    sleep 10
  done
  cd ..
  echo "== pods after (restarts matter)"
  kubectl -n p03 get pods --no-headers | awk '{print $1, $2, $3, "restarts="$4}'
  echo "== pool or thread errors in service logs (expect nothing)"
  for d in company-service student-service job-service application-service event-service; do
    printf "%s: " $d; kubectl -n p03 logs deploy/p03-$d --since=20m 2>&1 | grep -ci "QueuePool\|Traceback"
  done
  echo "== MySQL peak connections"
  kubectl -n p03 exec p03-mysql-0 -- sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "SHOW STATUS LIKE \"Max_used_connections\"" 2>/dev/null'
  echo "== throttling note: pod CPU limits in k8s/*.yaml are 500m per service"
} > "$OUT" 2>&1
echo "done: results are in $OUT"
