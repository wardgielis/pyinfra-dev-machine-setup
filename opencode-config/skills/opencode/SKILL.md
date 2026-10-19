---
name: opencode
description: Use when editing or managing opencode in this repo — configuration (files/opencode_config.jsonc), plugins (opencode-config/plugins/), AGENTS.md (files/opencode_agents.md), or skills (opencode-config/skills/). Covers the repo-to-live file map, the repo-first editing rule, deploy.py Section 8 sync, and the skill authoring workflow (frontmatter, naming, lifecycle, size, vendoring, validation). For generic opencode configuration (schema, agents, permissions, MCP, plugin API) use the upstream docs.
metadata:
  review_after: "2026-11-19"
  docs_url: "https://opencode.ai/docs/skills/"
---

# opencode

This skill is the operating manual for managing **opencode itself in this repo**. Every opencode asset — config, plugins, AGENTS.md, and skills — is authored as code, public and version-controlled, then deployed to `~/.config/opencode` by pyinfra.

**Goal**: a fresh machine gets exactly the same opencode setup. The repo is the single source of truth; `~/.config/opencode` is a deploy artifact.

**Upstream reference**: [opencode docs](https://opencode.ai/docs/) cover generic configuration — schema, agents, permissions, MCP, and the plugin API. This repo has no local generic-config skill; the repo-specific operating manual is this file.

---

## Repo-first rule

**Never hand-edit `~/.config/opencode/`.** Edit the repo file, then sync via `deploy.py` Section 8 (`uv run pyinfra @local deploy.py`). Direct local edits get overwritten on the next deploy and are lost on a new machine.

## Repo → live file map

| Asset | Edit here (repo) | Live path (deploy artifact) | Sync mechanism |
|---|---|---|---|
| Config | `files/opencode_config.jsonc` | `~/.config/opencode/opencode.jsonc` | `_deploy_template()` (uses `string.Template`, `$$` escapes `$`; requires `OPENCODE_SKILLS_PATH` env) |
| Plugins | `opencode-config/plugins/<id>/` | `~/.config/opencode/plugins/<id>/` | `files.sync` + `npm install` |
| Plugin deps | `opencode-config/package.json` | `~/.config/opencode/package.json` | `files.put` + `npm install` |
| AGENTS.md | `files/opencode_agents.md` | `~/.config/opencode/AGENTS.md` | `files.put` |
| Skills | `opencode-config/skills/<name>/SKILL.md` | loaded via the config `skills` array (no copy) | none — read live from repo |

Key details:

- **Config**: the template renders `$$schema` → `$schema`, and the V2 `skills` array is substituted from `OPENCODE_SKILLS_PATH`. It already includes the claude-code plugin and provider settings — preserve them when editing. `opencode.jsonc` in the repo is powered by these templates, not a standalone file; keep it that way. The config is **native V2** (`plugins`, `providers.*.settings`, `policies`, `skills` array) — do not reintroduce V1 keys (`plugin`, `provider.*.options`, `disabled_providers`, `skills.paths`).
- **Plugins**: repo-versioned, deploy-synced. Each plugin is a directory (`opencode-config/plugins/<id>/`) with a server entrypoint (`index.ts`) and, when it needs the terminal UI, a TUI entrypoint (`tui.ts`) importing `@opencode/plugin/tui`. The freshness plugin (`skill-freshness/`) shows a stale-skill toast from `tui.ts` on TUI startup — announced from `setup()` after a 1.5 s deferral, with `session.created` kept as a fallback and one guard shared by both, so it appears on the home screen and on resumed sessions too, at most once per run. Every run appends one line to `~/.local/share/opencode/log/skill-freshness.log` (`trigger=… stale=N toast=shown`), the quickest way to tell whether the plugin ran. When adding a plugin, put the source under `opencode-config/plugins/<id>/`, add any npm dependency to `opencode-config/package.json`, then run deploy so `npm install` picks it up.

  Entrypoints are resolved by `@opencode/plugin`'s `host.resolve`: `index.ts` is the **server** entrypoint (loads for every client), `tui.ts` the **terminal UI** entrypoint. Only the terminal CLI/TUI reconciles TUI plugins — the desktop app does not, so a toast emitted from `tui.ts` is invisible there. V2 has **no server-side** toast or log API (V1's `client.tui.showToast` / `client.app.log` are gone), so any user-facing notice must live in `tui.ts`.

  **Startup-hook gotcha**: plugins load *after* the client's event stream connects — the log shows `"event stream connected"` roughly 20 ms before `stage=setup plugin=…`. A `server.connected` listener registered in `setup()` therefore never fires (confirmed with a pty capture in which the handler never ran). Do startup work directly in `setup()`, deferred with `setTimeout` so the first frame commits before `ui.toast.show`; use `session.created` only as an extra fallback.

  **JSONC parsing gotcha**: plugins that read `opencode.jsonc` must strip comments string-aware. A naive `raw.replace(/\/\/.*$/gm, "")` corrupts `"$schema": "https://…"`, `JSON.parse` then throws, and a `try/catch` fallback silently degrades the plugin to a no-op. `skill-freshness/tui.ts` carries `parseJsonc()` for this.
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
   - Custom repo metadata keys: `review_after` (ISO date, consumed by the skill-freshness plugin to flag out-of-date skills), `docs_url` (reference link), and `version_pinned` (the tool/runtime version the skill targets, e.g. `3.12+` or `polars >= 2.0`). Set `review_after` ~1 month out when authoring/updating.
4. **Body structure**: start with `# <name>`, then a goal, then short sections. Cross-link related skills with a `**Related skills**:` line and route to alternatives (e.g. [[spark]] vs [[polars]]). Use existing skills (e.g. [[pyinfra]], [[homebrew]]) as the style reference.
5. **Size**: keep the skill in one `SKILL.md` up to ~500 lines. Past that, move depth into `references/<topic>.md`, link it from the skill body, and open every reference file with a `## Contents` line so it can be skimmed.

### Lifecycle: generic vs org-specific

- **Generic skills** (public, safe for anyone): commit them — the repo is public and mirrors to GitHub.
- **Org-specific skills** (internal infrastructure, workspace URLs, org names, credentials): add the directory path to the repo's `.gitignore`, then remind the user to copy it to their SSD backup. Deleting the repo copy loses it permanently since it's untracked.

### Vendored skills

When a skill is copied from an upstream project (e.g. the official Polars skill):

- Keep the upstream `LICENSE` next to `SKILL.md`.
- Add `VENDORED.md` with the source repository, tag, commit, copy date, the files copied, and every local change.
- Patch upstream examples for the pinned version and record each patch in `VENDORED.md`.
- Keep the upstream text where it is still correct; put local additions in clearly marked sections.

### Validation checklist

- `SKILL.md` spelled in all caps
- frontmatter present with `name` + `description`; `name` exactly matches the directory and is unique across ALL locations
- `description` starts with "Use when", is at most 1024 chars, and names the class of work so it triggers even when the user does not name the tool
- every file under `opencode-config/skills/`, never under `~/.config/opencode/skills`
- code fences balanced; every cross-link to another skill points to an existing skill directory
- examples executed against the installed versions, including each example patched in a vendored skill
- three realistic sample prompts run through the skill and the output checked against it

## Reloading

Skills are injected into `<available_skills>` at session start. After adding/updating a skill you must restart opencode (or start a new session) before an agent can see it. Loading is on-demand via the `skill` tool; an agent reads the full SKILL.md by its `<location>` path only when relevant.

Plugin *code* is hot-reloaded by the file watcher, but provider/provider-settings are read when the server starts. **Quitting chat sessions does not restart the app** — the background service (`pgrep -f 'opencode-cli serve'`) and the desktop app keep running. To force a clean re-read, fully quit and relaunch OpenCode, or run `opencode service restart` / `opencode reload`.
