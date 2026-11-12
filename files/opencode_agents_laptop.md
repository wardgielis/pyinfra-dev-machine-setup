## Creating New Skills

Follow the repo's skill-authoring workflow: write skills to
`~/pyinfra-dev-machine-setup/opencode-config/skills/<name>/SKILL.md` and follow the
naming/frontmatter/validation rules. Full procedure: load the **[[opencode]]** skill. To test
and iterate on a skill (test prompts, baseline comparison, benchmark, review viewer, description
tuning), load the **[[skill-creator]]** skill as well.

`~/.claude/skills` is also a discovery source (lower precedence than the repo), so Claude
Desktop's synced skills appear in the list. Those that need Claude app tools are denied in
`files/opencode_config.jsonc` (`skill.use` policies); do not rely on them.

## The homelab server lives in the same repo

`homelab/` manages the briareus mini PC. It is a second pyinfra target with its
own inventory, deploy and task modules. Run it from inside `homelab/`. Read
`homelab/AGENTS.md` before changing anything there.

The OpenCode config is shared: one template, rendered per target by
`scripts/opencode_config.py`. A change to policies or instructions reaches both
the laptop and the server, so test both variants with `bash scripts/ci.sh`.

## Editing OpenCode config, plugins, or AGENTS.md
OpenCode assets are managed in the repo, not in `~/.config/opencode`:

- Config → `files/opencode_config.jsonc` (deployed as `~/.config/opencode/opencode.jsonc`)
- Plugins → `opencode-config/plugins/` (+ `opencode-config/package.json` deps)
- AGENTS.md → `files/opencode_agents_core.md` (shared) plus `files/opencode_agents_laptop.md` (laptop), joined by `scripts/opencode_config.py`
- Skills → `opencode-config/skills/<name>/SKILL.md`

Edit the repo file, then sync via `deploy.py` Section 8. Never hand-edit `~/.config/opencode`.
Full workflow: load the **[[opencode]]** skill.

## PyCharm MCP

OpenCode is wired to PyCharm's built-in MCP server, exposed as `tools.pycharm.*` (52
tools: inspections and lint, refactoring, run configurations, Jupyter kernels, database
connections). Prefer it over shell tooling when IDE-accurate answers matter.

- **Instance-wide, not per project.** PyCharm enables the server for the whole IDE
  installation (`options/mcpServer.xml`), so one endpoint serves every project open in
  that PyCharm instance; the opencode side is a single global entry in
  `~/.config/opencode/opencode.jsonc`, so every session in every directory gets it.
- **Always pass `projectPath`** (an absolute path, typically the session's working
  directory). Without it a call fails with "Unable to determine the target project".
  The server can only act on projects that are actually open in PyCharm.
- **Use the `/stream` endpoint, never `/sse`.** `/sse` is the legacy GET-only transport
  and opencode's `remote` type POSTs to it, failing with HTTP 405. The working URL is
  `http://127.0.0.1:64462/stream` (streamable HTTP).
- **The port is chosen per IDE launch**, so it can change when PyCharm restarts. Re-read it
  from Settings → Tools → MCP Server (or `scripts/find-endpoint.sh` in the [[pycharm]]
  skill), then set `PYCHARM_MCP_URL` in `.env`; the default lives in `deploy.py` Section 8.
- **Verify with `opencode mcp list`** (expect `✓ pycharm connected`). MCP servers are
  read when the opencode server starts; a config change is usually picked up live, but if
  `mcp list` still reports a failure, restart OpenCode (`opencode service restart`).

Full tool map, pre-flight checks, index-lag discipline and troubleshooting: load the
**[[pycharm]]** skill.

## If the `claude-agent` provider dies

Claude models run through opencode's built-in **Claude Agent** provider (`claude-agent`,
opencode 2.2.3+). There is no plugin: opencode starts the installed `claude` CLI through
the official Claude Agent SDK. It resolves `claude` from `PATH` with **no bundled
fallback**, so a missing or outdated binary takes the whole provider down.

Symptoms and fixes:

- `No items available` in the model picker / no `claude-agent/*` models → run
  `opencode auth login claude-agent --method claude-login` (or `/connect` → Claude Agent),
  then `claude auth status` (expect `loggedIn: true`).
- `Claude Code … is too old; 2.1.248 or later is required` → `brew upgrade --cask claude-code`.
- `Could not resolve command on PATH: claude` → the cask is broken or off `PATH`; see below.
  To use another copy, set `OPENCODE_CLAUDE_PATH` on the server
  (`opencode service set env OPENCODE_CLAUDE_PATH /opt/claude/bin/claude`).
- Claude Code is signed in but requests fail → check `claude auth status`; the provider
  inherits whatever that CLI holds (plan, API key, Bedrock, Vertex).

Cause of a missing binary: an interrupted `brew upgrade`. Homebrew removes a cask's
version directory before staging the new one, so a killed or failed upgrade leaves
`/opt/homebrew/Caskroom/claude-code/` holding only `.metadata/` — no binary, no version
dir. `brew list --cask` still lists the cask while `brew info --cask` says "Not installed".
The same state makes every pyinfra run abort at Section 2 (`BrewCasks` fact).

Fail-safe — run the doctor, don't hand-debug it:

```bash
bash ~/pyinfra-dev-machine-setup/scripts/cask-doctor.sh   # detects + reinstalls broken casks
```

It is idempotent and no-ops on a healthy machine, and `deploy.py` runs it at load time on
every deploy. If you repair manually, use `brew uninstall --cask <name> --force` then
`brew install --cask <name>` — **never `--zap`**, which deletes `~/.claude.json` and the
CLI credentials and forces a fresh login. Details: the **[[homebrew]]** skill.

Claude Agent is local-only: it is skipped in remote workspaces. It also deliberately does
not read `~/.claude` settings, `CLAUDE.md`, hooks, MCP servers or skills — opencode's own
`AGENTS.md`, skills, MCP servers and permissions are what apply.

