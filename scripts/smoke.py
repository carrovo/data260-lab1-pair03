"""Smoke test: every ready service must answer GET /health.

Usage:  python scripts/smoke.py [host]
Run it while the stack is up (Docker Compose or port-forward).
Exit code 0 means every ready service is healthy.
"""

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
services = json.loads((ROOT / "contracts" / "services.json").read_text())

failures = 0
for svc in services["services"]:
    if not svc["health"]:
        continue
    if svc["status"] != "ready":
        print(f"SKIP  {svc['name']:<12} {svc['port']}  ({svc['status']})")
        continue
    url = f"http://{host}:{svc['port']}/health"
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            body = json.loads(response.read())
        ok = body.get("status") == "ok" and body.get("service") == svc["name"]
    except Exception as exc:  # noqa: BLE001 - report any failure
        print(f"FAIL  {svc['name']:<12} {svc['port']}  {exc}")
        failures += 1
        continue
    print(f"{'OK  ' if ok else 'FAIL'}  {svc['name']:<12} {svc['port']}")
    failures += 0 if ok else 1

sys.exit(1 if failures else 0)
