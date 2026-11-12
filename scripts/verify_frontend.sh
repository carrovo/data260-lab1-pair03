#!/bin/sh
# Builds and starts the whole Compose stack including the frontend gateway, then
# checks that every route reaches the right service. Results: verify_frontend_output.txt
#   sh scripts/verify_frontend.sh
OUT=verify_frontend_output.txt
G=http://localhost:9036
code() { printf "%-3s %-6s %s\n" "$(curl -s -o /dev/null -w '%{http_code}' -X "$1" "$G$2")" "$1" "$2"; }
{
  echo "== date"; date
  echo "== up"
  docker compose --env-file .env.compose up -d --build 2>&1 | tail -6
  sleep 45
  docker ps --filter name=p03-frontend --format "{{.Names}} {{.Status}}"
  echo "== gateway"
  code GET /healthz
  echo "== SPA pages (expect 200 and HTML)"
  code GET /
  code GET /jobs
  code GET /company/login
  curl -s $G/jobs | grep -o "<title>[^<]*</title>"
  echo "== student API through /gw (expect 200, 401 for protected)"
  code GET /gw/jobs
  code GET "/gw/jobs?keyword=data"
  code GET /gw/jobs/1
  code GET /gw/events
  code GET /gw/events/1
  code GET /gw/applications/me
  code GET /gw/registrations/me
  code GET /gw/auth/me
  code POST /gw/jobs/1/applications
  code POST /gw/events/1/registrations
  echo "== company API through /api (expect 401/403/422 = reached the service, not 404/502)"
  code GET /api/companies/me
  code GET /api/companies/jobs
  code GET /api/companies/events
  code GET /api/companies/jobs/1/applicants
  code GET /api/companies/students
  echo "== real login through the gateway"
  curl -s -o /dev/null -w "student login %{http_code}\n" -X POST $G/gw/auth/login -H 'Content-Type: application/json' -d '{"email":"nobody@example.com","password":"wrong-password"}'
  echo "== gateway log (errors)"
  docker logs p03-frontend 2>&1 | grep -i "error\|emerg\|502" | tail -5
  echo "== smoke on direct ports"
  python scripts/smoke.py
} > "$OUT" 2>&1
echo "done: results are in $OUT  (then open $G in your browser)"
