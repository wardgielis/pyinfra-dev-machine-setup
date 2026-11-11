"""Restic backups to Backblaze B2.

The backup runs as root and reads its credentials from a root-only file, so the
agent cannot read them and cannot send a false ping. The repository is offsite, so
it survives theft, fire and a dead NUC.
"""

import io
import os

from pyinfra import host, logger
from pyinfra.operations import apt, files, systemd
from pyinfra.operations.util import any_changed

REPOSITORY = os.environ.get("RESTIC_REPOSITORY", "")
PASSWORD = os.environ.get("RESTIC_PASSWORD", "")

# v1 paths. Phase 10 adds /srv/data, /srv/k3s and the k3s token.
PATHS = [
    "/home/agent/code",
    "/home/agent/.local/share/opencode",
    "/etc/opencode",
    "/etc/opencode-secrets",
]

# ------------------------------------------------------------
# 1. Package and units
# ------------------------------------------------------------
apt.packages(
    name="Install restic",
    packages=["restic"],
    _sudo=True,
)

files.directory(
    name="Create /etc/restic",
    path="/etc/restic",
    mode="0700",
    _sudo=True,
)

files.put(
    name="Write the restic environment",
    src=io.StringIO(
        f"RESTIC_REPOSITORY={REPOSITORY}\n"
        f"RESTIC_PASSWORD={PASSWORD}\n"
        f"AWS_ACCESS_KEY_ID={os.environ.get('AWS_ACCESS_KEY_ID', '')}\n"
        f"AWS_SECRET_ACCESS_KEY={os.environ.get('AWS_SECRET_ACCESS_KEY', '')}\n"
    ),
    dest="/etc/restic/restic.env",
    mode="0600",
    _sudo=True,
)

files.put(
    name="Install the backup script",
    src="files/homelab-restic-backup",
    dest="/usr/local/bin/homelab-restic-backup",
    mode="0700",
    _sudo=True,
)

_restic_service = files.put(
    name="Install restic-backup.service",
    src="files/restic-backup.service",
    dest="/etc/systemd/system/restic-backup.service",
    mode="0644",
    _sudo=True,
)

_restic_timer = files.put(
    name="Install restic-backup.timer",
    src="files/restic-backup.timer",
    dest="/etc/systemd/system/restic-backup.timer",
    mode="0644",
    _sudo=True,
)

systemd.daemon_reload(
    name="Reload systemd after the backup unit change",
    _if=any_changed(_restic_service, _restic_timer),
    _sudo=True,
)

# ------------------------------------------------------------
# 2. Enable the timer only when the repository is configured
# An enabled timer without credentials fails every night and mails once per run.
# ------------------------------------------------------------
if REPOSITORY and PASSWORD:
    systemd.service(
        name="Enable the restic timer",
        service="restic-backup.timer",
        running=True,
        enabled=True,
        _sudo=True,
    )
else:
    systemd.service(
        name="Keep the restic timer off until credentials exist",
        service="restic-backup.timer",
        running=False,
        enabled=False,
        _sudo=True,
    )
    logger.warning(
        "RESTIC_REPOSITORY or RESTIC_PASSWORD is empty. Units installed, timer left off."
    )

logger.info("Restic backs up: %s", ", ".join(PATHS))
