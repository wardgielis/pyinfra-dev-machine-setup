"""The OpenCode server, its config, and Claude Code.

Isolation comes first, because this agent runs unattended. The systemd unit, not
the permission policy, is the security boundary for shell commands.
"""

import io
import os
import subprocess
import sys
from pathlib import Path

from pyinfra import host, logger
from pyinfra.facts.server import Command
from pyinfra.operations import files, server, systemd
from pyinfra.operations.util import any_changed

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

import opencode_config  # noqa: E402

ADMIN_USER = host.data.admin_user
AGENT_USER = host.data.agent_user
LAN_SUBNET = host.data.lan_subnet
LAN_GATEWAY = host.data.lan_gateway

SKILLS_SRC = REPO / "opencode-config" / "skills"
SKILLS_DEST = "/opt/opencode-skills"
CONFIG_DIR = "/etc/opencode"
SECRETS_DIR = "/etc/opencode-secrets"

# Skills that must never reach the server. A denylist, not an allowlist: a new
# tracked skill then arrives without a plan edit.
DENIED_SKILLS = ["pycharm"]


def _gitignored_entries() -> list[str]:
    """Return top-level skill names that only exist on the laptop.

    The org skills are gitignored, so the git clone never holds them. The deploy
    copies from the laptop disk, so it must skip them by name.
    """
    result = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "--others", "--ignored", "--directory", "--exclude-standard"],
        capture_output=True,
        text=True,
        check=False,
    )
    prefix = "opencode-config/skills/"
    names = []
    for line in result.stdout.splitlines():
        entry = line.strip().removesuffix("/")
        if not entry.startswith(prefix):
            continue
        name = entry.removeprefix(prefix)
        # Nested entries are covered by their top-level folder.
        if "/" in name:
            continue
        names.append(name)
    return names


# ------------------------------------------------------------
# 1. Workspace
# ------------------------------------------------------------
files.directory(
    name="Create the agent workspace",
    path=f"/home/{AGENT_USER}/code",
    user=AGENT_USER,
    group=AGENT_USER,
    mode="0755",
    _sudo=True,
)


# ------------------------------------------------------------
# 2. Skills
# Root-owned copy. The agent cannot edit its own instructions.
# ------------------------------------------------------------
if SKILLS_SRC.is_dir():
    _ignored = _gitignored_entries()
    _ignored_dirs = [name for name in _ignored if (SKILLS_SRC / name).is_dir()]
    _ignored_files = [name for name in _ignored if not (SKILLS_SRC / name).is_dir()]
    files.sync(
        name="Sync the tracked skills",
        src=str(SKILLS_SRC),
        dest=SKILLS_DEST,
        delete=True,
        exclude=[*_ignored_files, ".DS_Store"],
        exclude_dir=[*DENIED_SKILLS, *_ignored_dirs],
        _sudo=True,
    )
    logger.info(
        "Skills synced to %s, skipped: %s",
        SKILLS_DEST,
        ", ".join([*DENIED_SKILLS, *_ignored]),
    )
else:
    logger.warning("No skills source at %s. Skipping the skill sync.", SKILLS_SRC)


# ------------------------------------------------------------
# 3. Config
# One template for both targets. Only the MCP block and the skills path differ.
# ------------------------------------------------------------
files.directory(
    name="Create the system config folder",
    path=CONFIG_DIR,
    mode="0755",
    _sudo=True,
)

_config = files.put(
    name="Render the server OpenCode config",
    src=io.StringIO(opencode_config.render("server")),
    dest=f"{CONFIG_DIR}/opencode.jsonc",
    mode="0644",
    _sudo=True,
)

_agents = files.put(
    name="Write the server AGENTS.md",
    src="files/opencode_agents.md",
    dest=f"{CONFIG_DIR}/AGENTS.md",
    mode="0644",
    _sudo=True,
)

# ------------------------------------------------------------
# 4. Secrets
# Systemd reads the file before it drops privileges. The agent can read its own
# environment, so only tokens that may be held by the agent go here.
# ------------------------------------------------------------
_secret_lines = [f"OPENCODE_PASSWORD={os.environ.get('OPENCODE_PASSWORD', '')}"]
if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
    _secret_lines.append(f"CLAUDE_CODE_OAUTH_TOKEN={os.environ['CLAUDE_CODE_OAUTH_TOKEN']}")

files.directory(
    name="Create the secrets folder",
    path=SECRETS_DIR,
    mode="0700",
    _sudo=True,
)

_secrets = files.put(
    name="Write the OpenCode environment file",
    src=io.StringIO("\n".join(_secret_lines) + "\n"),
    dest=f"{SECRETS_DIR}/opencode.env",
    mode="0600",
    _sudo=True,
)


# ------------------------------------------------------------
# 5. The service
# ------------------------------------------------------------
_unit = files.template(
    name="Install the opencode unit",
    src="files/opencode.service.j2",
    dest="/etc/systemd/system/opencode.service",
    mode="0644",
    agent_user=AGENT_USER,
    lan_subnet=LAN_SUBNET,
    lan_gateway=LAN_GATEWAY,
    _sudo=True,
)

systemd.service(
    name="Enable and start the opencode service",
    service="opencode",
    running=True,
    enabled=True,
    _sudo=True,
)

# A restart kills a running session, so only reload and restart when something
# changed. The deploy is a chosen time; the daily sync never restarts.
_changed = any_changed(_unit, _config, _agents, _secrets)

systemd.daemon_reload(
    name="Reload systemd after the opencode unit change",
    _if=_changed,
    _sudo=True,
)

systemd.service(
    name="Restart opencode after a config change",
    service="opencode",
    restarted=True,
    _if=_changed,
    _sudo=True,
)


# ------------------------------------------------------------
# 6. Remote access
# 443 belongs to Traefik in v2, so use 8443. The password stays on: the tailnet
# ACL protects the network, the password protects the app.
# ------------------------------------------------------------
_tailnet_up = bool(host.get_fact(Command, command="tailscale ip -4 2>/dev/null || true"))
_serve = host.get_fact(Command, command="tailscale serve status 2>/dev/null || true") or ""

if _tailnet_up and "8443" not in _serve:
    server.shell(
        name="Publish OpenCode on port 8443 over tailscale serve",
        commands=["tailscale serve --bg --https=8443 http://127.0.0.1:4096"],
    )
elif not _tailnet_up:
    logger.warning("Tailscale is not up. Skipping tailscale serve for OpenCode.")

if not os.environ.get("OPENCODE_PASSWORD"):
    logger.warning("OPENCODE_PASSWORD is empty. The server is reachable without a password.")
