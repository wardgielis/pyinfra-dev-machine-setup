# Vendored Jupyter Notebook skill

This directory is a copy of the OpenAI Jupyter Notebook skill, with a small
number of local changes.

## Source

- Repository: https://github.com/openai/skills
- Path: `skills/.curated/jupyter-notebook`
- Last commit touching the path: `77963424cd7687fd52e5fcfdd3f08d826ab9b1ab` (2026-02-02)
- Copied: 2026-10-19
- Licence: Apache-2.0 (see `LICENSE.txt`)

## Files copied from upstream

- `SKILL.md`
- `agents/openai.yaml`
- `assets/` (experiment and tutorial templates, two icons)
- `references/` (experiment patterns, tutorial patterns, notebook structure, quality checklist)
- `scripts/new_notebook.py`
- `LICENSE.txt`

## Local changes

1. Added a `metadata` block to the frontmatter with `short-description`,
   `author`, `source`, and `review_after`.
2. Replaced the Codex-specific `$CODEX_HOME` helper-script path with the
   skill's own directory, because opencode reads skills from the repo rather
   than from `~/.codex/skills`.
3. Added `--no-project` to the `uv run` scaffold commands so the stdlib-only
   helper script runs even when the working directory is a uv project pinned
   to a different Python version.
4. Removed the JetBrains `.intellij-skill-source` marker, which is not part of
   the upstream skill.
