# Vendored skill-creator

This directory is a copy of Anthropic's skill-creator skill, adapted for opencode.

## Source

- Repository: https://github.com/anthropics/skills
- Path: `skills/skill-creator`
- Commit: `2c5958ecac7cee2b583967a2c4981d0f4a75c579` (2026-11-06)
- Copied: 2026-11-07
- Licence: Apache-2.0 (see `LICENSE.txt`)

## Files copied from upstream

Everything under `skills/skill-creator/`: `SKILL.md`, `LICENSE.txt`, `agents/`
(`analyzer.md`, `comparator.md`, `grader.md`), `assets/eval_review.html`,
`eval-viewer/` (`generate_review.py`, `viewer.html`), `references/schemas.md`, and
`scripts/` (`__init__.py`, `aggregate_benchmark.py`, `generate_report.py`,
`improve_description.py`, `package_skill.py`, `quick_validate.py`, `run_eval.py`,
`run_loop.py`, `utils.py`).

## Local changes

1. **`SKILL.md` rewritten for opencode.** New frontmatter: `description` starts with
   "Use when", plus `license`, `review_after`, `docs_url`, `upstream_repo` and
   `upstream_commit` in `metadata`. Added a "Related skills" line and a "Where things live"
   section (repo-first rule, workspace kept out of the skills directory, new skills are
   not visible until restart). Delegated naming, frontmatter, size and vendoring rules to
   `[[opencode]]` instead of repeating them. Removed the Claude.ai and Cowork sections,
   the `present_files` packaging branch and the "no subagents" fallbacks. Subagent runs use
   opencode's `subagent` tool and are told to read the skill by path. Added a "Finish"
   section. Kept the loop, writing guidance, grading, viewer, improvement and blind
   comparison text from upstream.
2. **Robustness fixes taken from the Claude Desktop synced copy**, which was newer than
   public `main` on 2026-11-02: `scripts/aggregate_benchmark.py` (any case name, several
   runs per configuration, missing time or token values recorded as notes instead of
   failing), `eval-viewer/generate_review.py` and `eval-viewer/viewer.html` (limits on
   nested output files, tolerant `eval_metadata.json` lookup, string eval ids), and
   `agents/analyzer.md` (append notes to `benchmark.json` instead of replacing them). The
   synced copy's case-folder test format (`evals/<case>/`, `claude plugin eval`) was
   deliberately **not** taken; tests stay in `evals/evals.json`.
3. **`scripts/quick_validate.py`** is the synced copy's version (rejects packages with more
   than one `SKILL.md`) plus the repo rules from the `opencode` skill's validation
   checklist: `name` must equal the directory name, `description` must start with
   "Use when", code fences must balance, and double-bracket cross-links must point at a
   sibling skill directory.
4. **Trigger evaluation ported from `claude -p` to `opencode run`.**
   - `scripts/utils.py`: added `opencode_command()` and `opencode_text()`.
   - `scripts/run_eval.py`: rewritten. Each query runs in its own temporary project holding
     a candidate skill under `.opencode/skills/`; a run counts as a trigger when the first
     tool call is `skill` with the candidate's ID (events read from
     `opencode run --format json`). No longer writes into `.claude/commands` or the user's
     project. Defaults changed to 5 workers and a 60 s timeout. `find_project_root` and the
     `project_root` parameter were removed.
   - `scripts/improve_description.py`: `_call_claude` replaced by `_call_model`, which uses
     `opencode_text()`.
   - `scripts/run_loop.py`: removed the project-root plumbing; `--model` is now
     `provider/model#variant`.
5. **Status of the port: experimental.** The event format was verified against a live
   `opencode run` (one manual probe did load the candidate skill, and the stream showed a
   `tool_use` event with `tool: "skill"`). The automated harness then scored a should-trigger
   query at 0/3 with `claude-agent/haiku` even when the description was a near-verbatim
   match, and a model asked to list its skills often did not list the candidate. Project-local
   skills in a new temporary directory appeared inconsistently through the background
   service; `--standalone` did not help, and an `opencode reload` made them appear in a
   directory that already existed. Root cause not found. `SKILL.md` therefore tells the
   user to run a sanity check before trusting any trigger numbers and to fall back to
   manual description tuning. Revisit when opencode documents project skill discovery for
   `opencode run`.

## Updating from upstream

Diff the upstream `skills/skill-creator` against this directory, port anything useful,
keep the local changes above, and update the commit and copy date in this file and in the
`SKILL.md` metadata.
