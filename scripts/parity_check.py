"""Compare the OpenCode setup on the laptop with the one on the server.

It checks four things and prints every difference:

    skills    the folder names in the laptop skills folder and on the server
    mcp       the MCP server names in the rendered configs
    config    the hash of the server config against a fresh render from this tree
    agents    the hash of the shared AGENTS core against the server AGENTS.md start

The server is read over SSH with the same key as the deploy. No secret is read or
printed. Exit code 0 means no difference, 1 means at least one.

Usage:
    python3 scripts/parity_check.py [--host me@briareus.dove-cobia.ts.net]
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import opencode_config  # noqa: E402

DEFAULT_HOST = "me@briareus.dove-cobia.ts.net"
LAPTOP_ONLY_SKILLS = {"pycharm"}
IGNORED_SKILL_NAMES = {".DS_Store"}
COMMENT_LINE = re.compile(r"^\s*//.*$", re.MULTILINE)


def ssh(host: str, command: str) -> str:
    """Run a command on the server and return its output.

    Args:
        host: The user and host for ssh.
        command: The shell command to run.

    Returns:
        Standard output of the command.
    """
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", host, command],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"ssh failed: {result.stderr.strip() or 'no output'}")
    return result.stdout


def sha(text: str) -> str:
    """Return a short SHA-256 of a text.

    Args:
        text: The text to hash.

    Returns:
        The first 12 hex characters.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def check_skills(host: str) -> list[str]:
    """Compare the skill folder names.

    Args:
        host: The user and host for ssh.

    Returns:
        One line per difference.
    """
    laptop_folder = Path(opencode_config.skills_path("laptop"))
    laptop = {
        path.name for path in laptop_folder.iterdir() if path.is_dir() and path.name not in IGNORED_SKILL_NAMES
    } - LAPTOP_ONLY_SKILLS
    server = set(ssh(host, "ls -1 /opt/opencode-skills").split()) - IGNORED_SKILL_NAMES
    lines = [f"skill only on the laptop: {name}" for name in sorted(laptop - server)]
    lines += [f"skill only on the server: {name}" for name in sorted(server - laptop)]
    return lines


def check_mcp(host: str) -> list[str]:
    """Compare the MCP names in the laptop render and the server file.

    Args:
        host: The user and host for ssh.

    Returns:
        One line per difference.
    """
    server_text = ssh(host, "sudo -n cat /etc/opencode/opencode.jsonc")
    match = re.search(r'"servers"\s*:\s*(\{.*?\n    \})', COMMENT_LINE.sub("", server_text), re.S)
    if not match:
        return ["could not find the MCP block in the server config"]
    server_names = set(json.loads(match.group(1)))
    laptop_names = set(opencode_config.mcp_entries("laptop")) - opencode_config.LAPTOP_ONLY_MCP
    lines = [f"MCP only on the laptop: {name}" for name in sorted(laptop_names - server_names)]
    lines += [f"MCP only on the server: {name}" for name in sorted(server_names - laptop_names)]
    return lines


def check_config(host: str) -> list[str]:
    """Compare the server config with a fresh render of this working tree.

    Args:
        host: The user and host for ssh.

    Returns:
        One line when the hashes differ.
    """
    expected = sha(opencode_config.render("server"))
    actual = sha(ssh(host, "sudo -n cat /etc/opencode/opencode.jsonc"))
    if expected != actual:
        return [f"server config hash {actual} differs from a render of this tree {expected}"]
    return []


def check_agents(host: str) -> list[str]:
    """Check that the server AGENTS.md starts with the shared core.

    Args:
        host: The user and host for ssh.

    Returns:
        One line when the core differs.
    """
    core = opencode_config.AGENTS_CORE.read_text(encoding="utf-8").strip()
    server_text = ssh(host, "sudo -n cat /etc/opencode/AGENTS.md")
    if not server_text.strip().startswith(core):
        return ["the server AGENTS.md does not start with the shared core of this tree"]
    return []


def main(argv: list[str]) -> int:
    """Run all checks and print the result.

    Args:
        argv: Command line arguments without the program name.

    Returns:
        Process exit code.
    """
    parser = argparse.ArgumentParser(description="Compare the laptop and server OpenCode setup.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="User and host for ssh.")
    args = parser.parse_args(argv)

    checks = {
        "skills": check_skills,
        "mcp": check_mcp,
        "config": check_config,
        "agents": check_agents,
    }
    differences = 0
    for name, check in checks.items():
        lines = check(args.host)
        print(f"{name}: {'ok' if not lines else 'DIFFERENT'}")
        for line in lines:
            print(f"  {line}")
        differences += len(lines)
    return 1 if differences else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
