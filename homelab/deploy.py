"""Deploy the briareus homelab host.

Run from this directory so relative paths resolve to the homelab tree:

    uv run pyinfra inventory.py deploy.py

Set PHASE to run one section, for example PHASE=base.
"""

import os
from pathlib import Path

from pyinfra import local

# Load homelab/.env into the environment so the task modules can read the secrets
# the same way the inventory does. A missing file is fine: scripts/ci.sh runs on a
# fresh clone.
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from inventory import read_env  # noqa: E402

for _key, _value in read_env(Path(__file__).resolve().parent / ".env").items():
    os.environ.setdefault(_key, _value)
from pyinfra.operations import python

# Section order matches the phase order in the plan.
SECTIONS = (
    "base",       # phase 2: apt, users, ssh, updates, power, swap, resolver, monitoring
    "shell",      # phase 3: fastfetch hook
    "homebrew",   # phase 4: brew, tools, coding agents
    "tailscale",  # phase 5: tailnet and serve
    "opencode",   # phase 6: service, config, Claude Code
    "sync",       # phase 6b: daily pull from git
    "backup",     # phase 6 and 10: restic
    "k3s",        # phase 7: v2
    "argocd",     # phase 8: v2
)

GROUPS = {
    "v1": ("base", "shell", "homebrew", "tailscale", "opencode", "sync", "backup"),
    "v2": ("k3s", "argocd", "backup"),
    "all": SECTIONS,
}

_phase = os.environ.get("PHASE", "v1").strip().lower()

if _phase in SECTIONS:
    _enabled = {_phase}
elif _phase in GROUPS:
    _enabled = set(GROUPS[_phase])
else:
    raise SystemExit(
        f"Unknown PHASE {_phase!r}. Use one of: {', '.join([*GROUPS, *SECTIONS])}."
    )

_active = [name for name in SECTIONS if name in _enabled]
print(f"--> homelab deploy: PHASE={_phase}, running: {', '.join(_active) or 'nothing'}")


# ============================================================
# SECTION 1: BASE SYSTEM (phase 2)
# ============================================================
if "base" in _enabled:
    local.include("tasks/base.py")


# ============================================================
# SECTION 2: INTERACTIVE SHELL (phase 3)
# ============================================================
if "shell" in _enabled:
    local.include("tasks/shell.py")


# ============================================================
# SECTION 3: HOMEBREW AND TOOLS (phase 4)
# ============================================================
if "homebrew" in _enabled:
    local.include("tasks/homebrew.py")


# ============================================================
# SECTION 4: TAILSCALE (phase 5)
# ============================================================
if "tailscale" in _enabled:
    local.include("tasks/tailscale.py")


# ============================================================
# SECTION 5: OPENCODE SERVER (phase 6)
# ============================================================
if "opencode" in _enabled:
    local.include("tasks/opencode.py")


# ============================================================
# SECTION 6: DAILY SYNC FROM GIT (phase 6b)
# ============================================================
if "sync" in _enabled:
    local.include("tasks/opencode_sync.py")


# ============================================================
# SECTION 7: BACKUPS (phase 6 and 10)
# ============================================================
if "backup" in _enabled:
    local.include("tasks/backup.py")


# ============================================================
# SECTION 8: K3S (phase 7, v2)
# ============================================================
if "k3s" in _enabled:
    local.include("tasks/k3s.py")


# ============================================================
# SECTION 9: ARGO CD (phase 8, v2)
# ============================================================
if "argocd" in _enabled:
    local.include("tasks/argocd.py")


# ============================================================
# SECTION 10: WHAT A HUMAN STILL HAS TO DO
# ============================================================
def _print_manual_steps() -> None:
    print(
        """
Manual steps that the deploy cannot do:
  1. As the agent user, run: opencode auth login
  2. As the agent user, run: claude auth login, then check claude auth status
  3. Point the laptop client at https://<tailnet name>:8443 with the password
     from homelab/.env.
  4. Fetch agent commits with git over SSH from briareus, review, then push.
"""
    )


if _enabled & {"opencode", "v1"} or _enabled == set(GROUPS["v1"]):
    python.call(name="Print the manual steps", function=_print_manual_steps)
