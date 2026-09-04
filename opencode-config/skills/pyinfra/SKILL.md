---
name: pyinfra
description: Use when writing, modifying, or running pyinfra deploy scripts. Covers CLI usage, connectors (@local/@ssh/@docker), brew/files/server operations, best practices for idempotent machine management, and the dev-machine-setup project patterns.
metadata:
  review_after: "2026-10-09"
  docs_url: "https://docs.pyinfra.com/"
  version_pinned: "3.x"
---

# pyinfra

pyinfra is a Python-based idempotent infrastructure-as-code tool. Operations are declared in plain Python (`deploy.py`) and executed against one or more connectors (local machine, SSH hosts, Docker containers). Each operation is idempotent by default — it checks the current state and skips if already satisfied.

**This project's goal**: manage a macOS development machine as code using pyinfra + Homebrew as an OS-agnostic abstraction. Homebrew is available on both macOS and Linux, making the setup portable.

**Related skills**: [[homebrew]] for Homebrew-specific patterns and CLI reference.

---

## CLI Workflow

```sh
# Apply deploy.py to the local machine
uv run pyinfra @local deploy.py

# Dry-run: show what would change without executing
uv run pyinfra @local deploy.py --dry

# Run with verbose output (shows each command)
uv run pyinfra @local deploy.py --debug

# Show operations and commands without executing
uv run pyinfra @local deploy.py --dry --debug

# Apply to a remote SSH host
uv run pyinfra user@host deploy.py

# Apply to a Docker container
uv run pyinfra @docker/ubuntu:22.04 deploy.py
```

> **Tip**: Always use `uv run pyinfra` so the venv is respected. Running `pyinfra` directly uses the system Python and will miss project dependencies.

### Verbosity levels

- `-v`: print facts collected and noop information
- `-vv`: as above plus print shell commands sent to the remote host
- `-vvv`: as above plus print shell output from the remote host

### JSON output

Pass `--json` for machine-readable output. Works with `debug-inventory`, `fact`, `--debug-operations`, `--dry`, and regular deploys. Without `--yes` it prints proposed changes and exits without touching the host.

```sh
uv run pyinfra @local deploy.py --json --dry    # proposed changes as JSON
uv run pyinfra @local deploy.py --json --yes    # apply and emit structured results
```

### Ad-hoc command execution

```sh
# Execute a raw command on the local machine
uv run pyinfra @local exec -- echo "hello world"

# Execute over SSH
uv run pyinfra my-server.net exec -- uptime

# Execute in a new Docker container
uv run pyinfra @docker/ubuntu:22.04 exec -- echo "hello"

# Combine multiple targets
uv run pyinfra my-server.net,@local exec -- uptime
```

### Debug flags

- `--debug`: print debug info
- `--debug-facts`: print facts after generating operations, then exit
- `--debug-operations`: print operations after generating, then exit

### Inspecting inventory

```sh
# Print the resolved inventory (hosts, groups, data) and exit
uv run pyinfra @local debug-inventory

# Same as JSON
uv run pyinfra @local debug-inventory --json
```

### Ad-hoc operation execution

Run a single named operation without a deploy file:

```sh
# Install a package on a remote host
uv run pyinfra my-server.net apt.packages nginx update=true _sudo=true

# Create a user on the local machine
uv run pyinfra @local server.user pyinfra home=/home/pyinfra _sudo=true

# Set a service state
uv run pyinfra my-server.net server.service nginx running=true enabled=true
```

This is useful for quick one-off tasks or testing an operation before wiring it into `deploy.py`.

### Shell autocompletion

Generate and install shell completion scripts:

```sh
# zsh
env _PYINFRA_COMPLETE=zsh_source pyinfra > pyinfra-complete.zsh
# Then add to ~/.zshrc:
source /path/to/pyinfra-complete.zsh

# bash
env _PYINFRA_COMPLETE=bash_source pyinfra > pyinfra-complete.sh
source pyinfra-complete.sh
```

> **`--limit` filters hosts, not operations.** `--limit somehost` restricts which inventory hosts are targeted. With `@local` there is only one host, so `--limit` has no useful effect. To run a subset of operations, use Python `if` conditions in `deploy.py`.

---

## Connectors

| Connector | Usage | Notes |
|-----------|-------|-------|
| `@local` | `pyinfra @local deploy.py` | Runs commands on this machine as the current user |
| `@ssh` | `pyinfra user@host deploy.py` | SSH into a remote machine |
| `@docker` | `pyinfra @docker/ubuntu:22.04 deploy.py` | Spin up a container and apply |
| `@vagrant` | `pyinfra @vagrant deploy.py` | Apply to running Vagrant VMs |

The `@local` connector is the standard for this dev machine setup repo — there's no SSH involved.

**Important**: `@local` runs operations as the current user, not root. If an operation needs elevated privileges (e.g. writing to `/etc/`), pass `_sudo=True` — see [Global Arguments](#global-per-operation-arguments) below.

---

## Project Structure

```
pyinfra-dev-machine-setup/
├── deploy.py             # Main entrypoint — all operations declared here
├── files/                # Static config files and templates deployed by files.put()
│   ├── zshrc
│   ├── zsh_plugins.txt
│   ├── starship.toml
│   ├── ghostty_config
│   ├── jira_config       # Template — rendered with .env vars at deploy time
│   ├── databrickscfg     # Template — rendered with .env vars at deploy time
│   ├── aws_config        # Template — rendered with .env vars at deploy time
│   └── secrets           # Template — rendered with .env vars at deploy time
└── .venv/                # Managed by uv (do not commit)
```

Keep `deploy.py` organized in numbered sections (e.g. `# --- SECTION 1: GUI APPS ---`) so the intent of each block is clear and the order of operations is predictable.

### Splitting a large deploy.py

Use `local.include()` to split `deploy.py` into logical sub-files:

```python
from pyinfra import local

local.include("deploy_apps.py")       # GUI apps and casks
local.include("deploy_cli.py")        # CLI tools
local.include("deploy_config.py")     # config file deployment
```

Each included file executes in the same pyinfra context — all imports, operations, and facts are shared. Additional data can be passed via the `data` param:

```python
local.include("tasks/create_user.py", data={"group": "admin", "user": "Bob"})
```

---

## `brew` Operations

Import: `from pyinfra.operations import brew`

### `brew.packages()`

Install/remove formulae (CLI tools).

```python
brew.packages(
    name="Install modern CLI tools",
    packages=["eza", "bat", "ripgrep", "fd"],
    present=True,    # True = install, False = uninstall (default: True)
    update=True,     # run `brew update` first (default: False)
    upgrade=False,   # run `brew upgrade` first (default: False)
    latest=False,    # always upgrade if newer version exists (default: False)
)

# Pin a specific version with @
brew.packages(
    name="Install pinned Node",
    packages=["node@20"],
)
```

**`update` vs `upgrade`**:
- `update=True` → `brew update` (refreshes the package index, then installs)
- `upgrade=True` → `brew upgrade` (upgrades ALL installed formulae, then installs)
- Use `update=True` for most cases; `upgrade=True` is aggressive and slow

### `brew.casks()`

Install/remove casks (GUI applications).

```python
brew.casks(
    name="Install GUI Apps",
    casks=["ghostty", "vscodium", "bitwarden"],
    present=True,    # True = install, False = uninstall (default: True)
    upgrade=False,   # run `brew upgrade --cask` first (default: False)
    latest=False,    # always upgrade if newer version exists (default: False)
)
```

> **Note**: Unlike `brew.packages`, casks do NOT have an `update` param. `upgrade=True` runs `brew upgrade --cask` (upgrades all casks) before installing.

### `brew.tap()`

Add/remove third-party Homebrew taps.

```python
# Standard tap from GitHub
brew.tap(
    name="Tap Databricks",
    src="databricks/tap",
)

# Tap with custom URL (non-GitHub)
brew.tap(
    name="Tap AnomalyCo opencode",
    src="anomalyco/tap",
    url="https://github.com/anomalyco/homebrew-tap",
)

# url-only: src is derived from the URL path (kptdev/kpt)
brew.tap(
    name="Tap kptdev",
    url="https://github.com/kptdev/kpt",
)

# Remove a tap
brew.tap(
    name="Remove old tap",
    src="oldorg/oldtap",
    present=False,
)
```

**Always add `brew.tap()` before `brew.packages()` that depend on it** — pyinfra executes operations in declaration order.

### `brew.cask_upgrade()`

Upgrade all installed casks. Stateless — always executes.

```python
brew.cask_upgrade()
```

Equivalent to `brew upgrade --cask`. Prefer `latest=True` on `brew.casks()` to upgrade specific casks rather than all at once.

### `brew.update()` and `brew.upgrade()`

Stateless operations — always execute, never idempotent.

```python
brew.update()    # always runs `brew update`
brew.upgrade()   # always runs `brew upgrade`
```

Prefer `update=True` on `brew.packages()` instead of calling `brew.update()` directly.

---

## `files` Operations

Import: `from pyinfra.operations import files`

### `files.put()`

Upload a local file to the machine (idempotent — skips if remote matches local checksum).

```python
files.put(
    name="Sync starship config",
    src="files/starship.toml",        # relative to deploy.py directory
    dest=os.path.expanduser("~/.config/starship.toml"),
    user=None,                         # user to own the file
    group=None,                        # group to own the file
    mode="644",                        # optional: set permissions (use True to copy local perms)
    create_remote_dir=True,            # create parent dir if missing (default: True)
    force=False,                       # always upload even if unchanged (default: False)
    assume_exists=False,               # skip local file check (default: False)
    atime=None,                        # set atime (True = match local, or datetime/POSIX timestamp)
    mtime=None,                        # set mtime (True = match local, or datetime/POSIX timestamp)
)
```

> **Note on `atime`**: setting `atime` will cause pyinfra to detect a change on every run because reading the file to checksum it updates atime. Only use it if you explicitly need atime control.

> **`src` is relative to the deploy directory** (`add_deploy_dir=True` by default). Use `os.path.expanduser()` on `dest` for `~` paths — pyinfra does not expand `~` automatically.

### `files.directory()`

Ensure a directory exists (or does not exist).

```python
files.directory(
    name="Ensure ~/.config/ghostty exists",
    path=os.path.expanduser("~/.config/ghostty"),
    present=True,      # True = create, False = remove (default: True)
    mode="755",        # optional
    recursive=False,   # apply user/group/mode recursively (default: False)
    force=False,       # if target exists and is not a dir, move/remove it (default: False)
)
```

### `files.file()`

Ensure a file exists (touch) or does not exist, or set permissions on an existing file.

```python
# Create an empty file (e.g. ~/.hushlogin)
files.file(
    name="Hush macOS last login message",
    path=os.path.expanduser("~/.hushlogin"),
    present=True,
)

# Remove a file
files.file(
    name="Remove old config",
    path=os.path.expanduser("~/.old_config"),
    present=False,
)
```

### `files.link()`

Manage symlinks. Prefer over `server.shell(["ln -sf ..."])`.

```python
files.link(
    name="Symlink ghostty config",
    path=os.path.expanduser("~/.config/ghostty/config"),
    target="/opt/homebrew/etc/ghostty/config",
    present=True,          # True = create, False = remove (default: True)
    symbolic=True,         # symbolic link (default: True); False = hard link
)
```

### `files.template()`

Render a Jinja2 template and write it to the machine.

```python
files.template(
    name="Render zshrc from template",
    src="templates/zshrc.j2",
    dest=os.path.expanduser("~/.zshrc"),
    # Extra kwargs become template variables:
    username="bulbasaur",
    homebrew_prefix="/opt/homebrew",
)
```

Template file (`templates/zshrc.j2`):
```jinja
# Generated for {{ username }}
export PATH="{{ homebrew_prefix }}/bin:$PATH"
```

The `host`, `state`, and `inventory` objects are automatically available in templates. You can also pass dicts, lists, and IO-like objects as `src`.

### `files.line()`

Ensure a specific line is present or absent in a file (uses grep + sed under the hood).

```python
# Add a line if it doesn't exist (appends to end of file)
files.line(
    name="Add homebrew to PATH in .profile",
    path=os.path.expanduser("~/.profile"),
    line='eval "$(/opt/homebrew/bin/brew shellenv)"',
    present=True,
    ensure_newline=True,  # ensure the line is on its own line
)

# Replace a matching line
files.line(
    name="Update JAVA_HOME",
    path=os.path.expanduser("~/.zshrc"),
    line="JAVA_HOME=.*",
    replace='JAVA_HOME="/opt/homebrew/opt/openjdk/libexec/openjdk.jdk/Contents/Home"',
)

# Remove a line
files.line(
    name="Remove old path entry",
    path=os.path.expanduser("~/.zshrc"),
    line="export PATH=/usr/local/bin:.*",
    present=False,
)
```

> `line` is matched as a regex. If it doesn't start with `^` and end with `$`, pyinfra wraps it as `^.*LINE.*$` (full-line match). To replace part of a line, use `files.replace()` instead.

Additional params: `backup=True` to keep old copies, `extended_regex=True` for `-E` grep/sed (supports `+`, `?`, groups without backslash), `escape_regex_characters=True` to match literal special chars.

### `files.replace()`

Replace text within a file using `sed`. Unlike `files.line()`, this replaces part of a line rather than the whole line.

```python
files.replace(
    name="Update a path in config",
    path=os.path.expanduser("~/.zshrc"),
    text="old/path",
    replace="new/path",
)
```

### `files.block()`

Manage a marked block of content in a file (idempotent — uses begin/end markers). Supports positioning with `line`, `before`, and `after`.

```python
files.block(
    name="Manage pyinfra-managed block in .zshrc",
    path=os.path.expanduser("~/.zshrc"),
    content="export MY_VAR=hello\nexport OTHER_VAR=world",
    present=True,
    # Block is wrapped in:
    # # BEGIN PYINFRA BLOCK
    # ...content...
    # # END PYINFRA BLOCK
)

# Position the block relative to an existing line
files.block(
    name="Add block before PATH line",
    path=os.path.expanduser("~/.zshrc"),
    content="export EXTRA_PATH=/opt/tools/bin",
    line=".*PATH.*",
    before=True,
)

# Remove the block
files.block(
    name="Remove pyinfra block from .zshrc",
    path=os.path.expanduser("~/.zshrc"),
    present=False,
)
```

The markers default to `# BEGIN PYINFRA BLOCK` / `# END PYINFRA BLOCK`. Customize with `marker=`, `begin=`, `end=`.

### `files.download()`

Download a file from a URL using `curl` or `wget`.

```python
files.download(
    name="Download Docker repo file",
    src="https://download.docker.com/linux/centos/docker-ce.repo",
    dest="/etc/yum.repos.d/docker-ce.repo",
    user="root",              # user to own the file
    group="root",             # group to own the file
    mode="644",               # permissions
    cache_time=86400,         # re-download after N seconds (None = always)
    force=False,              # always download even if exists (default: False)
    sha256sum="abc...",       # optional checksum verification
    sha384sum=None,           # sha384 checksum
    sha1sum=None,             # sha1 checksum
    md5sum=None,              # md5 checksum
    headers={"Authorization": "Bearer token"},  # HTTP headers
    insecure=False,           # disable SSL verification
    proxy="http://proxy:3128",  # HTTP proxy
    limit_rate="1M",          # bandwidth cap (curl/wget format: 1M, 500k)
)
```

### `files.unarchive()`

Extract archive files on the remote system. Supports `.tar`, `.tar.gz`, `.tar.bz2`, `.tar.xz`, `.tar.zst`, `.zip`.

```python
files.unarchive(
    name="Extract app tarball",
    src="/tmp/app.tar.gz",
    dest="/opt/app",
    remote_src=True,          # archive is already on the remote system
    creates="/opt/app/bin/start",  # skip if this path exists
)
```

### `files.sync()`

Sync a local directory to a remote one. More efficient than multiple `files.put()` calls for directory trees.

```python
files.sync(
    name="Sync config directory",
    src="files/configs",
    dest=os.path.expanduser("~/.config/myapp"),
    delete=True,                    # remove remote files not present locally
    exclude=["*.pyc", "__pycache__"],  # fnmatch patterns
    exclude_dir=["node_modules"],
)
```

### `files.get()` and `files.copy()`

- `files.get(src, dest)` — download a file from the remote system to local
- `files.copy(src, dest, overwrite=False)` — copy a remote file/directory to another remote location

Both are stateless (always execute).

### `files.move()`

Move a remote file, directory, or symlink to another location. Stateless — always executes.

```python
files.move(
    name="Move old config out of the way",
    src="/tmp/old_config",
    dest="/tmp/backup",
    overwrite=False,   # whether to overwrite dest if it exists (default: False)
)
```

### `files.rsync()`

Sync a local directory to the remote system using the local `rsync` binary. **Alpha** — only supported with `@local` and SSH connectors. When using SSH, only `_sudo` and `_sudo_user` global arguments are supported.

```python
files.rsync(
    name="Rsync local dir to remote",
    src="files/configs/",
    dest="/etc/myapp/",
    flags=["-avz", "--delete"],
)
```

Stateless — always executes. Prefer `files.sync()` for cross-connector use; use `files.rsync()` only when you need `rsync`-specific flags (e.g. `--checksum`, bandwidth throttling).

### `files.flags()`

Set or clear file flags (macOS `chflags`).

```python
files.flags(
    name="Ensure ~/Library is visible in the GUI",
    path=os.path.expanduser("~/Library"),
    flags=["hidden"],
    present=False,    # clear the hidden flag
)
```

---

## `launchd` Operations (macOS)

Import: `from pyinfra.operations import launchd`

On macOS, `launchd` is the native service manager. Use `launchd` operations instead of `server.service()` when you need macOS-specific control (user agents vs system daemons, plist management).

### `launchd.service()`

Start/stop/enable a launchd service by its label. More macOS-idiomatic than `server.service()`.

```python
launchd.service(
    name="Ensure homebrew postgres is running",
    service="homebrew.mxcl.postgresql@16",
    running=True,
    restarted=False,   # one-shot restart
    reloaded=False,    # one-shot reload
    enabled=None,      # True = load at login, False = unload, None = don't change
    user_mode=False,   # True = manage as user agent (launchctl --user); False = system
)
```

### `launchd.plist()`

Ensure a launchd plist file is present/absent and loaded. Idempotent — compares the plist content and reloads only if it changed.

```python
import os

launchd.plist(
    name="Install custom launch agent",
    path=os.path.expanduser("~/Library/LaunchAgents/com.mycompany.tool.plist"),
    present=True,
    loaded=True,     # whether to launchctl load it (default: True)
    user_mode=True,  # user agent (default: False = system daemon)
)
```

> **`server.service()` vs `launchd.service()`**: Use `launchd.service()` for Homebrew-managed services (e.g. `brew services start postgresql@16` equivalent) and for user-level agents (`~/Library/LaunchAgents`). Use `server.service()` for cross-platform deploys.

---

## `server` Operations

Import: `from pyinfra.operations import server`

### `server.shell()`

Run raw shell commands. Always executes (stateless, not idempotent).

```python
server.shell(
    name="Run a raw shell command",
    commands=["echo hello"],
)
```

Prefer typed operations (`brew.*`, `files.*`) over `server.shell()`. Use `server.shell()` only when no typed operation exists for the task.

### `server.etc_hosts()`

Manage entries in `/etc/hosts` (idempotent). Keyed by IP — replaces the whole line for an IP when present, or removes it when `present=False`.

```python
server.etc_hosts(
    name="Register db.internal in /etc/hosts",
    ip="192.168.1.10",
    hostnames=["db.internal", "db"],
    path="/etc/hosts",   # optional: use an alternative hosts file (default: /etc/hosts)
)

# Remove a specific hostname from an entry (keeps other names for that IP)
server.etc_hosts(
    name="Drop legacy alias",
    ip="192.168.1.10",
    hostnames="db",
    present=False,
)

# Remove all entries for an IP
server.etc_hosts(
    name="Remove 10.0.0.1 entirely",
    ip="10.0.0.1",
    present=False,
)
```

### `server.wait()`

Wait for a port to become active on the target machine. Checks every second.

```python
server.wait(
    name="Wait for webserver to start",
    port=80,
)
```

### `server.service()`

Manage services (launchd on macOS, systemd on Linux).

```python
server.service(
    name="Ensure nginx is running",
    service="nginx",
    running=True,        # whether the service should be running (default: True)
    enabled=True,        # start on boot
    restarted=False,     # restart the service (one-shot, stateless)
    reloaded=False,      # reload the service config (one-shot, stateless)
    command=None,        # custom command to run instead of start/stop/reload
)
```

### `server.script()` and `server.script_template()`

Upload and execute a local script (or Jinja2 script template) on the remote host. Both are stateless.

```python
server.script(
    name="Run bootstrap script",
    src="files/bootstrap.sh",
)

server.script_template(
    name="Run templated setup",
    src="templates/setup.sh.j2",
    some_var="value",
)
```

### Other server operations

| Operation | Description |
|-----------|-------------|
| `server.user()` | Add/remove/update users and SSH keys |
| `server.group()` | Add/remove system groups |
| `server.hostname()` | Set the system hostname |
| `server.reboot()` | Reboot and wait for reconnection |
| `server.packages()` | Install via OS package manager (auto-detects apt/yum/etc.) |
| `server.locale()` | Enable/disable locales |
| `server.modprobe()` | Load/unload kernel modules |
| `server.mount()` | Manage mounted filesystems |
| `server.sysctl()` | Edit sysctl configuration |
| `server.timezone()` | Set system timezone |
| `server.security_limit()` | Edit `/etc/security/limits.conf` |
| `server.kill()` | Kill a process by PID |
| `server.user_authorized_keys()` | Manage `authorized_keys` for users |

---

## Global Per-Operation Arguments

Every pyinfra operation accepts these keyword arguments (prefixed with `_`) to override behavior for that single call.

### Privilege & user escalation

| Argument | Type | Description |
|----------|------|-------------|
| `_sudo` | `bool` | Run with `sudo` |
| `_sudo_user` | `str` | `sudo -u <user>` (default: `root`) |
| `_sudo_password` | `str` | Sudo password if required |
| `_use_sudo_login` | `bool` | Execute sudo with a login shell |
| `_preserve_sudo_env` | `bool` | Preserve the connecting user's shell environment |
| `_su_user` | `str` | Execute with `su -u <user>` |
| `_use_su_login` | `bool` | Execute su with a login shell |
| `_preserve_su_env` | `bool` | Preserve environment when using su |
| `_su_shell` | `str` | Shell to use instead of the user's login shell when using su (Linux only; useful when target user has `nologin`) |
| `_su_password` | `str` | Password for su |
| `_doas` | `bool` | Execute with `doas` |
| `_doas_user` | `str` | `doas -u <user>` |
| `_dzdo` | `bool` | Execute with `dzdo` |
| `_dzdo_user` | `str` | `dzdo -u <user>` |

> Escalation order: `doas` → `dzdo` → `sudo` → `su`. Combining them nests accordingly.

### Shell control & features

| Argument | Type | Description |
|----------|------|-------------|
| `_shell_executable` | `str` | Shell to use (default: `sh`) |
| `_chdir` | `str` | Directory to switch to before executing |
| `_env` | `dict` | Extra environment variables for this operation |
| `_success_exit_codes` | `list[int]` | Exit codes to consider a success (default: `[0]`) |
| `_timeout` | `int` | Timeout for each command in seconds |
| `_get_pty` | `bool` | Get a pseudoTTY |
| `_stdin` | `str/list` | String or buffer to send to stdin |
| `_temp_dir` | `str` | Temporary directory on the remote host |

### Operation meta & callbacks

| Argument | Type | Description |
|----------|------|-------------|
| `name` | `str` | Human-readable label shown in CLI output |
| `_ignore_errors` | `bool` | Continue deploy even if this operation fails |
| `_continue_on_error` | `bool` | Continue executing commands after error (requires `_ignore_errors=True`) |
| `_if` | `callable/list` | Only run if callable(s) return True (see [Change Detection](#change-detection)) |

### Execution strategy

| Argument | Type | Description |
|----------|------|-------------|
| `_parallel` | `int` | Max hosts to execute on at once (`0` = global default = all) |
| `_run_once` | `bool` | Only execute on the first host that reaches the operation |
| `_serial` | `bool` | Run host by host instead of in parallel |

These three are mutually exclusive per operation.

### Retry behavior

| Argument | Type | Description |
|----------|------|-------------|
| `_retries` | `int` | Number of times to retry failed operations (default: `0`) |
| `_retry_delay` | `int/float` | Seconds between retries (default: `5`) |
| `_retry_until` | `callable` | Function taking output data; returns True to keep retrying |

```python
server.shell(
    name="Download file with retries",
    commands=["curl -O https://example.com/file.tar.gz"],
    _retries=3,
    _retry_delay=10,
)

# Custom retry condition
def retry_on_network_error(output_data):
    for line in output_data["stderr_lines"]:
        if "temporary failure" in line.lower():
            return True
    return False

server.shell(
    name="Download with conditional retry",
    commands=["wget https://example.com/large-file.zip"],
    _retries=5,
    _retry_until=retry_on_network_error,
)
```

CLI-level retries: `--retry N` and `--retry-delay N` flags.

### Full example

```python
files.put(
    name="Write to system location",
    src="files/hosts_entry",
    dest="/etc/hosts",
    _sudo=True,
    _sudo_user="root",
    _chdir="/tmp",
    _env={"EDITOR": "vim"},
    _retries=2,
    _retry_delay=5,
)

brew.packages(
    name="Try installing optional tool",
    packages=["some-optional-tool"],
    _ignore_errors=True,
)
```

---

## Reusable Deploy Units with `@deploy`

The `@deploy()` decorator groups related operations into a callable unit — the pyinfra equivalent of an Ansible role.

```python
from pyinfra.api import deploy
from pyinfra.operations import brew, files
import os

@deploy("Install and configure starship")
def setup_starship():
    brew.packages(
        name="Install starship",
        packages=["starship"],
    )
    files.put(
        name="Sync starship config",
        src="files/starship.toml",
        dest=os.path.expanduser("~/.config/starship.toml"),
    )

# Call it like any other operation
setup_starship(name="Set up starship prompt")
```

> **Important**: `@deploy()` must be called with parentheses. `@deploy` (no parentheses) raises a `PyinfraError`.

---

## Conditional Logic with Facts

Facts let you query the current state of the machine before deciding what to do — the idiomatic pyinfra alternative to `os.system` + `shutil.which`.

```python
from pyinfra import host
from pyinfra.facts.server import Which, Home
from pyinfra.facts.brew import BrewPackages

# Check if a command exists
if host.get_fact(Which, command="docker"):
    print("docker already installed, skipping cask install")
else:
    brew.casks(name="Install Docker Desktop", casks=["docker-desktop"])

# Get the home directory
home = host.get_fact(Home)
files.put(
    name="Sync config",
    src="files/zshrc",
    dest=f"{home}/.zshrc",  # no os.path.expanduser needed
)

# Check what brew packages are already installed
installed = host.get_fact(BrewPackages)
if "node@20" not in installed:
    brew.packages(name="Install Node 20", packages=["node@20"])
```

Available brew facts: `BrewPackages`, `BrewCasks`, `BrewTaps`, `BrewVersion`.

Available server facts: `Which`, `Home`, `Hostname`, `User`, `Users`, `Kernel`, `LinuxDistribution`, `MacOsVersion`, `Port`, `Ports`, `Processes`, `Timezone`, `Uptime`, `Path`, `Command`, `Arch`, and more.

> **Important**: Only use **immutable** facts in Python branches — facts whose value cannot change during the deploy. Facts are read during prepare, before any operation runs. For conditions that need execute-time evaluation, use `_if` (see below).

### Error handling on facts

```python
# Ignore errors when getting a fact (e.g. command not installed)
if host.get_fact(Which, command="mysql", _ignore_errors=True):
    ...
```

---

## Change Detection

Every operation returns an `OperationMeta` object with gating helpers. Use `_if` to gate operations at **execute time** (after earlier operations have run).

```python
from pyinfra.operations import server, brew

create_user = server.user(name="Create user", user="deploy")

# Only run if the user was actually created
server.shell(
    name="Bootstrap user setup",
    commands=["mkdir -p /home/deploy/.ssh"],
    _if=create_user.did_change,
)

# Gate on multiple operations
setup_app = brew.packages(name="Install app", packages=["myapp"])
setup_config = files.put(name="Sync config", src="files/app.conf", dest="/etc/app.conf")

server.shell(
    name="Restart app after changes",
    commands=["brew services restart myapp"],
    _if=[setup_app.did_change, setup_config.did_change],
)

# Custom lambda for OR conditions
server.shell(
    name="Notify on any change",
    commands=["echo 'something changed'"],
    _if=lambda: setup_app.did_change() or setup_config.did_change(),
)

# Utilities
from pyinfra.operations.util import any_changed, all_changed
server.shell(commands=["echo 'any changed'"], _if=any_changed(setup_app, setup_config))
server.shell(commands=["echo 'all changed'"], _if=all_changed(setup_app, setup_config))
```

Available helpers on `OperationMeta`:
- `did_change` — true if the operation executed at least one command
- `did_not_change` — inverse
- `did_succeed` — true if finished without error (covers both ran+succeeded and no-change-needed)
- `did_error` — true if any command failed

> **Important**: `_if` must be a callable or list of callables. Passing a value directly (e.g. `_if=host.get_fact(MyFact)`) does NOT work. Wrap in a lambda: `_if=lambda: bool(host.get_fact(MyFact))`.

---

## The `config` Object

Set deploy-wide defaults instead of passing per-operation kwargs repeatedly.

```python
from pyinfra import config

config.SUDO = True           # all operations below will use sudo by default
config.REQUIRE_PYINFRA_VERSION = "~=3.0"
config.REQUIRE_PACKAGES = ["pyinfra~=3.0"]   # or a path: "requirements.txt"
```

Per-operation kwargs override config defaults. Plain Python variables (`APP_USER = "myapp"`) are just constants — prefer `host.data` for host-specific values.

---

## The `inventory` Object

Access facts and data from other hosts in the inventory.

```python
from pyinfra import inventory
from pyinfra.facts.server import Hostname
from pyinfra.operations import files

db_host = inventory.get_host("postgres-main")
db_hostname = db_host.get_fact(Hostname)

files.template(
    name="Generate app config",
    src="templates/app-config.j2",
    dest="/opt/myapp/config.yaml",
    db_hostname=db_hostname,
)
```

---

## Output & Callbacks

pyinfra doesn't execute operations immediately, so output isn't available right away. Use `python.call` to access results after execution.

```python
from pyinfra import logger
from pyinfra.operations import python, server

result = server.shell(commands=["echo output"])

def callback():
    logger.info(f"Got result: {result.stdout}")

python.call(name="Log output", function=callback)
```

---

## When to Use `os.system` Instead of pyinfra Operations

Some tasks cannot be expressed as idempotent pyinfra operations because they require:

- **Interactive TTY / `sudo` prompts** (e.g. `launchctl` for Docker Desktop)
- **Brew autoupdate** (launchd plist bootstrapping has no pyinfra operation)

Pattern used in this project:

```python
import os, shutil

# Guard with a check so the command only runs when needed
if not shutil.which("docker"):
    print("Installing docker-desktop...")
    os.system("brew install --cask docker-desktop")

if not os.path.exists(os.path.expanduser("~/Library/LaunchAgents/homebrew.autoupdate.plist")):
    os.system("brew tap homebrew/autoupdate && brew autoupdate start 86400 --cleanup")
```

**Rule**: if you're using `os.system`, wrap it in a guard condition that makes it idempotent. Otherwise every `pyinfra` run will execute it.

---

## Best Practices

- **Always set `name=`** on every operation — it appears in structured logs and helps identify slow or failing steps
- **Group by logical section** with `# --- SECTION N: ... ---` comments; keeps deploy.py readable
- **Declare taps before packages** that depend on them — execution is top-to-bottom
- **Use `update=True` on the first `brew.packages()` block** so the index is fresh; subsequent blocks don't need it
- **`os.path.expanduser()`** on all destination paths that use `~`
- **Keep `files/` flat** for config files deployed by `files.put()`; only introduce `templates/` if you need Jinja2 templating
- **Never use `present=False` accidentally** — double-check when removing packages
- **Secrets and credentials** are loaded from `.env` at the top of `deploy.py` via `os.environ.setdefault`; the `_deploy_template` helper renders config files from `files/` templates using those values
- **Prefer facts over `os.system` guards** for conditional logic — `host.get_fact(Which, command="tool")` is cleaner and testable
- **Use `@deploy()` for reusable groups** — if you find yourself copy-pasting the same set of operations, extract them into a `@deploy()` function
- **Use `files.link()` instead of `server.shell(["ln -sf ..."])`** — idempotent and checkable
- **Use `files.sync()` over multiple `files.put()`** when syncing a directory tree — more efficient and supports delete
- **Use `files.block()` with `before`/`after`/`line`** for precise positioning in config files
- **Use `config` for deploy-wide settings** (e.g. `config.SUDO = True`) instead of `_sudo=True` on every operation
- **Use `_retries` for flaky network operations** — e.g. downloading packages or tapping remote repos
- **Use `server.etc_hosts()` instead of `files.line()` on `/etc/hosts`** — purpose-built and more reliable

---

## Idempotency Rules

| Operation | Idempotent? | Notes |
|-----------|-------------|-------|
| `brew.packages()` | Yes | Checks installed packages via `brew list` |
| `brew.casks()` | Yes | Checks installed casks via `brew list --cask` |
| `brew.tap()` | Yes | Checks existing taps via `brew tap` |
| `files.put()` | Yes | Checksums the remote file |
| `files.directory()` | Yes | Checks directory existence |
| `files.file()` | Yes | Checks file existence |
| `files.link()` | Yes | Checks symlink target |
| `files.template()` | Yes | Renders template and checksums result |
| `files.line()` | Yes | Checks for line presence before writing |
| `files.replace()` | Yes | Checks for text presence before writing |
| `files.block()` | Yes | Checks for block markers before writing |
| `files.download()` | Yes | Re-downloads after `cache_time` seconds |
| `files.sync()` | Yes | Syncs directory, optionally deletes extras |
| `files.unarchive()` | Yes | Uses `creates` param for idempotency |
| `server.etc_hosts()` | Yes | Checks existing entries |
| `server.service()` | Yes | Checks running/enabled state |
| `brew.update()` | No | Always runs `brew update` |
| `brew.upgrade()` | No | Always runs `brew upgrade` |
| `brew.cask_upgrade()` | No | Always runs `brew upgrade --cask` |
| `server.shell()` | No | Always executes commands |
| `server.script()` | No | Always uploads and executes |
| `server.wait()` | No | Stateless — always polls until port is active |
| `files.get()` | No | Always downloads |
| `files.copy()` | No | Always copies |
| `files.move()` | No | Always moves |
| `files.rsync()` | No | Always runs rsync (alpha) |
| `os.system(...)` | Only if you add a guard | Your responsibility |

---

## Quick Reference

```sh
# Run the full deploy
uv run pyinfra @local deploy.py

# Dry run (preview only)
uv run pyinfra @local deploy.py --dry

# Debug (verbose output)
uv run pyinfra @local deploy.py --debug

# Preview with full command details
uv run pyinfra @local deploy.py --dry --debug

# JSON output
uv run pyinfra @local deploy.py --json --dry

# Ad-hoc command
uv run pyinfra @local exec -- echo "hello"

# Ad-hoc operation (no deploy file needed)
uv run pyinfra @local server.shell commands="echo hello"

# Collect a fact
uv run pyinfra @local fact server.Hostname

# Inspect inventory
uv run pyinfra @local debug-inventory

# Retry on failure
uv run pyinfra @local deploy.py --retry 3 --retry-delay 10
```

---

## Troubleshooting

### Operation is skipped with "noop"

**Cause**: pyinfra detected the state already matches. This is correct behavior — it means the operation is idempotent and the machine is already in the desired state.

**If you want to force**: add `force=True` to `files.put()` / `files.directory()`, or for packages use `latest=True` on `brew.packages()`.

### Permission denied writing a file

**Cause**: `@local` runs operations as the current user. Writing to system-owned paths (e.g. `/etc/`) requires sudo.

**Fix**: Add `_sudo=True` to the operation:
```python
files.put(
    name="Write system file",
    src="files/something",
    dest="/etc/something",
    _sudo=True,
)
```

### `brew.tap()` fails silently

**Cause**: `src` must be in `owner/repo` format. A URL without `src` derives the name from the URL path.

**Fix**:
```python
brew.tap(name="...", src="owner/repo")  # correct
brew.tap(name="...", src="owner")       # wrong — only one component
```

### Config file not updated after editing `files/`

**Cause**: `files.put()` is idempotent — it checks the remote checksum. If the local file changed, it will detect the difference and re-upload automatically on the next run.

**If it's still not updating**: check that the `src` path is correct and relative to the deploy directory, and that `force=False` isn't masking the actual issue (it's fine at default).

### `--limit` doesn't filter by operation name

**Cause**: `--limit` in pyinfra filters which **hosts** receive operations, not which operations run. With `@local` (single host) it has no effect.

**Workaround**: Use Python conditions in `deploy.py` to selectively run sections:
```python
import os
RUN_SECTION = os.environ.get("SECTION", "all")

if RUN_SECTION in ("all", "apps"):
    brew.casks(name="Install GUI Apps", casks=[...])

if RUN_SECTION in ("all", "cli"):
    brew.packages(name="Install CLI Tools", packages=[...])
```

Then run: `SECTION=apps uv run pyinfra @local deploy.py`

### Facts return unexpected values

**Cause**: Facts are gathered once at the start of a deploy (prepare phase). If an earlier operation changes the state, later Python `if` branches still see the pre-deploy state.

**Fix**: Use `_if` for execute-time conditions that need to reflect earlier operation results.

### `_if` raises `ArgumentTypeError` or always runs

**Cause**: `_if` must be a callable (function/lambda), not a direct value. `_if=host.get_fact(SomeFact)` evaluates immediately and passes the result (not a callable) to pyinfra.

**Fix**: `_if=lambda: bool(host.get_fact(SomeFact))`

---

## Related Skills

- [[homebrew]]: Homebrew CLI reference, tap/cask/formula patterns, and autoupdate setup
