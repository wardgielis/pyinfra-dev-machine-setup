"""Daily sync of skills and config from git.

The clone is root-owned and lives inside /srv, which the OpenCode unit hides, so
the agent cannot edit its own instructions. The sync never touches the systemd
unit: a restart kills the running session, so the restart stays manual and only
happens in a deploy.
"""

from pyinfra import host
from pyinfra.facts.server import Command
from pyinfra.operations import files, server, systemd
from pyinfra.operations.util import any_changed

REPO_URL = "https://codeberg.org/wardgielis/pyinfra-dev-machine-setup.git"
CLONE = "/srv/opencode-src"

# ------------------------------------------------------------
# 1. Root-owned clone of the public repository
# Anonymous HTTPS: the repository is public, so no key and no secret.
# ------------------------------------------------------------
files.directory(
    name="Create /srv",
    path="/srv",
    mode="0755",
    _sudo=True,
)

_clone = host.get_fact(Command, command=f"test -d {CLONE}/.git && echo yes || true")

if not _clone:
    server.shell(
        name="Clone the homelab repository",
        commands=[f"git clone --quiet --branch main {REPO_URL} {CLONE}"],
        _sudo=True,
    )

_owner = host.get_fact(Command, command=f"stat -c %U {CLONE} 2>/dev/null || true") or ""
if _owner.strip() not in ("", "root"):
    server.shell(
        name="Make the clone root-owned",
        commands=[f"chown -R root:root {CLONE}"],
        _sudo=True,
    )

# ------------------------------------------------------------
# 2. The sync script and the pending-change notice
# ------------------------------------------------------------
files.put(
    name="Install the opencode-sync script",
    src="files/opencode-sync",
    dest="/usr/local/bin/opencode-sync",
    mode="0755",
    _sudo=True,
)

files.put(
    name="Install the pending-change notice",
    src="files/opencode_pending.sh",
    dest="/etc/profile.d/99-opencode-pending.sh",
    mode="0644",
    _sudo=True,
)

# ------------------------------------------------------------
# 3. The timer
# Daily at 04:10, and once after boot when the machine was off at 04:10.
# ------------------------------------------------------------
_sync_service = files.put(
    name="Install opencode-sync.service",
    src="files/opencode-sync.service",
    dest="/etc/systemd/system/opencode-sync.service",
    mode="0644",
    _sudo=True,
)

_sync_timer = files.put(
    name="Install opencode-sync.timer",
    src="files/opencode-sync.timer",
    dest="/etc/systemd/system/opencode-sync.timer",
    mode="0644",
    _sudo=True,
)

systemd.daemon_reload(
    name="Reload systemd after the sync unit change",
    _if=any_changed(_sync_service, _sync_timer),
    _sudo=True,
)

systemd.service(
    name="Enable the opencode-sync timer",
    service="opencode-sync.timer",
    running=True,
    enabled=True,
    _sudo=True,
)
