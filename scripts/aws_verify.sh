#!/bin/sh
# End-to-end evidence for the AWS deployment (Lab 2 parts 1.5 and 1.6). Result: aws_verify_output.txt
#   sh scripts/aws_verify.sh
OUT=aws_verify_output.txt
hide() { sed 's/[0-9]\{12\}/ACCOUNT/g; s/"access_token":"[^"]*"/"access_token":"<hidden>"/'; }
H=$(kubectl -n p03 get svc p03-frontend -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
G="http://$H:9036"
PW=${DEMO_PASSWORD:-Pair03Demo!2026}
{
  echo "== date"; date
  echo "== kubectl context"; kubectl config current-context | hide
  echo "== nodes"; kubectl get nodes -o wide | awk '{print $1,$2,$5,$6}' | hide
  echo "== namespace"; kubectl get ns | grep -E "NAME|p03"
  echo "== pods"; kubectl -n p03 get pods
  echo "== deployments"; kubectl -n p03 get deploy
  echo "== services"; kubectl -n p03 get svc
  echo "== public endpoint"; echo "$G"
  echo "== 1. gateway health (expect 200)"
  curl -s -o /dev/null -w "GET /healthz -> %{http_code}\n" "$G/healthz"
  echo "== 2. sign in as a seeded student (request and response, token hidden)"
  echo "POST $G/gw/auth/login   body: {\"email\":\"seed3.student.001@demo.p03.example.com\",\"password\":\"<demo password>\"}"
  RESP=$(curl -s -w "\nHTTP %{http_code}" -X POST "$G/gw/auth/login" -H 'Content-Type: application/json' \
    -d "{\"email\":\"seed3.student.001@demo.p03.example.com\",\"password\":\"$PW\"}")
  echo "$RESP" | cut -c1-300 | hide
  TOKEN=$(echo "$RESP" | head -1 | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])" 2>/dev/null)
  echo "== 3. search jobs with that token"
  echo "GET $G/gw/jobs?city=San%20Jose&limit=3"
  curl -s -w "\nHTTP %{http_code}\n" "$G/gw/jobs?city=San%20Jose&limit=3" -H "Authorization: Bearer $TOKEN" | cut -c1-600
  echo "== 4. Kafka flow through the public address (new student, apply, replace resume)"
  G="$G" sh scripts/check_kafka_flow.sh >/dev/null 2>&1
  sed -n '/== verdict/,$p' kafka_flow_output.txt
} > "$OUT" 2>&1
echo "done: results are in $OUT"
