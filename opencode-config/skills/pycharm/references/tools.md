# PyCharm MCP tool reference

## Contents

- Analysis, inspections and build
- Code insight
- Search
- Editing and refactoring
- Files and directories
- Execution and terminal
- Version control
- Python environment (PyCharm only)
- Jupyter notebooks (PyCharm only)
- Databases and SQL
- Session
- Regenerating this file

Generated from a live `tools/list` call against PyCharm 2026.2.3 on 2026-10-21 (52 tools). Parameters marked `?` are optional. Tool descriptions here are summaries; the server's own descriptions are longer and are what the agent sees in the tool catalog.

Every tool accepts an optional `projectPath`. Pass it on every call: the MCP server is instance-wide and needs the path to pick the target project.


## Analysis, inspections and build

| Tool | Parameters | Notes |
|---|---|---|
| `analyze_calls` | `symbolFqn`:string, `analysisKind`:string, `depth`?:integer, `maxChildren`?:integer, `maxNodes`?:integer, `treePath`?:array, `childOffset`?:integer, `timeout`?:integer, `projectPath`?:string | `analysisKind` is a required enum: `INCOMING_CALLS` or `OUTGOING_CALLS` (anything else is rejected). Needs a callable FQN (`com.example.Service.run`), so it **throws** for Python: both `_deploy_template` and `deploy._deploy_template` fail with `No callable symbol found`. Read `treePath` back to render a subtree; page children with `childOffset`. |
| `build_project` | `rebuild`?:boolean, `filesToRebuild`?:array, `timeout`?:integer, `projectPath`?:string | Triggers building of the project or specified files, waits for completion, and returns build errors. |
| `get_file_problems` | `filePath`:string, `errorsOnly`?:boolean, `timeout`?:integer, `projectPath`?:string | Triggers a VFS refresh and waits for indexing, so it is also the way to catch the IDE index up to disk after outside edits. Slow per call, needs a non-modal IDE state, and known to miss problems — it returned `errors: []` on a file where `lint_files` found four. The result field is `errors` regardless of `errorsOnly`, so an empty array reads like "clean"; never report a file clean on this call alone. |
| `lint_files` | `files`:array, `min_severity`?:string, `timeout`?:integer, `projectPath`?:string | Preferred inspection tool; a one-element array is fine. Check per-file `timedOut`, `notAnalyzedReason` and the top-level `more` flag before reporting a file clean. |
| `get_project_dependencies` | `projectPath`?:string | JVM-centric; on a Python project it may list nothing useful. Not a valid health check for Python. |
| `get_project_modules` | `projectPath`?:string | Lists fine even on an unloaded project model, so it is a false green as a health check. |

## Code insight

| Tool | Parameters | Notes |
|---|---|---|
| `get_symbol_info` | `filePath`:string, `line`:integer, `column`:integer, `projectPath`?:string | Retrieves information about the symbol at the specified position. A hit carries `symbolInfo.declarationFile`/`declarationLine`; documentation-only output with **no `symbolInfo` key** means there is no symbol at that position — not success. |

## Search

| Tool | Parameters | Notes |
|---|---|---|
| `search_symbol` | `q`:string, `paths`?:array, `include_external`?:boolean, `limit`?:integer, `projectPath`?:string | Takes `q`, not `query`. Set `include_external: true` to reach SDK and library symbols when the project search comes up empty. Index lookup only — a hit does **not** prove type resolution works. |
| `search_text` | `q`:string, `paths`?:array, `limit`?:integer, `projectPath`?:string | Takes `q` plus optional `paths` globs (`!` excludes supported). Results include the `def` line and hits in Markdown; filter both when auditing callers. |
| `search_regex` | `q`:string, `paths`?:array, `limit`?:integer, `projectPath`?:string | Takes `q` plus optional `paths` globs. |
| `search_file` | `q`:string, `paths`?:array, `includeExcluded`?:boolean, `limit`?:integer, `projectPath`?:string | Takes `q` as a glob pattern, relative to the project root. |

## Editing and refactoring

| Tool | Parameters | Notes |
|---|---|---|
| `apply_patch` | `input`?:string, `patch`?:string, `projectPath`?:string | Accepts Codex `apply_patch` or unified git diff text in `input` (or `patch`). Paths must stay inside the project. |
| `rename_refactoring` | `pathInProject`:string, `symbolName`:string, `newName`:string, `projectPath`?:string | `symbolName` is the **simple** name in that file; a dotted `module.func` is rejected. Unknown symbols error loudly rather than no-op, but on a bad model the failure mode is a *partial* rename — unresolved references, `getattr` access and non-Python mentions survive, and the reported usage count under-reports. Only use in the Healthy state, and grep the old name afterwards. |
| `reformat_file` | `files`:array, `projectPath`?:string | This build takes `files` (an array). The docs show a single `path` in other versions. |
| `create_new_file` | `pathInProject`:string, `text`?:string, `overwrite`?:boolean, `projectPath`?:string | Creates a new file at the specified path within the project directory and optionally populates it with text if provided. |

## Files and directories

| Tool | Parameters | Notes |
|---|---|---|
| `read_file` | `file_path`:string, `offset`?:integer, `limit`?:integer, `projectPath`?:string | Takes `file_path` (snake case) with `offset`/`limit`. Output is line-prefixed (`L1: …`), which makes naive string matching awkward — prefer the plain file read for exact content. Other builds expose richer modes (slice/lines/line_columns/offsets/indentation) and can read sources inside jars. |
| `list_directory_tree` | `directoryPath`:string, `maxDepth`?:integer, `timeout`?:integer, `projectPath`?:string | Tree representation like `tree`. **`maxDepth: 1` returns only the root** — use 2 for immediate children, 3 to recurse one level deeper. |
| `get_all_open_file_paths` | `projectPath`?:string | Returns active editor's and other open editors' file paths relative to the project root. |
| `open_file_in_editor` | `filePath`:string, `projectPath`?:string | Opens the specified file in the JetBrains IDE editor. |

## Execution and terminal

| Tool | Parameters | Notes |
|---|---|---|
| `get_run_configurations` | `filePath`?:string, `projectPath`?:string | Without `filePath` it lists run configurations; with it, it lists run points (executable entry points) and their line numbers for `execute_run_configuration`. |
| `execute_run_configuration` | `configurationName`?:string, `filePath`?:string, `line`?:integer, `timeout`?:integer, `waitForExit`?:boolean, `programArguments`?:string, `workingDirectory`?:string, `envs`?:object, `projectPath`?:string | Pass either `configurationName`, or `filePath` + `line`. Only use `programArguments`/`workingDirectory`/`envs` when `supportsDynamicLaunchOverrides` is true. `waitForExit: false` returns as soon as the process starts; `fullOutputPath` holds the full raw output. |
| `execute_terminal_command` | `command`:string, `executeInShell`?:boolean, `reuseExistingTerminalWindow`?:boolean, `timeout`?:integer, `maxLinesCount`?:integer, `truncateMode`?:string, `projectPath`?:string | Runs in the IDE terminal, reuses an existing window by default, truncates to 2000 lines, and prompts the user unless brave mode is on. |
| `execute_tool` | `command`:string, `projectPath`?:string | Router: invokes any IDE tool by command-line string. The only way to reach tools marked router-only in the IDE settings. |

## Version control

| Tool | Parameters | Notes |
|---|---|---|
| `get_repositories` | `projectPath`?:string | Retrieves the list of VCS roots in the project. |
| `git_status` | `repositoryPathRelativeToProject`?:string, `includeUntracked`?:boolean, `includeIgnored`?:boolean, `limit`?:integer, `projectPath`?:string | Multi-repo aware (porcelain-style), with `includeUntracked`/`includeIgnored`/`limit`. |

## Python environment (PyCharm only)

| Tool | Parameters | Notes |
|---|---|---|
| `get_python_environment` | `filePath`:string, `projectPath`?:string | Read-only. Returns interpreter version, environment type, executable path, environment path and package manager, or `noInterpreterConfigured` with a hint (not an error). |
| `configure_python_interpreter` | `filePath`:string, `projectPath`?:string | Only call it when `get_python_environment` says PyCharm can configure an interpreter. Local interpreters only; no remote/WSL/Docker. |

## Jupyter notebooks (PyCharm only)

| Tool | Parameters | Notes |
|---|---|---|
| `create_notebook` | `file_path`:string, `projectPath`?:string | Create a new empty Jupyter notebook (.ipynb) file. |
| `edit_notebook` | `file_path`:string, `cell_id`?:string, `new_source`?:string, `cell_type`?:string, `edit_mode`?:string, `projectPath`?:string | Edit a Jupyter notebook cell and save the notebook document. |
| `read_notebook` | `file_path`:string, `projectPath`?:string | Read a Jupyter notebook without executing it. |
| `read_notebook_cell` | `file_path`:string, `cell_id`:string, `read_mode`?:string, `output_mode`?:string, `projectPath`?:string | Prefer this over `read_notebook` for large cells. `output_mode: "delta"` returns only output added since the previous read of that cell. |
| `run_notebook_cell` | `file_path`:string, `cell_ids`?:array, `projectPath`?:string | Runs through the live kernel. Omit `cell_ids` to run every cell in order. |
| `wait_cell_execution` | `file_path`:string, `cell_id`:string, `projectPath`?:string | Blocks until the cell reaches a terminal state instead of polling; call it again to keep waiting. |
| `execute_code_on_kernel` | `file_path`:string, `code`:string, `projectPath`?:string | Short probe in the already-running kernel, without touching the notebook. Needs an existing kernel session. |
| `get_notebook_state` | `file_path`:string, `projectPath`?:string | Inspect the current notebook kernel execution state without starting a kernel. |
| `interrupt_notebook` | `file_path`:string, `projectPath`?:string | Interrupt the current notebook kernel execution. |
| `kill_notebook` | `file_path`:string, `projectPath`?:string | Ends the kernel session; the next execution starts a fresh kernel, so imports and setup cells must run again. |

## Databases and SQL

| Tool | Parameters | Notes |
|---|---|---|
| `list_database_connections` | `projectPath`?:string | Retrieves a list of configured database connections or data sources in the project. |
| `create_database_connection` | `name`:string, `dbms`:string, `url`:string, `needToCheckDs`:boolean, `projectPath`?:string | Set `needToCheckDs: false` when creating connections in a batch, then probe the important ones with `test_database_connection`. |
| `edit_database_connection` | `connectionId`:string, `dbms`:string, `url`:string, `needToCheckDs`:boolean, `projectPath`?:string | Edit an existing database connection (data source) identified by `connectionId`. |
| `test_database_connection` | `id`:string, `projectPath`?:string | Checks whether a specific database connection is valid and reachable. |
| `list_database_schemas` | `connectionId`:string, `projectPath`?:string | Retrieves a list of database schemas in the specified database connection. |
| `list_schema_object_kinds` | `connectionId`:string, `projectPath`?:string | Retrieves supported schema object kinds (e.g., table, view, routine) for the given database connection. |
| `list_schema_objects` | `connectionId`:string, `databaseName`:string, `schemaName`:string, `kind`?:string, `projectPath`?:string | Retrieves a list of database objects within the given schema. |
| `get_database_object_description` | `connectionId`:string, `databaseName`:string, `schemaName`:string, `kind`:string, `objectName`:string, `projectPath`?:string | Retrieves the structure of a database object (columns, types, keys, indexes) within a particular schema as a hierarchical text representation. |
| `introspect_schema` | `connectionId`:string, `databaseName`:string, `schemaName`:string, `projectPath`?:string | Loads schema metadata into the IDE model; use it when a schema reports `isIntrospected: false`. |
| `execute_sql_query` | `connectionId`:string, `databaseName`:string, `schemaName`:string, `queryText`:string, `projectPath`?:string | This build requires `databaseName` and `schemaName` alongside `connectionId`/`queryText`; results come back as CSV. Use a read-only database user for agent work. |
| `fetch_query_result` | `resultSetId`:string, `offset`:integer, `projectPath`?:string | Paginates a `resultSetId` returned by `execute_sql_query` or `preview_table_data`. |
| `preview_table_data` | `connectionId`:string, `databaseName`:string, `schemaName`:string, `tableName`:string, `maxRowCount`?:integer, `projectPath`?:string | Previews data of the table, view, materialized view or other table-like object using given database connection. |
| `list_recent_sql_queries` | `connectionId`:string, `projectPath`?:string | Not available on free subscription plans. |
| `cancel_sql_query` | `sessionId`:integer, `projectPath`?:string | Cancels a running query using its unique ID. |

## Session

| Tool | Parameters | Notes |
|---|---|---|
| `air_set_session_title` | `title`:string, `projectPath`?:string | Air-specific; sets the session title. |

## Regenerating this file

Regenerate whenever the IDE is upgraded, then diff — tool sets are version- and
plugin-dependent, and PyCharm bundles and unbundles plugins between releases. The
authoritative list is always Settings | Tools | MCP Server | Exposed Tools in the IDE.

Initialize first, then list with the `mcp-session-id` that the initialize response returns:

```sh
# 1. initialize (the response's mcp-session-id header is needed for step 2)
curl -si -X POST -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"dump","version":"1"}}}' \
  http://127.0.0.1:64462/stream

# 2. tools/list with that session id
curl -s -X POST -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'mcp-session-id: <id from initialize>' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
  http://127.0.0.1:64462/stream
```

Adjust the port — see `scripts/find-endpoint.sh`. Note that descriptions and parameter
schemas vary by IDE build: the same tool can take `file_path` in one version and `filePath`
in another, so regenerate rather than trusting a copied example.
