"""Check an Airflow agent user without side effects.

Usage: python3 -I scripts/airflow_agent_check.py DEV|PROD URL
Example: python3 -I scripts/airflow_agent_check.py DEV https://airflow.arise.dryrun.link

Reads AIRFLOW_<ENV>_USERNAME and AIRFLOW_<ENV>_PASSWORD from homelab/.env. The token and
the password are never printed. Every write check uses a DAG id that does not exist, so a
permitted call ends in 404 and a refused call ends in 403. Nothing is created or deleted.
Run it after a redeploy or a database restore to see that the user and its role still work.
"""

import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

env_name, base = sys.argv[1].upper(), sys.argv[2].rstrip("/")
values = {}
for line in open(pathlib.Path(__file__).resolve().parents[1] / "homelab" / ".env", encoding="utf-8"):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        key, value = line.split("=", 1)
        values[key] = value
user, password = values[f"AIRFLOW_{env_name}_USERNAME"], values[f"AIRFLOW_{env_name}_PASSWORD"]
MISSING = "opencode_permission_check_does_not_exist"


def call(method, path, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(base + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


status, raw = call("POST", "/auth/token", {"username": user, "password": password})
token = json.loads(raw).get("access_token") if status in (200, 201) else None
print(f"token exchange: HTTP {status}", "-> token received" if token else "-> NO TOKEN")
if not token:
    sys.exit(1)

checks = [
    ("read DAG list", "GET", "/api/v2/dags?limit=1", None, {200}),
    ("start a run (missing DAG)", "POST", f"/api/v2/dags/{MISSING}/dagRuns", {"logical_date": None}, {404}),
    ("pause a DAG (missing DAG)", "PATCH", f"/api/v2/dags/{MISSING}?update_mask=is_paused", {"is_paused": True}, {404}),
    ("delete a DAG (missing DAG)", "DELETE", f"/api/v2/dags/{MISSING}", None, {403}),
    ("delete a run (missing DAG)", "DELETE", f"/api/v2/dags/{MISSING}/dagRuns/x", None, {403}),
    ("read connections", "GET", "/api/v2/connections?limit=1", None, {403}),
    ("read variables", "GET", "/api/v2/variables?limit=1", None, {403}),
]
failed = 0
for label, method, path, body, expected in checks:
    status, raw = call(method, path, body, token)
    ok = status in expected
    failed += 0 if ok else 1
    print(f"{'ok  ' if ok else 'FAIL'} {label:30} HTTP {status} (want {'/'.join(map(str, expected))})")
print("RESULT:", "all checks passed" if not failed else f"{failed} check(s) failed")
sys.exit(1 if failed else 0)
