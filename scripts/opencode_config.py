"""Render the shared OpenCode config for one target.

Both the laptop and the server render the same template. Only the MCP block and
the skills path differ, so a change to policies or instructions reaches both
targets by construction.

The command line has three jobs:

    --target laptop --out PATH     write the laptop variant
    --target server --out PATH     write the server variant
    --check-drift                  compare the two variants
    --report-review-dates DIR      list skills whose review date has passed
"""

import argparse
import os
import re
import string
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "files" / "opencode_config.jsonc"
FRAGMENT_PATHS = {
    "mcp": {
        "laptop": REPO / "files" / "opencode_mcp_laptop.json",
        "server": REPO / "files" / "opencode_mcp_server.json",
    },
    "permissions": {
        "laptop": REPO / "files" / "opencode_permissions_laptop.json",
        "server": REPO / "files" / "opencode_permissions_server.json",
    },
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

# Placeholders inside the laptop MCP block. Blank values keep a server wired but
# inert instead of failing the render.
DEFAULT_VARIABLES = {
    "PYCHARM_MCP_URL": "http://127.0.0.1:64462/stream",
    "ARGOCD_BASE_URL": "",
    "ARGOCD_API_TOKEN": "",
    "CLICKHOUSE_DEV_USER": "",
    "CLICKHOUSE_DEV_PASSWORD": "",
    "CLICKHOUSE_PROD_USER": "",
    "CLICKHOUSE_PROD_PASSWORD": "",
    "GRAFANA_URL": "",
    "GRAFANA_SERVICE_ACCOUNT_TOKEN": "",
}

# Match a frontmatter review_after value such as: review_after: "2026-12-07"
REVIEW_AFTER_PATTERN = re.compile(r"^review_after:\s*\"?(\d{4}-\d{2}-\d{2})\"?\s*$", re.MULTILINE)


def read_variables() -> dict[str, str]:
    """Read the MCP placeholder values from the environment.

    Returns:
        One value per placeholder, with the default when the variable is unset.
    """
    return {key: os.environ.get(key, default) for key, default in DEFAULT_VARIABLES.items()}


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


def render_fragment(target: str, name: str) -> str:
    """Render one fragment for a target.

    Args:
        target: Either laptop or server.
        name: The fragment name, mcp or permissions.

    Returns:
        The fragment text, indented for insertion after its key.
    """
    fragment = FRAGMENT_PATHS[name][target].read_text(encoding="utf-8").strip()
    rendered = string.Template(fragment).substitute(read_variables())
    return indent_after_first_line(rendered, 4)


def render(target: str) -> str:
    """Render the config for a target.

    Args:
        target: Either laptop or server.

    Returns:
        The full config file text, ending with a newline.
    """
    if target not in FRAGMENT_PATHS["mcp"]:
        raise SystemExit(f"Unknown target {target!r}. Use laptop or server.")

    text = TEMPLATE.read_text(encoding="utf-8")
    for anchor in ANCHORS.values():
        if text.count(anchor) != 1:
            raise SystemExit(f"{TEMPLATE} must contain {anchor} exactly once.")

    for name, anchor in ANCHORS.items():
        text = text.replace(anchor, render_fragment(target, name))
    values = read_variables()
    values["OPENCODE_SKILLS_PATH"] = skills_path(target)
    return string.Template(text).substitute(values)


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


def check_drift() -> list[str]:
    """Compare the two rendered variants.

    Returns:
        A list of problems. Empty when the configs differ only at the anchors and
        both AGENTS files share the same core.
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
    parser.add_argument("--target", choices=sorted(FRAGMENT_PATHS["mcp"]))
    parser.add_argument("--out", help="Write the rendered config to this path.")
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

    Path(args.out).write_text(render(args.target), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
