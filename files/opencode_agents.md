# OpenCode Skills Protocol

OpenCode skills are the authoritative source for project conventions,
tooling patterns, and hard-won lessons. Training knowledge is supplementary only.

## How to Access Skills (Important)

OpenCode injects skill metadata into your system prompt via `<available_skills>` XML, which
includes a `<location>` field with the exact file path to each skill's content.

Use the `Read` tool to load a skill's content:
```
Read({ file_path: "<location from available_skills>" })
```

The `<location>` is the absolute path shown in the `<available_skills>` block,
e.g. `~/.config/opencode/skills/pyinfra/SKILL.md`

## Session Start

At the start of every session, in your FIRST response:

1. **List all available skills** from the `<available_skills>` block in your system prompt
2. **Identify which skills are relevant** to the current project context and task
3. **Read relevant skills** using the `Read` tool at the `<location>` path — read COMPLETE content
   - Not just summaries or descriptions — read the full skill content
   - Example: before recommending pyinfra changes, Read the pyinfra SKILL.md fully
4. **Tell the user** which skills you loaded, why, and what they say

Do this proactively at session start — not reactively when asked.

## Ongoing Protocol

- **Before making any technical recommendation**: check if a skill covers it
- **If a skill name matches your task** → Read its SKILL.md file fully before proceeding
- **Cross-reference all suggestions** against loaded skill patterns
- **Skill documentation > training knowledge**, always

### Edge Cases

- If no skills are relevant to the context: proceed with training knowledge, but mention this to the user
- If a skill exists but you're uncertain whether it applies: load it anyway and let the user decide

## Skill Precedence

1. **Authoritative**: Skill documentation (Read SKILL.md files first)
2. **Supplementary**: Training knowledge (fills gaps only)
3. **Never**: Substitute training for documented skill patterns

This prevents repeating mistakes and ensures you work from the most accurate, project-specific information available.

## Creating New Skills

When creating a new skill or helping the user document a new workflow, always write it to
`~/pyinfra-dev-machine-setup/opencode-config/skills/<name>/SKILL.md`.

- **Generic skills**: commit normally — they're public and version-controlled
- **Org-specific skills** (internal infrastructure, workspace URLs, org names, credentials):
  add the directory to `.gitignore` in the repo, then remind the user to copy it to their SSD backup

## Keeping AGENTS.md up to date

When you complete a task, phase, or to-do item that is listed in AGENTS.md, update the file
immediately after the work is done — mark it ✅, check it off, or remove it. Do this inside
the same turn so the next session does not repeat work that is already finished.

## Continuing through multi-step tasks

opencode requires the user to press "continue" after each turn ends. When a
task has multiple steps, do them all in one turn — chain tool calls rather
than pausing for user confirmation between subtasks. End the turn only
when the task is done, you need clarification on intent, or you hit a real
blocker. The user can interrupt or abort at any time; turn endings should
mark meaningful checkpoints, not every completed substep.
