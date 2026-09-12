---
name: opencode
description: Use when editing or managing opencode in this repo — configuration (files/opencode_config.jsonc), plugins (opencode-config/plugins/), AGENTS.md (files/opencode_agents.md), or skills (opencode-config/skills/). Covers the repo-to-live file map, the repo-first editing rule, deploy.py Section 8 sync, and the skill authoring workflow (frontmatter, naming, lifecycle). For generic opencode config/plugin reference, read [[customize-opencode]] first.
metadata:
  review_after: "2026-10-09"
  docs_url: "https://opencode.ai/docs/skills/"
---

# opencode

This skill is the operating manual for managing **opencode itself in this repo**. Every opencode asset — config, plugins, AGENTS.md, and skills — is authored as code, public and version-controlled, then deployed to `~/.config/opencode` by pyinfra.

**Goal**: a fresh machine gets exactly the same opencode setup. The repo is the single source of truth; `~/.config/opencode` is a deploy artifact.

**Related skills**: [[customize-opencode]] for generic opencode configuration reference (schema, agents, permissions, MCP, plugins API).

---

## Repo-first rule

**Never hand-edit `~/.config/opencode/`.** Edit the repo file, then sync via `deploy.py` Section 8 (`uv run pyinfra @local deploy.py`). Direct local edits get overwritten on the next deploy and are lost on a new machine.

## Repo → live file map

| Asset | Edit here (repo) | Live path (deploy artifact) | Sync mechanism |
|---|---|---|---|
| Config | `files/opencode_config.jsonc` | `~/.config/opencode/opencode.jsonc` | `_deploy_template()` (uses `string.Template`, `$$` escapes `$`; requires `OPENCODE_SKILLS_PATH` env) |
| Plugins | `opencode-config/plugins/*.ts` | `~/.config/opencode/plugins/` | `files.put` + `npm install` |
| Plugin deps | `opencode-config/package.json` | `~/.config/opencode/package.json` | `files.put` + `npm install` |
| AGENTS.md | `files/opencode_agents.md` | `~/.config/opencode/AGENTS.md` | `files.put` |
| Skills | `opencode-config/skills/<name>/SKILL.md` | loaded via `skills.paths` (no copy) | none — read live from repo |

Key details:

- **Config**: the template renders `$$schema` → `$schema`, and `skills.paths` is substituted from `OPENCODE_SKILLS_PATH`. It already includes the claude-code plugin and provider settings — preserve them when editing. `opencode.jsonc` in the repo is powered by these templates, not a standalone file; keep it that way.
- **Plugins**: repo-versioned, deploy-synced, and the freshness plugin (`skill-freshness.ts`) reads `skills.paths` from the rendered config at runtime. When adding a plugin, put the source in `opencode-config/plugins/`, add any npm dependency to `opencode-config/package.json`, then run deploy so `npm install` picks it up.
- **AGENTS.md**: always edit `files/opencode_agents.md` (this is the deployed file's source).

## Skills lifecycle

### Where skills live (single source of truth)

- **Repo path**: `opencode-config/skills/<name>/SKILL.md` — the ONLY location opencode reads skills from.
- **`~/.config/opencode/skills` is deprecated** — deploy.py removes it (`files.directory present=False`); duplicate names across locations resolve nondeterministically. Never put skills there.

### Creating or updating a skill

1. Create directory `opencode-config/skills/<name>/SKILL.md`.
2. **Name rules**: lowercase alphanumeric + single hyphens, 1-64 chars, must EXACTLY match the directory name, matching `^[a-z0-9]+(-[a-z0-9]+)*$`.
3. **Frontmatter** (YAML at top, starts with `---`):
   - `name` — required, validated (see above)
   - `description` — required, 1-1024 chars; specific enough for the agent to choose correctly, starting with "Use when ..."
   - `license`, `compatibility`, `metadata` — optional
   - Custom repo metadata keys: `review_after` (ISO date, consumed by the skill-freshness plugin to flag out-of-date skills) and `docs_url` (reference link). Set `review_after` ~1 month out when authoring/updating.
4. **Body structure**: start with `# <name>`, then a goal, then short sections. Cross-link related skills with `**Related skills**: [[other-skill]]`. Use existing skills (e.g. [[pyinfra]], [[homebrew]]) as the style reference.

### Lifecycle: generic vs org-specific

- **Generic skills** (public, safe for anyone): commit them — the repo is public and mirrors to GitHub.
- **Org-specific skills** (internal infrastructure, workspace URLs, org names, credentials): add the directory path to the repo's `.gitignore`, then remind the user to copy it to their SSD backup. Deleting the repo copy loses it permanently since it's untracked.

### Validation checklist

- `SKILL.md` spelled in all caps
- frontmatter present with `name` + `description`
- skill name unique across ALL locations (docs: "Ensure skill names are unique across all locations")
- keep every file under `opencode-config/skills/`, never under `~/.config/opencode/skills`

## Reloading

Skills are injected into `<available_skills>` at session start. After adding/updating a skill you must restart opencode (or start a new session) before an agent can see it. Loading is on-demand via the `skill` tool; an agent reads the full SKILL.md by its `<location>` path only when relevant.