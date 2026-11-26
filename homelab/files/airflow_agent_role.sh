# Create the Airflow role PipelineStarter. It lets the OpenCode agent read everything a
# Viewer reads and start pipeline runs, and it has no delete right anywhere.
#
# Run it on the Airflow VM as the development user, once per environment:
#   ssh development@tools-<env>-airflow.hosts.naturalis.io 'bash -s' < homelab/files/airflow_agent_role.sh
# It is safe to run again. Run it again after a restore of the Airflow database from an
# older dump, because a restore brings back the roles of that day.
set -eu
KX="microk8s kubectl -n airflow exec deploy/airflow-api-server --"
ROLE=PipelineStarter

echo "== create the role (a second run only reports that it exists) =="
$KX airflow roles create "$ROLE" 2>&1 | tail -2

echo "== read the Viewer permissions =="
$KX airflow roles list -p -o json 2>/dev/null > /tmp/roles.$$.json

# One add-perms command per action. The resources of one action share that action,
# so no (action, resource) pair is invented.
python3 - "$ROLE" "/tmp/roles.$$.json" > /tmp/plan.$$.sh <<'PY'
import collections, json, shlex, sys
role, path = sys.argv[1], sys.argv[2]
by = collections.defaultdict(set)
for row in json.load(open(path)):
    if row["name"] != "Viewer":
        continue
    for action in row["action"].split(","):
        by[action.strip()].add(row["resource"])
for action in sorted(by):
    resources = " ".join(shlex.quote(r) for r in sorted(by[action]))
    print(f'echo "   {action}: {len(by[action])} resources"')
    print(f"$KX airflow roles add-perms {shlex.quote(role)} -a {shlex.quote(action)} -r {resources} 2>&1 | tail -1")
PY
rm -f /tmp/roles.$$.json

echo "== copy the Viewer permissions to the role =="
. /tmp/plan.$$.sh
rm -f /tmp/plan.$$.sh

echo "== the two extra permissions that start a run =="
# Airflow checks both: can_create on DAG Runs, and can_edit on the DAG (a non-GET call on a
# sub entity needs EDIT on the DAG). Neither one includes any delete right.
$KX airflow roles add-perms "$ROLE" -a can_create -r "DAG Runs" 2>&1 | tail -1
$KX airflow roles add-perms "$ROLE" -a can_edit -r "DAGs" 2>&1 | tail -1
