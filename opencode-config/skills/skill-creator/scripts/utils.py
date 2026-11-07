"""Shared utilities for skill-creator scripts."""

import json
import subprocess
import tempfile
from pathlib import Path


def opencode_command(model: str | None, title: str) -> list[str]:
    """Build an `opencode run` command that emits JSON events and leaves no visible session.

    `model` uses opencode's `provider/model#variant` form (for example
    `claude-agent/sonnet`); None keeps the user's default. The message is passed
    on stdin so that long prompts and prompts starting with "-" are safe.
    """
    cmd = ["opencode", "run", "--format", "json", "--auto", "--archived", "--title", title]
    if model:
        cmd.extend(["-m", model])
    return cmd


def opencode_text(prompt: str, model: str | None, timeout: int = 300) -> str:
    """Run one prompt through `opencode run` and return the concatenated text reply.

    Runs from an empty temporary directory so that no project files or
    project-level skills leak into the answer.
    """
    with tempfile.TemporaryDirectory(prefix="skill-creator-") as workdir:
        result = subprocess.run(
            opencode_command(model, "skill-creator description improvement"),
            input=prompt,
            capture_output=True,
            text=True,
            cwd=workdir,
            timeout=timeout,
        )
    if result.returncode != 0:
        raise RuntimeError(f"opencode run exited {result.returncode}\nstderr: {result.stderr}")

    parts = []
    for line in result.stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "text":
            parts.append(event.get("part", {}).get("text", ""))
    return "".join(parts)


def parse_skill_md(skill_path: Path) -> tuple[str, str, str]:
    """Parse a SKILL.md file, returning (name, description, full_content)."""
    content = (skill_path / "SKILL.md").read_text()
    lines = content.split("\n")

    if lines[0].strip() != "---":
        raise ValueError("SKILL.md missing frontmatter (no opening ---)")

    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        raise ValueError("SKILL.md missing frontmatter (no closing ---)")

    name = ""
    description = ""
    frontmatter_lines = lines[1:end_idx]
    i = 0
    while i < len(frontmatter_lines):
        line = frontmatter_lines[i]
        if line.startswith("name:"):
            name = line[len("name:"):].strip().strip('"').strip("'")
        elif line.startswith("description:"):
            value = line[len("description:"):].strip()
            # Handle YAML multiline indicators (>, |, >-, |-)
            if value in (">", "|", ">-", "|-"):
                continuation_lines: list[str] = []
                i += 1
                while i < len(frontmatter_lines) and (frontmatter_lines[i].startswith("  ") or frontmatter_lines[i].startswith("\t")):
                    continuation_lines.append(frontmatter_lines[i].strip())
                    i += 1
                description = " ".join(continuation_lines)
                continue
            else:
                description = value.strip('"').strip("'")
        i += 1

    return name, description, content
