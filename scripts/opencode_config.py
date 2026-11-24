"""Render the shared OpenCode config for one target.

Both the laptop and the server render the same template and the same MCP list.
The laptop adds one extra entry (pycharm). Only the skills path, the permission
rules and a few per-target constants differ, so a change to policies,
instructions or MCP servers reaches both targets by construction.

The command line has these jobs:

    --target laptop --out PATH     write the laptop config
    --target server --out PATH     write the server config
    --target server --kind agents --out PATH   write the server AGENTS.md
    --check-drift                  compare the two variants
    --report-review-dates DIR      list skills whose review date has passed
"""

import argparse
import json
import os
import re
import string
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "files" / "opencode_config.jsonc"

# One MCP list for every target. Extra entries per target come on top of it.
MCP_SHARED = REPO / "files" / "opencode_mcp_shared.json"
MCP_EXTRA = {
    "laptop": REPO / "files" / "opencode_mcp_laptop.json",
    "server": None,
}
PERMISSIONS = {
    "laptop": REPO / "files" / "opencode_permissions_laptop.json",
    "server": REPO / "files" / "opencode_permissions_server.json",
}

# One anchor per fragment, in the order the template holds them.
ANCHORS = {
    "mcp": "${OPENCODE_MCP_SERVERS}",
    "permissions": "${OPENCODE_PERMISSIONS}",
}
SKILLS_ANCHOR = "${OPENCODE_SKILLS_PATH}"

SKILLS_PATHS = {
    "laptop": str(REPO / "opencode-config" / "skills"),
    "server": "/opt/opencode-skills",
}

# Entries that exist on one target only. The drift check allows exactly these.
LAPTOP_ONLY_MCP = {"pycharm"}

# Values that are secret or personal. The laptop config gets the real value at
# render time. The server config gets {env:NAME}, and the service reads the value
# from /etc/opencode-secrets/opencode.env at run time, so no secret sits in the
# config file.
MCP_SECRET_VARIABLES = (
    "ARGOCD_BASE_URL",
    "ARGOCD_API_TOKEN",
    "CLICKHOUSE_DEV_USER",
    "CLICKHOUSE_DEV_PASSWORD",
    "CLICKHOUSE_PROD_USER",
    "CLICKHOUSE_PROD_PASSWORD",
    "GRAFANA_URL",
    "GRAFANA_SERVICE_ACCOUNT_TOKEN",
)

# Tokens that tools read from the environment but that the config never names.
OTHER_SERVER_VARIABLES = ("GITLAB_TOKEN", "JIRA_API_TOKEN")

# Every variable the deploy must write to the server secrets file for the MCP
# servers and tools. The drift check fails when the server config names a
# variable that is not in this list.
SERVER_ENV_VARIABLES = (*MCP_SECRET_VARIABLES, *OTHER_SERVER_VARIABLES)

# Per-target constants. The server reaches both ClickHouse hosts through local
# SSH tunnels (see homelab/tasks/naturalis.py), the laptop reaches the dev host
# directly over eduVPN.
TARGET_CONSTANTS = {
    "laptop": {
        "CLICKHOUSE_DEV_HOST": "tools-development-clickhouse.hosts.naturalis.io",
        "CLICKHOUSE_DEV_PORT": "8123",
    },
    "server": {
        "CLICKHOUSE_DEV_HOST": "127.0.0.1",
        "CLICKHOUSE_DEV_PORT": "8124",
    },
}

# Defaults for laptop values that are blank when the variable is unset. Blank
# values keep a server wired but inert instead of failing the render.
DEFAULT_VARIABLES = {
    "PYCHARM_MCP_URL": "http://127.0.0.1:64462/stream",
    **{name: "" for name in MCP_SECRET_VARIABLES},
}

# Match a frontmatter review_after value such as: review_after: "2026-12-07"
REVIEW_AFTER_PATTERN = re.compile(r"^review_after:\s*\"?(\d{4}-\d{2}-\d{2})\"?\s*$", re.MULTILINE)
ENV_REFERENCE_PATTERN = re.compile(r"\{env:([A-Z0-9_]+)\}")
COMMENT_LINE_PATTERN = re.compile(r"^\s*//.*$", re.MULTILINE)


def read_variables(target: str) -> dict[str, str]:
    """Return the placeholder values for one target.

    Args:
        target: Either laptop or server.

    Returns:
        One value per placeholder. The laptop reads the environment. The server
        gets {env:NAME} for every secret, and the constants for its own target.
    """
    if target == "server":
        values = {name: f"{{env:{name}}}" for name in MCP_SECRET_VARIABLES}
        values["PYCHARM_MCP_URL"] = DEFAULT_VARIABLES["PYCHARM_MCP_URL"]
    else:
        values = {key: os.environ.get(key, default) for key, default in DEFAULT_VARIABLES.items()}
    values.update(TARGET_CONSTANTS[target])
    return values


def skills_path(target: str) -> str:
    """Return the skills folder for a target.

    Args:
        target: Either laptop or server.

    Returns:
        The absolute skills path that goes into the rendered config.
    """
    if target == "laptop" and os.environ.get("OPENCODE_SKILLS_PATH"):
        return os.environ["OPENCODE_SKILLS_PATH"]
    return SKILLS_PATHS[target]


def indent_after_first_line(text: str, spaces: int) -> str:
    """Indent every line after the first.

    Args:
        text: Text to indent.
        spaces: Number of spaces to add.

    Returns:
        The indented text, with the first line unchanged so it can follow a key.
    """
    pad = " " * spaces
    lines = text.splitlines()
    return "\n".join([lines[0], *(pad + line for line in lines[1:])])


def merge_objects(shared: str, extra: str | None) -> str:
    """Join two JSON object texts into one, keeping comments.

    Args:
        shared: Text of the object every target uses.
        extra: Text of an object with entries for one target, or None.

    Returns:
        One object text that holds the entries of both.
    """
    shared_body = shared.strip()[1:-1].rstrip()
    extra_body = extra.strip()[1:-1].strip() if extra else ""
    if not extra_body:
        return "{" + shared_body + "\n}"
    return "{" + shared_body + ",\n  " + extra_body + "\n}"


def mcp_text(target: str) -> str:
    """Return the MCP object text for a target, before the placeholders are filled.

    Args:
        target: Either laptop or server.

    Returns:
        The shared MCP object, plus the extra entries of the target.
    """
    extra_path = MCP_EXTRA[target]
    extra = extra_path.read_text(encoding="utf-8") if extra_path else None
    return merge_objects(MCP_SHARED.read_text(encoding="utf-8"), extra)


def render_fragment(target: str, name: str) -> str:
    """Render one fragment for a target.

    Args:
        target: Either laptop or server.
        name: The fragment name, mcp or permissions.

    Returns:
        The fragment text, indented for insertion after its key.
    """
    if name == "mcp":
        fragment = mcp_text(target)
    else:
        fragment = PERMISSIONS[target].read_text(encoding="utf-8").strip()
    rendered = string.Template(fragment).substitute(read_variables(target))
    return indent_after_first_line(rendered, 4)


def render(target: str) -> str:
    """Render the config for a target.

    Args:
        target: Either laptop or server.

    Returns:
        The full config file text, ending with a newline.
    """
    if target not in MCP_EXTRA:
        raise SystemExit(f"Unknown target {target!r}. Use laptop or server.")

    text = TEMPLATE.read_text(encoding="utf-8")
    for anchor in ANCHORS.values():
        if text.count(anchor) != 1:
            raise SystemExit(f"{TEMPLATE} must contain {anchor} exactly once.")

    for name, anchor in ANCHORS.items():
        text = text.replace(anchor, render_fragment(target, name))
    return string.Template(text).substitute({"OPENCODE_SKILLS_PATH": skills_path(target)})


AGENTS_CORE = REPO / "files" / "opencode_agents_core.md"
AGENTS_ADDENDA = {
    "laptop": REPO / "files" / "opencode_agents_laptop.md",
    "server": REPO / "homelab" / "files" / "opencode_agents_server.md",
}


def render_agents(target: str) -> str:
    """Build the AGENTS.md for one target.

    The shared core comes first, then the addendum for the target. Both targets load
    the same core, so the voice and skill rules cannot drift apart.

    Args:
        target: Either laptop or server.

    Returns:
        The full AGENTS.md text, ending with a newline.
    """
    if target not in AGENTS_ADDENDA:
        raise SystemExit(f"Unknown target {target!r}. Use laptop or server.")
    core = AGENTS_CORE.read_text(encoding="utf-8").rstrip() + "\n"
    addendum = AGENTS_ADDENDA[target].read_text(encoding="utf-8").strip() + "\n"
    return core + "\n" + addendum


def mcp_entries(target: str) -> dict:
    """Parse the rendered MCP entries of a target.

    Args:
        target: Either laptop or server.

    Returns:
        The MCP server entries as a dictionary.
    """
    fragment = string.Template(COMMENT_LINE_PATTERN.sub("", mcp_text(target))).substitute(read_variables(target))
    return json.loads(fragment)


def check_drift() -> list[str]:
    """Compare the two rendered variants.

    Returns:
        A list of problems. Empty when the configs differ only at the anchors,
        the MCP lists differ only by the laptop-only entries, the server config
        names only variables that the deploy writes, and both AGENTS files share
        the same core.
    """
    problems = []
    template = TEMPLATE.read_text(encoding="utf-8")
    for anchor in ANCHORS.values():
        if template.count(anchor) != 1:
            problems.append(f"the template must hold {anchor} exactly once")
    if SKILLS_ANCHOR not in template:
        problems.append(f"the template must hold {SKILLS_ANCHOR}")

    normalized = {}
    for target in ("laptop", "server"):
        text = render(target)
        for name, anchor in ANCHORS.items():
            text = text.replace(render_fragment(target, name), anchor)
        text = text.replace(skills_path(target), SKILLS_ANCHOR)
        normalized[target] = text

    if normalized["laptop"] != normalized["server"]:
        problems.append("the laptop and server variants differ outside the anchors")

    laptop_mcp = mcp_entries("laptop")
    server_mcp = mcp_entries("server")
    expected = set(laptop_mcp) - LAPTOP_ONLY_MCP
    if set(server_mcp) != expected:
        missing = sorted(expected - set(server_mcp))
        extra = sorted(set(server_mcp) - expected)
        problems.append(f"the server MCP list differs from the laptop list: missing {missing}, extra {extra}")
    for name in sorted(expected & set(server_mcp)):
        for key in ("type", "command", "url", "protocol"):
            if laptop_mcp[name].get(key) != server_mcp[name].get(key):
                problems.append(f"MCP entry {name} differs in {key}")

    known = set(SERVER_ENV_VARIABLES)
    for name in sorted(set(ENV_REFERENCE_PATTERN.findall(render("server"))) - known):
        problems.append(f"the server config names {name}, but the deploy does not write it")

    # Both hosts must load the same AGENTS core, or the shared rules drift apart.
    core = AGENTS_CORE.read_text(encoding="utf-8").strip()
    if not core:
        problems.append("the AGENTS core is empty")
    for target in ("laptop", "server"):
        if not render_agents(target).startswith(core):
            problems.append(f"the {target} AGENTS.md does not start with the shared core")

    return problems


def report_review_dates(skills_dir: Path) -> list[str]:
    """List skills whose review date has passed.

    Args:
        skills_dir: Folder that holds one directory per skill.

    Returns:
        One line per expired skill.
    """
    today = date.today().isoformat()
    lines = []
    for skill_file in sorted(skills_dir.glob("*/SKILL.md")):
        match = REVIEW_AFTER_PATTERN.search(skill_file.read_text(encoding="utf-8")[:2000])
        if match and match.group(1) < today:
            lines.append(f"skill {skill_file.parent.name} review date {match.group(1)} has passed")
    return lines


def main(argv: list[str]) -> int:
    """Run one of the command line jobs.

    Args:
        argv: Command line arguments without the program name.

    Returns:
        Process exit code.
    """
    parser = argparse.ArgumentParser(description="Render and check the shared OpenCode config.")
    parser.add_argument("--target", choices=sorted(MCP_EXTRA))
    parser.add_argument("--kind", choices=("config", "agents"), default="config")
    parser.add_argument("--out", help="Write the rendered file to this path.")
    parser.add_argument("--check-drift", action="store_true", help="Compare the two variants.")
    parser.add_argument("--report-review-dates", metavar="DIR", help="List expired review dates.")
    args = parser.parse_args(argv)

    if args.check_drift:
        problems = check_drift()
        for problem in problems:
            print(f"drift: {problem}", file=sys.stderr)
        return 1 if problems else 0

    if args.report_review_dates:
        for line in report_review_dates(Path(args.report_review_dates)):
            print(line)
        return 0

    if not args.target or not args.out:
        parser.error("--target and --out are required unless a check is requested")

    text = render_agents(args.target) if args.kind == "agents" else render(args.target)
    Path(args.out).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
