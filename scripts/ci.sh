#!/usr/bin/env bash
# Run the checks that are worth running before a push.
#
# There is no hosted CI: a pre-commit hook covers the real risk, a commit on the
# laptop, and this script covers the rest by hand.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> gitleaks: scan the full history"
if command -v gitleaks >/dev/null 2>&1; then
    gitleaks detect --no-banner --redact
else
    echo "gitleaks is not installed, skipping the history scan" >&2
fi

echo "==> python: compile every module"
python3 -m compileall -q -x '(\.venv|node_modules)' . >/dev/null

echo "==> opencode config: render both targets and compare"
python3 scripts/opencode_config.py --check-drift

echo "==> homelab: resolve the inventory"
(
    cd homelab
    uv run pyinfra inventory.py debug-inventory >/dev/null
)

echo "OK"
