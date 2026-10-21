---
name: pycharm
description: Use when work touches a JetBrains IDE through its built-in MCP server — when `tools.pycharm.*` tools are available or would help (IDE inspections and lint, symbol search, call hierarchy, safe rename, apply_patch, run configurations, integrated terminal, Jupyter notebooks with a live kernel, the project's Python interpreter, database/SQL tools), when a session seems to be missing IDE tools, when IDE results look wrong (everything red while pytest passes, stale or phantom symbols), or when the IDE connection itself is broken (HTTP 405 on /sse, a port that changed after an IDE restart, "Unable to determine the target project", "doesn't correspond to any open project"). Also use when wiring, verifying or troubleshooting the IDE-to-agent connection for opencode.
metadata:
  review_after: "2026-11-21"
  docs_url: "https://www.jetbrains.com/help/pycharm/mcp-server.html"
  version_pinned: "PyCharm 2026.2.3 (MCP Server plugin bundled since 2025.2)"
---

# pycharm

The JetBrains IDE is a second, better-informed view of the code than the shell is. It has a
parsed and indexed project model, framework resolution, and the same inspections the editor
shows. This skill is about using that view well — and about the fact that it is a *remote
service with state*: it can be unreachable, bound to the wrong project, or confidently wrong.

**Related skills**: [[opencode]] for the repo-first rule on editing opencode config;
[[python]] for project layout and tooling conventions; [[jupyter-notebook]] for notebook
authoring; [[spark]] / [[databricks]] for the data work those PyCharm plugins no longer cover.

---

## What the connection is

PyCharm ships an **MCP Server** plugin (bundled and enabled by default; "Enable MCP Server"
under Settings → Tools → MCP Server). It serves the IDE's own tools over HTTP so any MCP
client can drive the IDE. opencode connects to it as a remote MCP server and exposes the
tools as `tools.pycharm.*`.

Observed on the reference install (PyCharm 2026.2.3): **52 tools** — analysis, code insight,
search, refactoring, file, formatting, patch, execution, Jupyter notebooks, Python
environment, database/SQL, plus `execute_tool` (the router) and `air_set_session_title`.

Three properties shape everything below:

1. **The server is instance-wide, the calls are project-scoped.** One endpoint per IDE
   installation serves *every* project open in that instance (the enable flag lives in
   `options/mcpServer.xml` at application level, not in a project's `.idea/`). But each call
   must name its target project via `projectPath`, and the IDE can only act on projects that
   are actually open in it. Verified with two projects open at once: the same endpoint
   answered for both, and each call returned that project's own branch and status.
2. **Only the streamable-HTTP endpoint works.** PyCharm serves `/stream` (streamable HTTP)
   and `/sse` (legacy SSE). opencode's `type: "remote"` speaks streamable HTTP; the legacy
   `/sse` is GET-only, so pointing at it fails with `HTTP 405`.
3. **The IDE is a cache.** The tools read the IDE's index and PSI, which can trail disk, or
   be current and still wrong because of the interpreter or content root.

## Wire it up (opencode)

opencode config is deployed from the repo, never hand-edited — see [[opencode]]. **Do not
edit `~/.config/opencode/opencode.jsonc`, not even for a one-line port change**; it is
overwritten on the next deploy and the change is lost or diverges.

The entry lives in `files/opencode_config.jsonc` (`mcp.servers.pycharm`) with the URL from
`PYCHARM_MCP_URL` (default in `deploy.py` Section 8, override in `.env`). A correct entry:

```jsonc
"mcp": {
  "servers": {
    "pycharm": { "type": "remote", "url": "http://127.0.0.1:64462/stream" }
  }
}
```

V2 remote fields worth knowing: `disabled: true` (not `enabled: false`), `codemode: false`
to expose the tools directly instead of through Code Mode, `timeout` (per-server ms),
`protocol` (`legacy` default, `auto`, `2026-07-28`).

Verify with `opencode mcp list` — expect `✓ pycharm connected` (the output is padded, so
match on `connected`, not on the spacing). `opencode mcp add <name> --url <url> --global`
exists but bypasses the deploy, so prefer the template.

### Changing the endpoint

`.env` does not contain `PYCHARM_MCP_URL` by default — `.env.example` documents the key
commented out, so append your own line:

```sh
echo 'PYCHARM_MCP_URL=http://127.0.0.1:64462/stream' >> .env   # use the live port
```

Then re-render from the repo:

```sh
cd ~/pyinfra-dev-machine-setup
printf 'n\n' | uv run pyinfra -y @local deploy.py   # `n` answers Section 7's removal prompt
```

The `-y` and the piped `n` matter: without `-y` pyinfra eats stdin, without the `n` the run
stops at an interactive prompt. The deploy re-renders all sections, so it takes a minute.

### Finding the endpoint

The IDE chooses its MCP port at launch, so **it can change when PyCharm restarts**. The
authoritative value is Settings → Tools → MCP Server in the IDE. From the shell, the skill's
`scripts/find-endpoint.sh` probes the listening IDE processes and prints every live
`/stream` endpoint. Run it from the repo root (or by its full path from anywhere):

```sh
sh opencode-config/skills/pycharm/scripts/find-endpoint.sh
# http://127.0.0.1:64462/stream  <= {"result":{"serverInfo":{"name":"PyCharm MCP Server",...
```

Silence is not proof: the script matches IDE process names, so it misses unusual launchers
(and Linux, where the process is `java`). Read the port from the settings panel in that case,
and never hand-probe a remembered range.

## Pre-flight: before trusting any result

**Pass `projectPath` on every call, and never assume the cwd is used.** opencode does not
send it for you: a call without it fails even when the session's working directory is an
open project. Sessions that start in `~` while the repo is a subdirectory are normal here,
so pass the repo root explicitly.

Two different errors, two different fixes:

| Error | Meaning | Fix |
|---|---|---|
| `Unable to determine the target project` | No `projectPath` sent | Pass the project root |
| `projectPath=<p> doesn't correspond to any open project` | That path is not inside an open project | Open it in PyCharm, or stop asking the IDE about it |

Both errors may append a list of the open projects, so tell them apart by the message, not
by the list. A path *inside* an open project (`…/opencode-config`) resolves to that
project's root, so a subdirectory is safe. An unrelated path is not — and every answer about
it would be worthless, so check this before acting on results. The IDE log shows the same
condition as `no IDE MCP servers: source project <path> is not open`.

Note that after a restart the IDE reopens only its **last** project, so a session in any
other repo hits the second error until that project is opened — a very common way for this
to look like a broken connection.

### Diagnose in order; the symptom does not name the cause

"It worked yesterday and now it fails" has several causes that look identical from the
outside. Cheapest check first:

1. **`opencode mcp list`** — it dials fresh, so `✓ connected` proves the URL is right *now*.
   It does **not** prove the session you are in is healthy, and it never shows the port.
2. **The exact error text** — it identifies transport (405), project binding, or a dead
   socket without guessing. `connected` at step 1 while *this session's* calls still fail
   means a dead transport from a connection made before the restart: start a new session,
   and `opencode service restart` if it persists.
3. **Is the project one the IDE has open?** If not, nothing else matters.
4. **The model** — probe it as below. A working connection with a wrong model produces no
   connection error at all.

Do not "fix" the port before 1-2 point at it. A restart equally leaves the project closed or
kills the open session's transport, and a port that never moved costs a full deploy to
"fix" nothing.

### "Connected" is not "usable"

| State | Symptom | Response |
|---|---|---|
| **Not connected** | calls error or time out; `mcp list` shows failed | Fall back to shell tooling; fix the connection |
| **Connected, model unusable** | calls answer but semantics are wrong: imports red, symbols unresolved, inspections flag everything | Do not trust semantic answers; find which of the two causes below applies |
| **Healthy** | the semantic probe below passes | Trust the IDE for semantic answers |

**Probe semantically, not by index lookup.** `search_symbol` reads the file index and finds
names even when PSI/type resolution is dead — it can report Healthy on a project where
nothing resolves. Use instead:

- `lint_files` on a file that imports an **in-project** module, and look for unresolved
  references in the result: that exercises resolution, not text indexing;
- `get_python_environment` with `filePath` (required) — interpreter, venv path and package
  manager, or `noInterpreterConfigured` with a hint;
- `get_symbol_info` on a **reference, not the declaration**: at a usage it returns
  `symbolInfo` with `declarationFile`/`declarationLine`, but at the `def` line it returns
  documentation only with `symbolInfo: null` — so probing the declaration reads as broken
  when the model is fine. No `symbolInfo` at a usage means there is no symbol there.

Argument names differ per tool, so the literal probe is:

```js
// Code Mode; substitute the absolute project path and a line that *references* a symbol
tools.pycharm.lint_files({ files: ["deploy.py"], projectPath: "/abs/path/to/project" })
tools.pycharm.get_python_environment({ filePath: "deploy.py", projectPath: "/abs/path/to/project" })
tools.pycharm.get_symbol_info({ filePath: "deploy.py", line: 42, column: 5, projectPath: "/abs/path/to/project" })
```

`lint_files` reporting `Unresolved reference` is the positive signal that resolution is
broken; zero such findings on a file with in-project imports is the healthy case.

Not health checks: `get_project_modules` (a bare module lists fine on a broken model) and
`get_project_dependencies` (JVM-centric; on this Python repo it reported only a JavaScript
dependency).

### Two causes of an unusable model

- **Index lag** — the IDE is behind disk, typically because opencode's `edit`/`write`
  bypassed it. Fix: `lint_files` / `get_file_problems`, which trigger a VFS refresh and wait
  for indexing.
- **Fresh but wrong model** — the index is current and still wrong: wrong interpreter, or a
  content root that is a parent/child of the repo root. This is the textbook "everything is
  red but `pytest` passes" (pytest puts the rootdir on `sys.path`, PyCharm does not). Fix the
  interpreter or content root; re-indexing will not help.

Rules that follow:

- After edits: `lint_files` first (a one-element array works) — `get_file_problems` also
  refreshes the index but can miss problems. Then trust semantic lookups.
- After a structural change (rename/move/delete done as text edits), grep for the old name;
  a hit means the change is incomplete whatever the IDE says.
- One writer at a time — don't edit or rename files the user is hand-editing in the IDE.

## Choosing a tool

Prefer the IDE's answer when it is a *semantic* question; the shell is fine for plumbing.

| Intent | Tool | Why over the shell |
|---|---|---|
| Find a symbol, then read it | `search_symbol` → `get_symbol_info` | Semantic lookup; `include_external` reaches SDK/library symbols |
| Text/regex/glob search | `search_text`, `search_regex`, `search_file` | Same index as Find in Files; coordinates included |
| Who calls this / what it calls | `analyze_calls` (JVM) | Real call hierarchy. Throws for Python — see Limits |
| Inspections on files | `lint_files` (preferred), `get_file_problems` | The editor's own inspections, not a linter CLI |
| Compile/build validation | `build_project` | Project model errors; `filesToRebuild` for targeted checks |
| Rename a symbol | `rename_refactoring` — **Healthy state only** | Project-wide semantic rename. Never on an unusable model; grep afterwards |
| Apply a diff | `apply_patch` | Codex `apply_patch` or unified-diff text, applied inside the project |
| Format | `reformat_file` | The project's configured formatter |
| Run something | `get_run_configurations` → `execute_run_configuration` | The user's real run configs and interpreter |
| Terminal in project context | `execute_terminal_command` | IDE terminal; prompts for confirmation unless brave mode is on |
| Notebook work | `read_notebook`, `edit_notebook`, `run_notebook_cell`, `wait_cell_execution`, `execute_code_on_kernel` | Operates the **live kernel**, so state persists and `.ipynb` is not hand-edited |
| Which Python is this project using | `get_python_environment` | The interpreter PyCharm configured, with package manager |
| VCS state | `git_status`, `get_repositories` | Multi-repo aware, porcelain-style |
| Databases | `list_database_connections` → `introspect_schema` / `execute_sql_query` | Uses connections already configured in the IDE — no credentials pass through the agent |
| Anything hidden by router-only mode | `execute_tool` | Command-line string form of any IDE tool, e.g. `execute_tool({"command": "get_project_modules"})` |

Full parameter reference per tool: **`references/tools.md`**.

### Notebooks deserve a note

The notebook tools exist because the naive alternative is bad: hand-editing `.ipynb` JSON
corrupts the file, and running cells through a subprocess loses kernel state (models,
dataframes, imports) when the process exits. Through the IDE the agent runs *in* the kernel:
`wait_cell_execution` blocks until the cell finishes instead of polling, and
`read_notebook_cell` with `output_mode: "delta"` returns only new output. Two habits:
`read_notebook_cell` for large cells (notebook-level reads are size-limited), and **save
artifacts explicitly** — agents reliably forget to persist a good model before the session
ends.

### Shell fallback (for semantic work you cannot trust)

When the model is unusable and the work is a rename or a caller audit, do it in text — but
do it completely:

```sh
git grep -nw 'old_name'        # code references
git grep -n  'old_name'        # strings, getattr, __all__, configs, docs
git grep -l  'old_name'        # the files to edit
# edit each file (per-file edit / apply_patch, or `sed -i ''` on macOS), then:
git grep -n  'old_name'        # must be zero code hits (docs may legitimately keep it)
uvx ruff check .               # or the project's configured linter; catches undefined names
uv run pytest                  # if the project has tests — the real gate
git diff --stat                # the file set should match what you intended
```

Use the project's own gates where they exist: in a repo with no dev dependencies installed,
`uv run pytest`/`uv run ruff` fail to spawn and prove nothing, while `uvx ruff check .`
still works. Two things text search will not tell you: the same name may legitimately
belong to another symbol, so read each hit before replacing; and after text edits the IDE
index is stale again — run `lint_files` before trusting any semantic answer.

If you later use `rename_refactoring` instead, grep immediately after it: the IDE leaves
unresolved references, `getattr`-style access and non-Python mentions untouched, and its
reported usage count under-reports.

## Limits and footguns

- **Argument names are inconsistent.** Search tools take `q` (not `query`); Jupyter,
  `read_file` and Python-environment tools take `file_path`; most others take `filePath`;
  `rename_refactoring` and `create_new_file` take `pathInProject`; `reformat_file` takes
  `files` (an array). Read the schema rather than guessing — the server rejects unknown
  arguments with the exact missing key.
- **Inspections: `get_file_problems` is not sufficient.** It returned `errors: []` on a file
  where `lint_files` found four real inspections; it is slow (a project refresh per call,
  IJPL-232381), needs a non-modal IDE state, and is known to miss problems (IJPL-219680,
  LLM-29051). Its result field is `errors` regardless of `errorsOnly`, so an empty array
  reads like "clean". **Use `lint_files` (a one-element array is fine) and never report a
  file clean from `get_file_problems` alone.** Respect `timedOut`, `notAnalyzedReason`,
  `more` and `partialResultReason` before saying a check was complete.
- **`analyze_calls` throws, not returns, for Python.** It needs a callable FQN such as
  `com.example.Service.run`, and `analysisKind` is a required enum
  (`INCOMING_CALLS` | `OUTGOING_CALLS`). On this Python repo both `_deploy_template` and
  `deploy._deploy_template` fail with `No callable symbol found`. For Python, use
  `search_text`.
- **Search results need reading, not just counting.** Filter out the `def` line, ignore
  hits in Markdown/docs, and remember one hit inside a loop can be N runtime invocations.
  Check `more` / `partialResultReason` before claiming a complete caller list; the default
  `limit` can truncate silently.
- **`rename_refactoring` takes the simple name** (`symbolName`), not `module.func`; a dotted
  name is rejected. It writes files, so the one-writer rule applies.
- **`read_file` output is line-prefixed** (`L1: …`), which makes naive string matching
  awkward — prefer the plain file read for exact content.
- **Python vs JVM tooling differ.** `get_python_environment` and
  `configure_python_interpreter` are PyCharm-only, and the latter cannot attach remote, WSL
  or Docker interpreters.
- **Terminal output is truncated** (2000 lines) with a 2-minute default timeout; run configs
  return a snapshot plus `fullOutputPath` for the full raw output, and `waitForExit: false`
  returns as soon as the process starts.
- **Only pass launch overrides** (`programArguments`, `workingDirectory`, `envs`) to
  `execute_run_configuration` when `get_run_configurations` reports
  `supportsDynamicLaunchOverrides: true` for that configuration.
- **Database tools need the Database Tools and SQL plugin**, and the IDE treats read-only
  enforcement as a *database-user* concern: use a read-only account for agent work rather
  than trusting prompts.
- **Tool sets are version- and plugin-dependent.** PyCharm 2026.2 unbundled Spark/PySpark,
  dbt, Databricks, Hugging Face, Colab and Data Wrangler, so data-source tooling is no
  longer guaranteed; debugger tools (`xdebug_*`) exist in IntelliJ IDEA/CLion but not in
  this PyCharm build. Refresh the authoritative list from the live server instead of
  trusting any document, including this one.
- **Router-only mode** hides tools from the list and keeps them reachable only through
  `execute_tool`. JetBrains' own guidance is to describe those tools in skills — if the tool
  list looks short, check Settings → Tools → MCP Server → Exposed Tools before assuming a
  tool is missing.

## Safety

The server is a privileged surface: it reads files, edits them, runs configurations and
terminal commands, and can reach databases.

- Keep it bound to localhost. Exposing it beyond that needs a deliberate decision, not a
  default.
- Enable **brave mode** ("Run shell commands or run configurations without confirmation")
  only for trusted projects. With it off, the IDE prompts the human — that prompt is the
  guardrail, so do not route around it.
- Disable exposed tools you don't need, especially terminal, run-configuration and database
  tools in sensitive or production-capable repositories.
- Expect tool results to carry project paths, source, run-configuration names, terminal
  output and query results into the transcript. Keep secrets out of what the agent reads.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `opencode mcp list` → `failed: Error POSTing to endpoint: (HTTP 405)` | URL points at the legacy GET-only `/sse` | Use `/stream` (streamable HTTP) |
| Connection refused, or works then stops after an IDE restart | Port moved with the restart, or the IDE is closed | Re-read the endpoint (settings panel or `scripts/find-endpoint.sh`), update `PYCHARM_MCP_URL`, redeploy |
| `mcp list` says `connected` but this session's calls fail | Dead transport from a connection made before the restart, or project scoping | Start a new session, then pass `projectPath`; `opencode service restart` if it persists |
| `Unable to determine the target project` | No `projectPath` | Pass the project root on every call |
| `doesn't correspond to any open project` + project list | That project is not open in the IDE (after a restart only the last project reopens) | Open it in PyCharm, or stop asking the IDE about it |
| Everything red, imports unresolved, `pytest` passes | Wrong interpreter or content root (a fresh but wrong model) | Fix the interpreter/content root; compare `git rev-parse --show-toplevel` with the open project and `.venv/pyvenv.cfg` with `get_python_environment` |
| Stale or phantom results right after edits | Index behind disk | `lint_files` / `get_file_problems` to force the refresh, then re-query |
| A file reports no problems but obviously has them | `get_file_problems` known to miss (IJPL-219680) | Re-check with `lint_files` |
| Tool list looks shorter than expected | Router-only mode, or a plugin unbundled | Settings → Tools → MCP Server → Exposed Tools |

## Sources

- PyCharm MCP Server (tools, transports, brave mode, exposed tools, router-only):
  <https://www.jetbrains.com/help/pycharm/mcp-server.html>
- Agentic debugging / router mode and `xdebug_*` tools (IDEA, CLion):
  <https://www.jetbrains.com/help/idea/agentic-debugging.html>
- opencode MCP servers, remote transport and V2 fields:
  <https://opencode.ai/docs/mcp-servers/> and <https://opencode.ai/docs/v2/mcp-servers/>
- Live Jupyter kernel skills and the Python environment tools (PyCharm 2026.2.1):
  <https://blog.jetbrains.com/pycharm/2026/08/we-gave-ai-agents-a-live-jupyter-kernel-in-pycharm/>
- Community skill guidance on IDE index lag and the three connection states:
  <https://github.com/woditschka/agentic-coding-reference>
- Known issues: IJPL-232381 (`get_file_problems` slow), IJPL-219680 / LLM-29051 (missed
  problems), LLM-26860 (stale file state)

Tools, parameters and behaviours above were verified against a live PyCharm 2026.2.3 MCP
server on 2026-10-21, including three sample-prompt walkthroughs (broken connection,
inspections plus caller audit, unusable model). Tool catalogue: `references/tools.md`.
