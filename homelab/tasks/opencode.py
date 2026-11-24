"""The OpenCode server, its config, and Claude Code.

Isolation comes first, because this agent runs unattended. The systemd unit, not
the permission policy, is the security boundary for shell commands.
"""

import io
import os
import string
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

# Paths that decide what the server renders. The sync on the server reads them from
# git, so the deploy must not run while they differ from origin/main.
RENDER_PATHS = ["files", "homelab/files", "scripts", "opencode-config"]


def _assert_pushed() -> None:
    """Stop the deploy when the server would render something different from git.

    The server config is written by opencode-sync from the main branch. A change
    that is only on this laptop would be missed or half applied, so refuse to run.
    Set ALLOW_UNPUSHED=1 to override, for example for a dry run of local work.
    """
    if os.environ.get("ALLOW_UNPUSHED") == "1":
        logger.warning("ALLOW_UNPUSHED=1: the server config may differ from this working tree.")
        return

    git = ["git", "-C", str(REPO)]
    subprocess.run([*git, "fetch", "--quiet", "origin", "main"], check=False)
    unpushed = subprocess.run(
        [*git, "diff", "--quiet", "origin/main", "HEAD", "--", *RENDER_PATHS], check=False
    ).returncode
    dirty = subprocess.run(
        [*git, "status", "--porcelain", "--", *RENDER_PATHS], capture_output=True, text=True, check=False
    ).stdout.strip()
    if unpushed or dirty:
        raise SystemExit(
            "The config files differ from origin/main. Commit and push them first, "
            "because the server renders its config from git. Details:\n" + (dirty or "unpushed commits")
        )


_assert_pushed()

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
    path=f"/home/{AGENT_USER}/dev",
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
        # The agent user must read the skills, so the folders and files stay world-readable.
        mode="644",
        dir_mode="755",
        _sudo=True,
    )
    logger.info(
        "Skills synced to %s, skipped: %s",
        SKILLS_DEST,
        ", ".join([*DENIED_SKILLS, *_ignored]),
    )
else:
    logger.warning("No skills source at %s. Skipping the skill sync.", SKILLS_SRC)
    _ignored_dirs = []

# The private skills exist only on the laptop disk, so git never holds them. Copy
# each one by itself, so the tracked sync above and the daily sync on the server
# never delete them. The list file tells the server sync which names to leave alone.
_private_skills = sorted(_ignored_dirs)

files.directory(
    name="Create the system config folder",
    path=CONFIG_DIR,
    mode="0755",
    _sudo=True,
)

files.put(
    name="Write the private skills list for the server sync",
    src=io.StringIO("".join(f"{name}/\n" for name in [*DENIED_SKILLS, *_private_skills])),
    dest=f"{CONFIG_DIR}/private-skills.list",
    mode="0644",
    _sudo=True,
)

for _skill in _private_skills:
    files.sync(
        name=f"Copy the private skill {_skill}",
        src=str(SKILLS_SRC / _skill),
        dest=f"{SKILLS_DEST}/{_skill}",
        delete=True,
        exclude=["*.pyc", ".DS_Store"],
        exclude_dir=["__pycache__"],
        mode="644",
        dir_mode="755",
        _sudo=True,
    )


# ------------------------------------------------------------
# 3. Config
# opencode-sync is the only writer of opencode.jsonc and AGENTS.md. It renders both
# from git main. The deploy runs it once, and stops earlier when the working tree
# is not pushed (see _assert_pushed).
# ------------------------------------------------------------
server.shell(
    name="Run opencode-sync to write the config from git",
    commands=["test -x /usr/local/bin/opencode-sync || { echo 'opencode-sync is missing, run PHASE=sync first' >&2; exit 1; }", "/usr/local/bin/opencode-sync"],
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

# MCP values, referenced from the server config as {env:NAME}. They sit here, not in
# the root-owned config file, which the agent can read. The list comes from
# scripts/opencode_config.py, and CI fails when the config names a variable that
# is missing from it.
for _mcp_var in opencode_config.SERVER_ENV_VARIABLES:
    _secret_lines.append(f"{_mcp_var}={os.environ.get(_mcp_var, '')}")

files.directory(
    name="Create the secrets folder",
    path=SECRETS_DIR,
    mode="0700",
    _sudo=True,
)

# The Jira CLI reads its settings from a file in the agent's home. The repo template
# holds only placeholders, so the values come from homelab/.env at deploy time.
_jira_template = (REPO / "files" / "jira_config").read_text(encoding="utf-8")
_jira_values = {key: os.environ.get(key, "") for key in ("JIRA_LOGIN", "JIRA_SERVER", "JIRA_PROJECT_KEY", "JIRA_BOARD_ID")}

files.directory(
    name="Create the agent Jira config folder",
    path=f"/home/{AGENT_USER}/.config/.jira",
    user=AGENT_USER,
    group=AGENT_USER,
    mode="0700",
    _sudo=True,
)

files.put(
    name="Write the agent Jira CLI config",
    src=io.StringIO(string.Template(_jira_template).safe_substitute(_jira_values)),
    dest=f"/home/{AGENT_USER}/.config/.jira/.config.yml",
    user=AGENT_USER,
    group=AGENT_USER,
    mode="0600",
    _sudo=True,
)

# The oc helper joins the server from an SSH or VS Code remote shell as the agent
# user. The agent already holds this password in its own environment, so a file in
# its home adds no new access.
files.put(
    name="Install the oc helper",
    src="files/oc",
    dest="/usr/local/bin/oc",
    mode="0755",
    _sudo=True,
)

files.put(
    name="Write the agent password file for oc",
    src=io.StringIO(os.environ.get("OPENCODE_PASSWORD", "") + "\n"),
    dest=f"/home/{AGENT_USER}/.config/opencode-password",
    user=AGENT_USER,
    group=AGENT_USER,
    mode="0600",
    _sudo=True,
)

# VS Code Remote-SSH to the agent user. The official OpenCode extension opens a terminal
# and types a plain "opencode". A plain opencode starts the agent user's own background
# service, which is a second server. This function makes a bare "opencode" join the shared
# server like the oc helper does. Anything with arguments (auth, mcp, run) runs unchanged.
# Debian's ~/.bashrc returns early for a non-interactive shell, so the OpenCode service
# and its tools never see the function.
_vscode_server = f"/home/{AGENT_USER}/.vscode-server"

files.block(
    name="Make a bare opencode join the shared server in the agent shell",
    path=f"/home/{AGENT_USER}/.bashrc",
    content=(
        "opencode() {\n"
        '    if [ "$#" -eq 0 ]; then\n'
        "        oc\n"
        "    else\n"
        '        command opencode "$@"\n'
        "    fi\n"
        "}\n"
    ),
    # No parentheses or other regex characters in the marker, or the block is appended on every run.
    marker="# {mark} OPENCODE SHARED SERVER MANAGED BY PYINFRA",
    present=True,
    _sudo=True,
    _sudo_user=AGENT_USER,
)

# The OpenChamber trial wrote these two files. Remove them.
for _leftover in (f"{_vscode_server}/server-env-setup", f"{_vscode_server}/data/Machine/settings.json"):
    files.file(
        name=f"Remove the OpenChamber trial file {_leftover}",
        path=_leftover,
        present=False,
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

# A restart kills a running session, so only restart when something changed. The
# deploy is a chosen time; the daily sync never restarts. Two reasons to restart:
# the unit or the secrets changed (pyinfra knows), or the sync staged a new config
# (it leaves a marker file). The first restart removes the marker, so the second
# check does not restart again.
# Accepted exception to the guard rule: a server.shell always reports a change, but
# its command only restarts when the marker exists.
_changed = any_changed(_unit, _secrets)

systemd.daemon_reload(
    name="Reload systemd after the opencode unit change",
    _if=_changed,
    _sudo=True,
)

server.shell(
    name="Restart opencode after a unit or secrets change",
    commands=["systemctl restart opencode", "rm -f /run/opencode-config-pending"],
    _if=_changed,
    _sudo=True,
)

server.shell(
    name="Restart opencode when the sync staged a config change",
    commands=[
        "if [ -e /run/opencode-config-pending ]; then "
        "systemctl restart opencode && rm -f /run/opencode-config-pending; fi"
    ],
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
