---
name: homebrew
description: Use when working with Homebrew on macOS — installing formulae/casks, managing taps, configuring autoupdate, or mapping brew CLI commands to pyinfra brew operations. Covers best practices for using Homebrew as the package backend for macOS dev machine setup.
metadata:
  review_after: "2026-10-09"
  docs_url: "https://docs.brew.sh/"
  version_pinned: "homebrew/4.x"
---

# Homebrew

Homebrew is the primary package manager for macOS (and available on Linux). In this project it serves as the **OS-agnostic package backend** for a pyinfra-managed development machine: pyinfra declares what should be installed, Homebrew handles the actual installation on both macOS and Linux.

**Related skills**: [[pyinfra]] for how to express Homebrew operations in pyinfra deploy scripts.

---

## Core Concepts

| Concept | Description |
|---------|-------------|
| **Formula** | A CLI tool or library (installed to `$(brew --prefix)/bin`) |
| **Cask** | A macOS GUI application (installed to `/Applications`) |
| **Tap** | A third-party Git repository of formulae, casks, and/or external commands |
| **Cellar** | Where Homebrew stores installed formulae (`$(brew --prefix)/Cellar/`) |
| **Caskroom** | Where Homebrew stores installed casks (`$(brew --prefix)/Caskroom/`) |
| **Prefix** | Root directory: `/opt/homebrew` (Apple Silicon) or `/usr/local` (Intel) |
| **Bottle** | A pre-built binary package (vs compiling from source) |
| **Keg** | Installation destination of a formula version (`$(brew --prefix)/Cellar/foo/0.1`) |
| **Rack** | Directory containing one or more versioned kegs (`$(brew --prefix)/Cellar/foo`) |
| **Opt prefix** | A symlink to the active version of a keg (`$(brew --prefix)/opt/foo`) — stable path for scripts |
| **Keg-only** | A formula not symlinked into the prefix (not on PATH automatically) |
| **External command** | A `brew` subcommand defined outside the Homebrew/brew GitHub repo (installed via taps or gems) |

---

## CLI Reference

### Installing

```sh
# Install a formula (CLI tool)
brew install ripgrep

# Install a cask (GUI app)
brew install --cask ghostty

# Install multiple at once
brew install eza bat fd zoxide

# Install from a tap (tap first, then install)
brew tap anomalyco/tap
brew install anomalyco/tap/opencode

# Install a specific version
brew install node@20

# Install the HEAD (latest upstream source) version
brew install --HEAD neovim

# Reinstall (useful when a formula gets corrupted)
brew reinstall ripgrep
brew reinstall --cask ghostty

# Install only a formula's dependencies (not the formula itself)
brew install --only-dependencies <formula>

# Overwrite conflicting files in prefix while linking
brew install --overwrite ripgrep

# Take ownership of a manually-installed app so Homebrew manages it going forward
brew install --cask --adopt textmate
```

### Removing

```sh
brew uninstall ripgrep
brew uninstall --cask ghostty
brew autoremove          # remove orphaned dependencies

# --zap: for casks, also removes files outside Homebrew's prefix (prefs, caches, etc.)
# More aggressive than --force — effectively a full uninstall
brew uninstall --cask --zap ghostty
```

### Updating and Upgrading

```sh
brew update              # refresh the package index (fetch new formula versions)
brew upgrade             # upgrade all installed formulae to latest
brew upgrade ripgrep     # upgrade a single formula
brew upgrade --cask      # upgrade all casks
brew upgrade --cask ghostty  # upgrade a single cask

brew outdated            # list formulae/casks with available updates
brew outdated --cask
brew outdated --json     # JSON output for scripting
```

> **`update` vs `upgrade`**: `brew update` fetches the latest formula definitions (like `git pull`). `brew upgrade` installs newer versions. You almost always need `update` before `upgrade` to know what's available.

### Pinning (prevent accidental upgrades)

```sh
brew pin node@20         # lock to current version; brew upgrade will skip it
brew unpin node@20       # allow upgrading again
brew list --pinned       # see all pinned formulae
```

> Pinned casks with `auto_updates true` may still update themselves outside Homebrew.

### Linking and Unlinking

When you have multiple versions of a formula, only one can be "linked" (symlinked into `$(brew --prefix)/bin`) at a time:

```sh
brew link node@20        # activate this version in PATH
brew unlink node@20      # remove from PATH without uninstalling
brew link --overwrite node@20  # force-link even if conflicts exist
```

> `brew unlink <formula>` is useful to quickly remove a formula from PATH without uninstalling it — e.g. when building against a different version.

### Auditing what's installed

```sh
brew leaves              # formulae NOT depended on by anything else (what YOU installed)
brew leaves --installed-on-request   # only leaves manually installed (more precise)
brew leaves --installed-as-dependency  # only leaves that are dependencies
brew list                # all installed formulae (including dependencies)
brew list --cask         # all installed casks
brew list --versions     # show version numbers
brew deps --installed ripgrep           # what ripgrep depends on
brew uses --installed ripgrep           # what installed packages depend on ripgrep
brew uses --installed --recursive ripgrep  # transitive reverse-deps
```

> **`brew leaves --installed-on-request`** is the most precise way to audit `deploy.py` — it shows exactly which packages you explicitly requested vs pulled in as dependencies.

### Searching and Info

```sh
brew search ripgrep      # find formulae/casks matching a term
brew info ripgrep        # show version, dependencies, install status, bottle availability
brew info --cask ghostty
brew info --json ripgrep # JSON output for scripting
brew deps ripgrep        # list dependencies of a formula (flat)
brew deps --tree ripgrep # show dependency tree
brew desc ripgrep        # show formula description
brew desc -s "fast grep" # search descriptions by text
brew home ripgrep        # open formula homepage in browser
brew home --cask ghostty

# Check upstream for newer versions than Homebrew currently knows about
brew livecheck ripgrep
brew livecheck --all     # check all installed formulae

# Get the install prefix of a specific formula (stable path for scripts)
brew --prefix node@20    # e.g. /opt/homebrew/opt/node@20

# Tap info
brew tap-info anomalyco/tap          # show tap details (path, formula count, git state)
brew tap-info --json anomalyco/tap   # JSON output
```

### Fetching (pre-download)

```sh
brew fetch ripgrep       # download without installing, shows SHA-256
brew fetch --build-from-source ripgrep  # download source instead of bottle
```

Useful for pre-caching downloads, verifying checksums, or checking bottle availability before deploying.

### Migrating

```sh
brew migrate <formula>   # migrate a renamed formula to its new name
```

When a formula is renamed, `brew migrate` updates symlinks and references.

### Maintenance

```sh
brew doctor              # diagnose installation problems
brew cleanup             # remove old versions of installed formulae
brew cleanup --prune=30  # remove everything older than 30 days
brew missing             # check for missing dependencies
```

### Analytics

```sh
brew analytics off       # disable anonymous usage analytics (recommended for privacy)
brew analytics on        # re-enable
brew analytics state     # show current state
```

> **Best practice**: run `brew analytics off` once after installing Homebrew. The `HOMEBREW_NO_ANALYTICS=1` env var achieves the same without the plist entry.

### Configuration & path introspection

```sh
brew config              # show full Homebrew configuration (prefix, git state, HOMEBREW_* vars)
                         # useful first step when debugging unexpected behaviour

# Path helpers
brew --prefix            # /opt/homebrew (Apple Silicon) or /usr/local (Intel)
brew --prefix node@20    # /opt/homebrew/opt/node@20  — stable path for scripts/configs
brew --cellar            # /opt/homebrew/Cellar
brew --cellar ripgrep    # /opt/homebrew/Cellar/ripgrep  — path to a specific formula's rack
brew --caskroom          # /opt/homebrew/Caskroom
brew --repository        # path to the Homebrew git repo (needed for update-reset)
```

Use `$(brew --prefix <formula>)` in shell configs instead of hardcoding paths — the prefix changes between Apple Silicon and Intel and across Homebrew versions.

### Shell completions

```sh
brew completions         # show completion state (linked/unlinked)
brew completions link    # link Homebrew's shell completions
brew completions unlink  # unlink completions
```

### Command not found

```sh
brew command-not-found-init  # print shell hook for "command not found" handling
```

Add the output to your `.zshrc` / `.bash_profile` so missing commands suggest the Homebrew formula that provides them.

### Running commands in Homebrew's environment

```sh
# Run a command with Homebrew formulae on PATH
brew exec --formulae=jq,yq -- ./script.sh

# Portable shebang (systems with env -S)
#!/usr/bin/env -S brew exec --formulae=jq,yq --
```

Useful for scripts that need specific Homebrew tools without a full Brewfile setup.

### Aliases

```sh
brew alias i='install'   # define a custom alias
brew alias ug='upgrade'
brew alias                # list all aliases
brew unalias i            # remove an alias
brew alias --edit i       # edit alias in $EDITOR
```

Aliases prefixed with `!` or `%` run shell commands: `brew alias status='!git status'`.

### MCP Server

```sh
brew mcp-server          # start the Homebrew MCP server (AI integration)
```

The MCP server exposes Homebrew functionality via the Model Context Protocol, enabling AI assistants to query and manage packages.

---

## Taps

A **tap** is a third-party Git repository of formulae. Official taps are hosted under `github.com/<owner>/homebrew-<name>` — the `homebrew-` prefix is stripped, so `brew tap homebrew/cask` points to `github.com/homebrew/homebrew-cask`.

```sh
# Add a tap (short form — GitHub convention)
brew tap databricks/tap

# Add a tap with an explicit URL (non-GitHub or custom)
brew tap anomalyco/tap https://github.com/anomalyco/homebrew-tap

# List active taps
brew tap

# Remove a tap
brew untap databricks/tap

# Repair tap structure (one-time migration from symlink to directory-based)
brew tap --repair
```

After tapping, formulae in the tap are available as `owner/tap/formula` or just `formula` if unambiguous:

```sh
brew install databricks/tap/databricks
# or, if unambiguous:
brew install databricks
```

> If a formula name exists in both `homebrew/core` and a tap, the core version is preferred. Use the fully-qualified name to install from a specific tap: `brew install owner/repo/formula`.

---

## Autoupdate

`homebrew/autoupdate` is a Homebrew tap that schedules daily `brew update && brew upgrade` via macOS launchd — no cron needed.

```sh
# Install and enable (runs every 86400 seconds = 24 hours)
brew tap homebrew/autoupdate
brew autoupdate start 86400 --cleanup

# Check status
brew autoupdate status

# Stop autoupdate
brew autoupdate stop

# Restart with a different interval
brew autoupdate restart 43200  # every 12 hours
```

The `--cleanup` flag also runs `brew cleanup` after each upgrade to remove old versions.

The launchd plist is written to `~/Library/LaunchAgents/homebrew.autoupdate.plist`.

**In pyinfra** (guard so it only runs once):

```python
import os

if not os.path.exists(os.path.expanduser("~/Library/LaunchAgents/homebrew.autoupdate.plist")):
    os.system("brew tap homebrew/autoupdate && brew autoupdate start 86400 --cleanup")
```

---

## Brewfile (brew bundle)

A **Brewfile** is a declarative snapshot of your Homebrew state — formulae, casks, and taps in one file. It complements pyinfra by serving as a low-dependency bootstrap or backup.

### Basic commands

```sh
# Generate a Brewfile from everything currently installed
brew bundle dump --file=Brewfile
brew bundle dump --force    # overwrite existing Brewfile

# Install everything listed in a Brewfile
brew bundle install --file=Brewfile
brew bundle install --no-upgrade  # skip brew upgrade on outdated deps
brew bundle upgrade        # shorthand for bundle install --upgrade

# Check if the current state satisfies the Brewfile (no install)
brew bundle check --file=Brewfile
brew bundle check --verbose   # list unmet dependencies

# List what would be installed
brew bundle list --file=Brewfile
brew bundle list --all       # list all dep types (formula, cask, tap, mas, etc.)
```

### Managing Brewfile entries

```sh
# Add an entry to the Brewfile
brew bundle add git          # add a formula (default)
brew bundle add --cask firefox  # add a cask
brew bundle add --tap owner/tap # add a tap

# Remove an entry from the Brewfile
brew bundle remove git
brew bundle remove --cask firefox

# Edit the Brewfile in your editor
brew bundle edit
```

### Cleanup & isolated environments

```sh
# Remove dependencies not in the Brewfile
brew bundle cleanup --force

# Run a command in an isolated build environment based on the Brewfile
brew bundle exec -- ./script.sh

# Run a shell in the bundle environment
brew bundle sh
brew bundle sh --install    # install deps first

# Print the environment variables that would be set
brew bundle env
```

Example `Brewfile`:
```ruby
tap "anomalyco/tap"
tap "databricks/tap"

brew "eza"
brew "bat"
brew "ripgrep"
brew "node@20"

cask "ghostty"
cask "vscodium"
```

**When to use Brewfile vs pyinfra**: pyinfra is the primary tool because it's more expressive (conditional logic, config file deployment, secrets). The Brewfile is useful as a fallback bootstrap when pyinfra isn't set up yet, or to share a quick snapshot with others.

---

## Homebrew Services

For formulae that run as background daemons (databases, web servers):

```sh
brew services list                  # show all managed services
brew services start postgresql@16   # start and enable at login
brew services stop postgresql@16    # stop and disable
brew services restart postgresql@16
brew services run postgresql@16     # start without enabling at login

brew services info postgresql@16    # show service info
brew services info --json           # JSON output

brew services kill postgresql@16    # stop immediately but keep registered

brew services cleanup              # remove unused services
```

Services are managed via launchd (macOS) or systemd (Linux).

Use `--sudo` prefix to operate on system-level services (`/Library/LaunchDaemons` or `/usr/lib/systemd/system`).

---

## Environment Variables

Key environment variables that affect Homebrew behavior in scripts and pyinfra deploys:

| Variable | Effect |
|----------|--------|
| `HOMEBREW_NO_AUTO_UPDATE=1` | Skip `brew update` on every `brew install`. Use in scripts where you control update timing (e.g. pyinfra already calls `update=True`). |
| `HOMEBREW_NO_INSTALL_CLEANUP=1` | Skip automatic cleanup after installs (speeds up CI). |
| `HOMEBREW_CASK_OPTS="--no-quarantine"` | Apply quarantine removal to all cask installs globally. |
| `HOMEBREW_NO_ANALYTICS=1` | Disable analytics collection without running `brew analytics off`. |
| `HOMEBREW_NO_EMOJI=1` | Hide the beer mug emoji at end of build output. |
| `HOMEBREW_INSTALL_BADGE="custom text"` | Replace the beer emoji with custom text. |
| `HOMEBREW_NO_ASK=1` | Skip confirmation prompts during install (non-interactive). |
| `HOMEBREW_DISPLAY_INSTALL_TIMES=1` | Show how long each install took. |
| `HOMEBREW_CLEANUP_MAX_AGE_DAYS=N` | Control how many days of cached downloads to keep (default: 120). |
| `HOMEBREW_BUNDLE_FILE=/path/Brewfile` | Override the default Brewfile location for `brew bundle`. |
| `HOMEBREW_BUNDLE_FILE_GLOBAL=1` | Use `~/.homebrew/Brewfile` or `~/.Brewfile` for `brew bundle`. |

**In pyinfra**, pass these via `_env` if a specific operation benefits:

```python
from pyinfra.operations import server

server.shell(
    name="Fast brew install without auto-update",
    commands=["brew install some-tool"],
    _env={"HOMEBREW_NO_AUTO_UPDATE": "1"},
)
```

Or set `HOMEBREW_NO_AUTO_UPDATE=1` in your shell when running pyinfra, since pyinfra already handles `brew update` explicitly via `update=True`.

---

## pyinfra Operation Mapping

How Homebrew CLI commands map to pyinfra `brew` operations:

| CLI command | pyinfra equivalent |
|-------------|-------------------|
| `brew update` | `brew.update()` or `update=True` on `brew.packages()` |
| `brew upgrade` | `brew.upgrade()` or `upgrade=True` on `brew.packages()` |
| `brew install <pkg>` | `brew.packages(packages=["<pkg>"])` |
| `brew uninstall <pkg>` | `brew.packages(packages=["<pkg>"], present=False)` |
| `brew install --cask <app>` | `brew.casks(casks=["<app>"])` |
| `brew uninstall --cask <app>` | `brew.casks(casks=["<app>"], present=False)` |
| `brew upgrade --cask` | `brew.cask_upgrade()` or `upgrade=True` on `brew.casks()` |
| `brew tap owner/name` | `brew.tap(src="owner/name")` |
| `brew untap owner/name` | `brew.tap(src="owner/name", present=False)` |

**Caveat**: `brew.packages(update=True)` runs `brew update` then installs. It does NOT upgrade other packages — it just refreshes the index. Use `latest=True` if you want the latest version of a specific package checked on every run.

---

## macOS-Specific Notes

### Apple Silicon vs Intel prefix

| Architecture | Homebrew prefix |
|---|---|
| Apple Silicon (M1/M2/M3/M4) | `/opt/homebrew` |
| Intel | `/usr/local` |

Get the prefix dynamically: `$(brew --prefix)`. Use this in shell configs instead of hardcoding:

```sh
eval "$(/opt/homebrew/bin/brew shellenv)"  # Apple Silicon
# or in zshrc: eval "$(brew shellenv)"     # portable
```

### ARM vs Intel bottle availability

When no pre-built binary (bottle) exists for Apple Silicon, Homebrew compiles from source — this can take 10–30 minutes for large tools. Check before adding a new formula:

```sh
brew info formula | grep -A5 "Bottle"
```

If the bottle line shows only `x86_64_linux` or `monterey/ventura` (Intel), expect a source build. Consider whether that's acceptable or if there's a cask alternative.

### Gatekeeper / quarantine

macOS quarantines casks downloaded from the internet. If an app won't open:

```sh
# Remove quarantine attribute for a specific app
xattr -dr com.apple.quarantine /Applications/AppName.app

# Or allow all installs (less secure)
brew install --cask --no-quarantine ghostty
```

### Xcode Command Line Tools

Homebrew requires the Xcode CLT. If missing:

```sh
xcode-select --install
```

If Homebrew is already installed but CLT was reset after a macOS update:

```sh
brew doctor  # will diagnose and tell you what to run
```

### Adopting manually-installed apps

If an app was installed manually (not via Homebrew) and you want Homebrew to manage it:

```sh
brew install --cask --adopt textmate
```

This takes ownership of the existing app in `/Applications` without overwriting it.

---

## Best Practices

- **Separate formulae from casks** — use `brew.packages()` for CLI tools and `brew.casks()` for GUI apps; don't mix them in one call
- **Tap before you install** — always add `brew.tap()` before `brew.packages()` that depend on that tap
- **Use `update=True` once per deploy** — add it to the first `brew.packages()` block; subsequent blocks will share the refreshed index
- **Pin stable tools** — use `brew pin <formula>` for anything that breaks on major version bumps (e.g. `postgresql`, `python`)
- **Prefer casks for GUI apps** — they handle app updates, quarantine removal, and macOS integration (Spotlight, etc.) better than manual installs
- **Run `brew doctor` before debugging** — it diagnoses 90% of Homebrew issues automatically
- **Group related packages** in one `brew.packages()` call for readability — pyinfra's log output shows the `name=` label, not individual packages
- **Opt out of analytics** — run `brew analytics off` once after install, or set `HOMEBREW_NO_ANALYTICS=1` in your shell config
- **Use `brew leaves --installed-on-request`** when auditing `deploy.py` — cross-reference with your package list to spot anything you installed ad-hoc outside of pyinfra
- **Use `brew install --cask --adopt`** to take ownership of manually-installed apps so Homebrew can manage updates
- **Use `brew unlink <formula>`** to quickly remove a formula from PATH without uninstalling it
- **Use `brew exec --formulae=X,Y -- ./script.sh`** for portable scripts that need specific Homebrew tools
- **Use `brew bundle dump` periodically** to snapshot your installed state as a Brewfile backup
- **After macOS upgrades**, run `xcode-select --install && brew upgrade` to fix potential breakage

---

## Troubleshooting

### NEVER run `sudo brew install`

Homebrew is designed for user-level installs. Running `sudo brew install` installs files owned by root, which corrupts Homebrew's permission model and causes cascading failures.

**Symptom**: `Error: The following directories are not writable by your user` after a `sudo brew` run.

**Fix**:
```sh
sudo chown -R $(whoami) $(brew --prefix)
brew doctor  # verify the repair
```

If you need to install something system-wide, use `sudo` on the resulting binary, not on `brew` itself.

### PATH ordering: brew prefix must come first

**Symptom**: `which python` returns `/usr/bin/python` (system) instead of `/opt/homebrew/bin/python`. Tools shadow each other unexpectedly.

**Cause**: `/usr/bin` appears before `/opt/homebrew/bin` in PATH.

**Fix**: Ensure `brew shellenv` is called at the top of `.zshrc` (before any PATH manipulation):

```sh
# .zshrc — must be before anything else that modifies PATH
eval "$(brew shellenv)"
```

Verify: `which brew` should return `/opt/homebrew/bin/brew`, and `echo $PATH` should show `/opt/homebrew/bin` before `/usr/bin`.

### `brew: command not found`

**Fix**: Homebrew is not in PATH. Add to `.zshrc`:

```sh
eval "$(/opt/homebrew/bin/brew shellenv)"  # Apple Silicon
eval "$(/usr/local/bin/brew shellenv)"     # Intel
```

Or run `brew shellenv` and follow the output.

### `Error: No available formula with the name "X"`

**Cause**: Formula is in a tap that isn't added.

**Fix**: Search for it first:

```sh
brew search X
```

If it shows up as `owner/tap/formula`, add the tap first:

```sh
brew tap owner/tap
brew install owner/tap/formula
```

### Cask install fails: "App is already installed"

**Cause**: App was installed manually (not via Homebrew) and is in `/Applications`.

**Fix**:

```sh
brew install --cask --force ghostty  # overwrite the existing app
```

Or use `--adopt` to take ownership of the existing installation without overwriting.

Or move the existing app to Trash first, then install normally.

### `brew upgrade` breaks a tool

**Fix**: Roll back to the previous version:

```sh
brew info ripgrep               # find the version you want
brew install ripgrep@14.1.0    # install old version (if formula exists)
brew pin ripgrep                # prevent future upgrades
```

For casks, most don't support `--version`. Reinstall the old `.dmg` manually and then:

```sh
brew uninstall --cask appname   # let brew take ownership again
```

### Permission denied on `/opt/homebrew`

**Cause**: Homebrew directory ownership issue, usually after a macOS upgrade or accidental `sudo brew`.

**Fix**:

```sh
sudo chown -R $(whoami) /opt/homebrew
brew doctor  # verify no other issues
```

### ARM bottle missing — source compile takes too long

**Cause**: Formula has no pre-built Apple Silicon bottle; must compile from source.

**Symptoms**: `brew install` spawns a compiler and takes 10–30 minutes.

**Options**:
1. Let it compile (fine for one-off installs, annoying in automated deploys)
2. Check if a cask exists instead: `brew search --cask toolname`
3. Use Rosetta 2 to force Intel bottle: `arch -x86_64 brew install formula` (not recommended long-term)

### `brew update` complains about untracked working tree files

**Fix**:
```sh
cd "$(brew --repository)"
git reset --hard FETCH_HEAD

# If brew doctor still complains:
cd "$(brew --repository)/Library"
git clean -fd
```

### Homebrew git repo is in a completely broken state

`brew update-reset` resets Homebrew's internal git repositories to a clean upstream state. Use this when `brew update` keeps failing or the Homebrew repo has become corrupted.

```sh
brew update-reset        # reset homebrew/brew and all taps to upstream HEAD
brew update-reset $(brew --repository)/Library/Taps/homebrew/homebrew-core  # reset a single tap
```

> This is equivalent to `git fetch && git reset --hard origin/HEAD` on each Homebrew repo. It discards any local changes to formula files.

### After a macOS upgrade, tools break with dyld errors

**Fix**:
```sh
xcode-select --install
brew upgrade
```

---

## Related Skills

- [[pyinfra]]: Writing pyinfra deploy scripts that use these Homebrew operations
