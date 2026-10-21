#!/usr/bin/env python3
"""Configure PyCharm's Tasks plugin with a shared Jira server.

IntelliJ stores task servers per project in .idea/workspace.xml, not in the
application-level settings that JetBrains account sync covers, so the server has
to be written into every project. The username comes from JIRA_LOGIN in .env and
never enters this repository; the API token stays in the macOS Keychain.

PyCharm rewrites workspace.xml when it exits, so this refuses to write while the
IDE is running. Quit PyCharm first, then run the deploy (or this script).
"""

from __future__ import annotations

import argparse
import html
import os
import re
import shutil
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

# PyCharm refreshes this from the server's /serverInfo endpoint; the value only
# seeds the repository before the first connection.
JIRA_VERSION = "1001.0.0-SNAPSHOT"
DEFAULT_PROJECT_ROOTS = ("~/dev",)
PYCHARM_CONFIG_ROOT = Path.home() / "Library/Application Support/JetBrains"
BACKUP_PREFIX = ".pycharm-jira-backup-"

# Match a Jira project key such as BIOCL: uppercase letters and digits, at least two characters.
PROJECT_KEY_RE = re.compile(r"^[A-Z][A-Z0-9]+$")

# Match a TaskManager component with content, keeping its indentation.
TASK_MANAGER_RE = re.compile(
    r'(?P<indent>^[ \t]*)<component name="TaskManager">[\s\S]*?^[ \t]*</component>',
    re.M,
)

# Match an empty TaskManager component, for example <component name="TaskManager" />.
SELF_CLOSING_TASK_MANAGER_RE = re.compile(
    r'(?P<indent>^[ \t]*)<component name="TaskManager"\s*/>',
    re.M,
)


@dataclass(frozen=True)
class SyncResult:
    """Outcome of one synchronisation run."""

    changed: tuple[Path, ...] = ()
    unchanged: tuple[Path, ...] = ()
    skipped: tuple[tuple[Path, str], ...] = ()
    backup_dir: Path | None = None
    blocked: str | None = None

    def summary(self) -> str:
        """Return a printable summary that never includes credentials."""
        lines: list[str] = []
        if self.blocked:
            lines.append(f"  BLOCKED: {self.blocked}")
        lines.extend(f"  patched:   {path}" for path in self.changed)
        lines.extend(f"  unchanged: {path}" for path in self.unchanged)
        lines.extend(f"  skipped:   {path} ({reason})" for path, reason in self.skipped)
        if self.backup_dir:
            lines.append(f"  backup:    {self.backup_dir}")
        if not lines:
            lines.append("  nothing to do")
        return "\n".join(lines)


def is_pycharm_running() -> bool:
    """Return whether a PyCharm process is running."""
    patterns = (["-x", "pycharm"], ["-f", "PyCharm.app/Contents/MacOS"])
    for args in patterns:
        result = subprocess.run(["pgrep", *args], capture_output=True, text=True, check=False)
        if result.returncode == 0:
            return True
    return False


def find_project_workspaces(roots: Iterable[str | Path]) -> list[Path]:
    """Return the workspace.xml files of projects directly below the given roots.

    A root that is itself a project (it contains .idea/workspace.xml) is included
    as well, so a single checkout can be passed instead of its parent directory.
    """
    found: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        root_path = Path(root).expanduser()
        if not root_path.is_dir():
            continue
        candidates = [root_path / ".idea" / "workspace.xml"]
        candidates.extend(sorted(root_path.glob("*/.idea/workspace.xml")))
        for candidate in candidates:
            if candidate.is_file() and candidate not in seen:
                seen.add(candidate)
                found.append(candidate)
    return found


def find_default_project_files() -> list[Path]:
    """Return the default-project template of every installed PyCharm version."""
    return sorted(PYCHARM_CONFIG_ROOT.glob("PyCharm*/options/project.default.xml"))


def render_server_entry(indent: str, server: str, login: str, project_key: str) -> str:
    """Render one JIRA entry for the Tasks servers block."""
    query = f"project = {project_key} AND resolution = Unresolved ORDER BY updated DESC"
    return (
        f'{indent}<JIRA url="{html.escape(server, quote=True)}">\n'
        f'{indent}  <option name="jiraVersion" value="{JIRA_VERSION}" />\n'
        f'{indent}  <option name="searchQuery" value="{html.escape(query, quote=True)}" />\n'
        f"{indent}  <username>{html.escape(login)}</username>\n"
        f"{indent}</JIRA>"
    )


def render_component(indent: str, server: str, login: str, project_key: str) -> str:
    """Render a complete TaskManager component for a file that has none."""
    child = indent + "  "
    entry = render_server_entry(child + "  ", server, login, project_key)
    return (
        f'{indent}<component name="TaskManager">\n'
        f"{child}<servers>\n"
        f"{entry}\n"
        f"{child}</servers>\n"
        f'{child}<option name="changelistNameFormat" value="${{id}}/${{summary}}" />\n'
        f'{child}<option name="branchNameFormat" value="${{id}}/" />\n'
        f"{indent}</component>"
    )


def _find_server_entry(block: str, server: str) -> re.Match[str] | None:
    # Match a JIRA entry for this URL, including its indentation and tolerating a trailing slash.
    pattern = re.compile(
        r'(?P<indent>^[ \t]*)<JIRA\b[^>]*\burl="'
        + re.escape(server.rstrip("/"))
        + r'/?["][^>]*>[\s\S]*?</JIRA>',
        re.M,
    )
    return pattern.search(block)


def _shift_indent(block: str, old_indent: str, new_indent: str) -> str:
    """Move every line of a block by the indentation difference."""
    delta = len(new_indent) - len(old_indent)
    if delta == 0:
        return block
    shifted: list[str] = []
    for line in block.splitlines():
        if not line.strip():
            shifted.append(line)
        elif delta > 0:
            shifted.append(" " * delta + line)
        else:
            removable = min(-delta, len(line) - len(line.lstrip(" ")))
            shifted.append(line[removable:])
    return "\n".join(shifted)


def _upsert_servers(component: str, server: str, login: str, project_key: str) -> str:
    """Add or refresh the JIRA entry, leaving any other task servers untouched."""
    component_indent = re.match(r"^[ \t]*", component).group(0)
    expected = component_indent + "  "

    # Match a self-closing servers element such as <servers />.
    self_closing = re.search(r"(?P<indent>^[ \t]*)<servers\s*/>", component, re.M)
    if self_closing:
        entry = render_server_entry(expected + "  ", server, login, project_key)
        block = f"{expected}<servers>\n{entry}\n{expected}</servers>"
        return component[: self_closing.start()] + block + component[self_closing.end() :]

    # Match a servers element with content.
    servers = re.search(r"(?P<indent>^[ \t]*)<servers>[\s\S]*?</servers>", component, re.M)
    if servers:
        indent = servers.group("indent")
        block = _shift_indent(servers.group(0), indent, expected)
        entry = render_server_entry(expected + "  ", server, login, project_key)
        existing = _find_server_entry(block, server)
        if existing:
            updated = block[: existing.start()] + entry + block[existing.end() :]
        elif f"\n{expected}</servers>" in block:
            updated = block.replace(
                f"\n{expected}</servers>",
                f"\n{entry}\n{expected}</servers>",
            )
        else:
            closing = block.rfind("</servers>")
            updated = block[:closing].rstrip() + f"\n{entry}\n{expected}" + block[closing:]
        return component[: servers.start()] + updated + component[servers.end() :]

    entry = render_server_entry(expected + "  ", server, login, project_key)
    block = f"{expected}<servers>\n{entry}\n{expected}</servers>"
    closing = component.rfind("</component>")
    line_start = component.rfind("\n", 0, closing) + 1
    return component[:line_start] + block + "\n" + component[line_start:]


def _upsert_option(component: str, name: str, value: str, indent: str) -> str:
    """Set a TaskManager option, adding it when the component does not have it."""
    # Match an option element for this name, including its indentation.
    pattern = re.compile(
        r'(?P<indent>^[ \t]*)<option\s+name="' + re.escape(name) + r'"\s+value="[^"]*"\s*/>',
        re.M,
    )
    replacement = f'{indent}<option name="{name}" value="{html.escape(value, quote=True)}" />'
    if pattern.search(component):
        return pattern.sub(lambda _match: replacement, component, count=1)
    closing = component.rfind("</component>")
    line_start = component.rfind("\n", 0, closing) + 1
    return component[:line_start] + replacement + "\n" + component[line_start:]


def patch_text(text: str, server: str, login: str, project_key: str, root_tag: str) -> str:
    """Return the file content with the shared Jira server in place."""
    component = TASK_MANAGER_RE.search(text)
    if component:
        block = component.group(0)
        indent = re.match(r"^[ \t]*", block).group(0)
        child = indent + "  "
        updated = _upsert_servers(block, server, login, project_key)
        updated = _upsert_option(updated, "changelistNameFormat", "${id}/${summary}", child)
        updated = _upsert_option(updated, "branchNameFormat", "${id}/", child)
        return text[: component.start()] + updated + text[component.end() :]

    empty = SELF_CLOSING_TASK_MANAGER_RE.search(text)
    if empty:
        rendered = render_component(empty.group("indent"), server, login, project_key)
        return text[: empty.start()] + rendered + text[empty.end() :]

    # Match the closing tag of the file's root element, for example </project>.
    closings = list(re.finditer(rf"^(?P<indent>[ \t]*)</{root_tag}>", text, re.M))
    if not closings:
        raise ValueError(f"no </{root_tag}> element found")
    closing = closings[-1]
    rendered = render_component(closing.group("indent") + "  ", server, login, project_key)
    prefix = text[: closing.start()].rstrip("\n")
    return prefix + "\n" + rendered + "\n" + text[closing.start() :]


def _backup(path: Path, backup_dir: Path) -> None:
    """Copy a file into the backup tree, mirroring its path below the home directory."""
    try:
        relative = path.relative_to(Path.home())
    except ValueError:
        relative = Path(path.name)
    target = backup_dir / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)


def _write_atomic(path: Path, text: str) -> None:
    """Replace a file in one step so an interrupted run cannot truncate it."""
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def sync_tasks_server(
    server: str,
    login: str,
    project_key: str,
    roots: Iterable[str | Path] = DEFAULT_PROJECT_ROOTS,
    include_default: bool = True,
    dry_run: bool = False,
    allow_running: bool = False,
) -> SyncResult:
    """Write the shared Jira server into every PyCharm project.

    Args:
        server: Jira base URL, for example https://your-org.atlassian.net.
        login: Atlassian account email, read from JIRA_LOGIN.
        project_key: Jira project key used to build the search query.
        roots: Directories whose immediate subdirectories are PyCharm projects.
        include_default: Also patch the default-project template for new projects.
        dry_run: Report changes without writing files.
        allow_running: Write even while PyCharm is running. Unsafe: the IDE
            rewrites workspace.xml when it exits and would drop the change.

    Returns:
        A result listing changed, unchanged and skipped files.

    Raises:
        ValueError: If the server URL, login or project key is missing or malformed.
    """
    server = server.strip().rstrip("/")
    login = login.strip()
    project_key = project_key.strip().upper()

    if not server.startswith(("http://", "https://")):
        raise ValueError(f"JIRA_SERVER must be an http(s) URL, got {server!r}")
    if not login:
        raise ValueError("JIRA_LOGIN is empty")
    if not PROJECT_KEY_RE.match(project_key):
        raise ValueError(f"JIRA_PROJECT_KEY is not a Jira project key: {project_key!r}")

    if not dry_run and not allow_running and is_pycharm_running():
        reason = "PyCharm is running; quit it first, because it rewrites workspace.xml on exit"
        return SyncResult(blocked=reason)

    targets = find_project_workspaces(roots)
    if include_default:
        targets.extend(find_default_project_files())

    changed: list[Path] = []
    unchanged: list[Path] = []
    skipped: list[tuple[Path, str]] = []
    backup_dir: Path | None = None

    for path in dict.fromkeys(targets):
        root_tag = "defaultProject" if path.name == "project.default.xml" else "project"
        try:
            original = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            skipped.append((path, f"cannot read: {error}"))
            continue

        try:
            updated = patch_text(original, server, login, project_key, root_tag)
        except ValueError as error:
            skipped.append((path, str(error)))
            continue
        if updated == original:
            unchanged.append(path)
            continue

        changed.append(path)
        if dry_run:
            continue
        if backup_dir is None:
            stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
            backup_dir = Path.home() / f"{BACKUP_PREFIX}{stamp}"
        _backup(path, backup_dir)
        _write_atomic(path, updated)

    if not targets:
        skipped.append((Path("~"), "no .idea/workspace.xml below the configured roots"))

    return SyncResult(
        changed=tuple(changed),
        unchanged=tuple(unchanged),
        skipped=tuple(skipped),
        backup_dir=backup_dir,
    )


def _load_env(path: Path) -> None:
    """Fill unset environment variables from a .env file."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def main(argv: list[str] | None = None) -> int:
    """Run the synchronisation from the command line."""
    repo_root = Path(__file__).resolve().parent.parent
    _load_env(repo_root / ".env")

    parser = argparse.ArgumentParser(description="Write the Jira Tasks server into PyCharm projects.")
    parser.add_argument("--server", default=os.environ.get("JIRA_SERVER", ""), help="Jira base URL")
    parser.add_argument("--login", default=os.environ.get("JIRA_LOGIN", ""), help="Atlassian account email")
    parser.add_argument("--project-key", default=os.environ.get("JIRA_PROJECT_KEY", ""), help="Jira project key")
    parser.add_argument(
        "--roots",
        default=os.environ.get("PYCHARM_PROJECT_ROOTS", ":".join(DEFAULT_PROJECT_ROOTS)),
        help="Colon-separated directories that contain PyCharm projects",
    )
    parser.add_argument("--no-default", action="store_true", help="skip the default-project template")
    parser.add_argument("--dry-run", action="store_true", help="show what would change without writing")
    parser.add_argument("--check", action="store_true", help="exit 1 when changes are pending")
    parser.add_argument(
        "--allow-running",
        action="store_true",
        help="write even while PyCharm is running (the IDE may overwrite the change)",
    )
    args = parser.parse_args(argv)

    result = sync_tasks_server(
        server=args.server,
        login=args.login,
        project_key=args.project_key,
        roots=args.roots.replace(",", ":").split(":"),
        include_default=not args.no_default,
        dry_run=args.dry_run,
        allow_running=args.allow_running,
    )
    print(result.summary())
    return 1 if args.check and (result.changed or result.blocked) else 0


if __name__ == "__main__":
    raise SystemExit(main())
