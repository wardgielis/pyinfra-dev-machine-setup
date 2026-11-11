"""Tailscale: join the tailnet and let the admin user run tailscale serve.

The node uses a tagged auth key so the key does not expire. MagicDNS and HTTPS
certificates are enabled in the admin console before this runs.
"""

import io
import os

from pyinfra import host, logger
from pyinfra.facts.server import Command
from pyinfra.operations import apt, files, server

ADMIN_USER = host.data.admin_user
HOSTNAME = host.data.hostname
AUTHKEY = os.environ.get("TS_AUTHKEY", "")

# ------------------------------------------------------------
# 1. The official apt repository
# ------------------------------------------------------------
files.download(
    name="Add the Tailscale signing key",
    src="https://pkgs.tailscale.com/stable/debian/trixie.noarmor.gpg",
    dest="/usr/share/keyrings/tailscale-archive-keyring.gpg",
    mode="0644",
    _sudo=True,
)

files.put(
    name="Add the Tailscale apt repository",
    src=io.StringIO(
        "deb [signed-by=/usr/share/keyrings/tailscale-archive-keyring.gpg] "
        "https://pkgs.tailscale.com/stable/debian trixie main\n"
    ),
    dest="/etc/apt/sources.list.d/tailscale.list",
    mode="0644",
    _sudo=True,
)

apt.packages(
    name="Install Tailscale",
    packages=["tailscale"],
    update=True,
    cache_time=86400,
    _sudo=True,
)


# ------------------------------------------------------------
# 2. Join the tailnet
# Tailscale does not read its auth key from the environment, so write it to a
# root-only file, use file: and remove it after the join.
# `--accept-dns=false` keeps Tailscale out of the resolver.
# ------------------------------------------------------------
_tailnet_up = bool(host.get_fact(Command, command="tailscale ip -4 2>/dev/null || true"))

if not _tailnet_up and AUTHKEY:
    files.directory(
        name="Create /etc/tailscale",
        path="/etc/tailscale",
        mode="0700",
        _sudo=True,
    )
    files.put(
        name="Write the Tailscale auth key",
        src=io.StringIO(f"{AUTHKEY}\n"),
        dest="/etc/tailscale/authkey",
        mode="0600",
        _sudo=True,
    )
    _join = server.shell(
        name="Join the tailnet",
        commands=[
            f"tailscale up --auth-key=file:/etc/tailscale/authkey "
            f"--hostname={HOSTNAME} --accept-dns=false",
        ],
        _sudo=True,
    )
    files.file(
        name="Remove the Tailscale auth key",
        path="/etc/tailscale/authkey",
        present=False,
        _if=lambda: _join.did_change(),
        _sudo=True,
    )
elif not _tailnet_up:
    logger.warning("TS_AUTHKEY is empty and the node is not on the tailnet. Skipping the join.")


# ------------------------------------------------------------
# 3. Let the admin user run tailscale serve without sudo
# The operator setting is idempotent, so only write it when it is wrong.
# ------------------------------------------------------------
_prefs = host.get_fact(Command, command="tailscale debug prefs 2>/dev/null || true") or ""
if _prefs and f'"OperatorUser": "{ADMIN_USER}"' not in _prefs:
    server.shell(
        name="Allow the admin user to run tailscale serve",
        commands=[f"tailscale set --operator={ADMIN_USER}"],
        _sudo=True,
    )

if _tailnet_up and not os.environ.get("TAILNET_NAME"):
    logger.info("The node is on the tailnet. Put the name from `tailscale status` in TAILNET_NAME.")
