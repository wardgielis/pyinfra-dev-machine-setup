"""Homebrew, the shared tools, and the coding agents.

Homebrew is installed as the admin user and owned by the admin user. The agent
user can run the tools but cannot change them.

Never run brew as root here. Never upgrade a cask from this deploy: an upgrade
can restart the agent and kill a running session.
"""

import os

from pyinfra import host, logger
from pyinfra.facts.server import Command
from pyinfra.operations import files, server, brew

ADMIN_USER = host.data.admin_user

BREW_PREFIX = "/home/linuxbrew/.linuxbrew"
BREW_BIN = f"{BREW_PREFIX}/bin/brew"
BREW_ENV = {
    "HOMEBREW_NO_AUTO_UPDATE": "1",
    "HOMEBREW_NO_ENV_HINTS": "1",
    "HOMEBREW_NO_ASK": "1",
}

TOOLS = [
    "ripgrep",
    "jq",
    "yq",
    "gh",
    "mise",
    "uv",
    "node",
    # The formula is kubernetes-cli. The kubectl alias is not a fact key, so a
    # short name would look missing and reinstall on every run.
    "kubernetes-cli",
    "helm",
    "k9s",
    "restic",
    "btop",
    # Jira CLI for the agent. Its settings come from the agent's config file.
    "jira-cli",
]

# The opencode formula from Homebrew core conflicts with the v2 formula from the
# anomalyco tap: both ship an `opencode` binary. The laptop runs opencode-v2, so
# the server must run the same one.
# Plain name: the tap is added first, and a fully qualified name never matches
# the installed package list, which would reinstall on every run.
OPENCODE_FORMULA = "opencode-v2"


# ------------------------------------------------------------
# 1. The prefix, owned by the admin user
# Create it before the installer runs, so the installer never needs sudo.
# ------------------------------------------------------------
files.directory(
    name="Create the Homebrew prefix",
    path=BREW_PREFIX,
    user=ADMIN_USER,
    group=ADMIN_USER,
    mode="0755",
    _sudo=True,
)

files.directory(
    name="Create the Caskroom",
    path=f"{BREW_PREFIX}/Caskroom",
    user=ADMIN_USER,
    group=ADMIN_USER,
    mode="0755",
    _sudo=True,
)

# ------------------------------------------------------------
# 2. Install Homebrew when the binary is missing
# ------------------------------------------------------------
_brew_installed = host.get_fact(Command, command=f"test -x {BREW_BIN} && echo yes || true")

if not _brew_installed:
    server.shell(
        name="Install Homebrew as the admin user",
        commands=[
            "curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh -o /tmp/brew-install.sh",
            "NONINTERACTIVE=1 CI=1 /bin/bash /tmp/brew-install.sh",
        ],
        _env={"NONINTERACTIVE": "1", "CI": "1"},
        _sudo_user=ADMIN_USER,
    )

# ------------------------------------------------------------
# 3. Make brew reachable from a non-interactive SSH shell
# A wrapper, not a symlink: bin/brew derives its prefix from the path it is called
# by, so a symlink in /usr/local/bin breaks it.
# ------------------------------------------------------------
files.put(
    name="Install the brew wrapper",
    src="files/brew_wrapper",
    dest="/usr/local/bin/brew",
    mode="0755",
    _sudo=True,
)

files.put(
    name="Add brew to the login shell",
    src="files/homebrew_profile.sh",
    dest="/etc/profile.d/homebrew.sh",
    mode="0644",
    _sudo=True,
)

_analytics = host.get_fact(Command, command=f"{BREW_BIN} analytics state 2>/dev/null || true") or ""
if "enabled" in _analytics.lower():
    server.shell(
        name="Turn brew analytics off",
        commands=[f"{BREW_BIN} analytics off"],
        _sudo_user=ADMIN_USER,
    )

# ------------------------------------------------------------
# 4. Taps, tools, and the coding agents
# ------------------------------------------------------------
_tap = brew.tap(name="Tap anomalyco", src="anomalyco/tap")

server.shell(
    name="Trust the anomalyco tap",
    commands=["brew trust anomalyco/tap || true"],
    _env=BREW_ENV,
    _if=lambda: _tap.did_change(),
)

_core_opencode = host.get_fact(
    Command, command=f"{BREW_BIN} list --formula opencode 2>/dev/null || true"
) or ""

if _core_opencode.strip():
    # The old hand-started instance keeps running after the formula is removed,
    # so stop it before the binary disappears. The systemd unit replaces it.
    server.shell(
        name="Stop the hand-started opencode service",
        # The bracket keeps pkill from matching its own command line, which would
        # kill the shell that pyinfra is using.
        commands=["pkill -f '[o]pencode serve' || true"],
    )
    server.shell(
        name="Remove the Homebrew core opencode formula",
        commands=[f"{BREW_BIN} uninstall --formula opencode"],
        _env=BREW_ENV,
    )

brew.packages(
    name="Install the shared tools",
    packages=[*TOOLS, OPENCODE_FORMULA],
    _env=BREW_ENV,
)

_cask = brew.casks(
    name="Install Claude Code",
    casks=["claude-code"],
    _env=BREW_ENV,
)

# ------------------------------------------------------------
# 5. Exactly one opencode and one claude on PATH
# Two copies cause confusing version bugs.
# ------------------------------------------------------------
for _command in ("opencode", "claude"):
    _paths = host.get_fact(Command, command=f"which -a {_command} 2>/dev/null | sort -u || true") or ""
    _count = len([line for line in _paths.splitlines() if line.strip()])
    if _count > 1:
        logger.warning("More than one %s on PATH: %s", _command, _paths.replace("\n", " "))
    elif _count == 0:
        logger.warning("No %s on PATH for a non-interactive shell. Check the brew install.", _command)

_claude_version = host.get_fact(Command, command=f"{BREW_BIN} list --cask --versions claude-code 2>/dev/null || true") or ""
if _claude_version:
    logger.info("Claude Code installed: %s", " ".join(_claude_version.split()))
