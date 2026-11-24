"""VS Code on the laptop: the app, the extensions, the settings and the SSH host.

deploy.py includes this file, and it also runs alone:

    uv run pyinfra @local vscode_setup.py

Run it from the repo root, because pyinfra resolves file paths from the working
directory.

What it does:
- Installs the visual-studio-code cask.
- Installs the extensions in files/vscode_extensions.txt that are missing. It never
  removes an extension that you added by hand.
- Sets the user settings from files/vscode_settings.json. Only those keys are set.
  Everything else in the live file stays, such as the database connections that DBCode
  saves there. Comments in the live file are not kept.
- Keeps a managed block in ~/.ssh/config for the homelab agent host. The block names
  the Bitwarden SSH agent socket. A program that starts from the Dock does not read
  .zshenv, so without the socket VS Code could not find the SSH key.

VSCodium stays installed and is not touched here.
"""

import io
import json
import os
import pathlib
import re
import subprocess

from pyinfra.operations import brew, files, server

REPO = pathlib.Path(__file__).resolve().parent
EXTENSIONS_FILE = REPO / "files" / "vscode_extensions.txt"
SETTINGS_FILE = REPO / "files" / "vscode_settings.json"

CODE_CLI_CANDIDATES = ["/opt/homebrew/bin/code", "/usr/local/bin/code"]
SETTINGS_DEST = os.path.expanduser("~/Library/Application Support/Code/User/settings.json")
SSH_CONFIG = os.path.expanduser("~/.ssh/config")
BITWARDEN_SOCKET = "~/Library/Containers/com.bitwarden.desktop/Data/.bitwarden-ssh-agent.sock"

HOMELAB_SSH_BLOCK = f"""\
# The agent user on the homelab server, for VS Code Remote-SSH and plain ssh.
# IdentityAgent names the Bitwarden socket, so a program that starts from the Dock
# can use the key. The server is only reachable over the tailnet.
Host briareus-agent
    HostName briareus.dove-cobia.ts.net
    User agent
    IdentityFile ~/.ssh/briareus.pub
    IdentitiesOnly yes
    IdentityAgent {BITWARDEN_SOCKET}
    ForwardAgent no
    ServerAliveInterval 30
    ServerAliveCountMax 4
"""


def read_extension_ids() -> list[str]:
    """Read the extension ids from the list file.

    Returns:
        One id per line, without comments and blank lines.
    """
    ids = []
    for line in EXTENSIONS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            ids.append(line)
    return ids


def merged_settings() -> str:
    """Build the settings file text: the live file with the managed keys set.

    VS Code and some extensions (DBCode saves its connections here) write into the
    user settings file, so replacing the whole file would delete their data. This
    keeps every key that the repo file does not name and sets the ones it does.

    Returns:
        The settings text, ending with a newline.

    Raises:
        SystemExit: When the live file exists but cannot be read as JSON. Nothing is
            written then, so a file with a typo is never destroyed.
    """

    def parse(text: str) -> dict:
        # Only full-line comments are removed, so a URL inside a string stays intact.
        return json.loads(re.sub(r"(?m)^\s*//.*$", "", text))

    managed = parse(SETTINGS_FILE.read_text(encoding="utf-8"))
    live: dict = {}
    if os.path.exists(SETTINGS_DEST):
        text = pathlib.Path(SETTINGS_DEST).read_text(encoding="utf-8")
        if text.strip():
            try:
                live = parse(text)
            except ValueError as error:
                raise SystemExit(f"{SETTINGS_DEST} is not valid JSON ({error}). Fix it, then run again.") from error
    live.update(managed)
    return json.dumps(live, indent=2, ensure_ascii=False) + "\n"


def find_code_cli() -> str | None:
    """Find the code command that the cask installs.

    Returns:
        The path of the command, or None when VS Code is not installed yet.
    """
    for candidate in CODE_CLI_CANDIDATES:
        if os.path.exists(candidate):
            return candidate
    return None


def missing_extensions() -> list[str]:
    """List the wanted extensions that are not installed yet.

    pyinfra calls this when the operation runs, after the cask is installed, so a
    first run on a new machine works too.

    Returns:
        The missing extension ids. Empty when the code command does not exist yet.
    """
    code = find_code_cli()
    if code is None:
        return []
    result = subprocess.run([code, "--list-extensions"], capture_output=True, text=True, check=False)
    installed = {line.strip().lower() for line in result.stdout.splitlines()}
    return [ext for ext in read_extension_ids() if ext.lower() not in installed]


def install_script() -> str:
    """Build one shell script that installs every wanted extension that is missing.

    pyinfra builds the command before it runs the cask install, so the script
    cannot depend on the state at that moment. It lists all wanted extensions and
    skips the installed ones when it runs.

    Returns:
        The shell script.
    """
    wanted = " ".join(f"'{ext}'" for ext in read_extension_ids())
    return (
        "code=$(command -v code || ls /opt/homebrew/bin/code /usr/local/bin/code 2>/dev/null | head -1); "
        '[ -n "$code" ] || { echo "VS Code command not found" >&2; exit 1; }; '
        'installed=$("$code" --list-extensions | tr "[:upper:]" "[:lower:]"); '
        f"for ext in {wanted}; do "
        'echo "$installed" | grep -qxi "$ext" || "$code" --install-extension "$ext" || exit 1; '
        "done"
    )


# ------------------------------------------------------------
# 1. The app
# ------------------------------------------------------------
brew.casks(
    name="Install VS Code",
    casks=["visual-studio-code"],
)

# ------------------------------------------------------------
# 2. The extensions
# The check runs when the operation runs, not when the file loads, so it sees the
# result of the cask install above. A second run finds nothing missing and does
# nothing.
# ------------------------------------------------------------
server.shell(
    name="Install the missing VS Code extensions",
    commands=[install_script()],
    # Evaluated when the operation runs, after the cask install, so a new machine works.
    _if=lambda: bool(missing_extensions()),
)

# ------------------------------------------------------------
# 3. The settings
# ------------------------------------------------------------
files.directory(
    name="Ensure the VS Code user folder exists",
    path=os.path.dirname(SETTINGS_DEST),
    present=True,
)

files.put(
    name="Set the managed VS Code settings and keep the rest",
    src=io.StringIO(merged_settings()),
    dest=SETTINGS_DEST,
)

# ------------------------------------------------------------
# 4. The SSH host for the homelab
# A marked block, so the rest of ~/.ssh/config stays yours.
# ------------------------------------------------------------
files.directory(
    name="Ensure ~/.ssh exists",
    path=os.path.expanduser("~/.ssh"),
    present=True,
    mode="0700",
)

files.block(
    name="Manage the homelab host in ~/.ssh/config",
    path=SSH_CONFIG,
    content=HOMELAB_SSH_BLOCK,
    # No parentheses or other regex characters in the marker: the operation reads it as a
    # pattern, and a marker that does not match makes it append a new block on every run.
    marker="# {mark} HOMELAB HOST MANAGED BY PYINFRA",
    present=True,
)
