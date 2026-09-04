import io
import os
import pathlib
import shutil
import string
from pyinfra.operations import brew, files, python, server


def _deploy_template(dest, template_name, varnames, mode=None):
    missing = [v for v in varnames if v not in os.environ]
    if missing:
        raise SystemExit(f"Missing env vars for {dest}: {', '.join(missing)} — add them to .env")
    rendered = string.Template(
        (pathlib.Path(__file__).parent / "files" / template_name).read_text()
    ).substitute(**{v: os.environ[v] for v in varnames})
    files.put(
        name=f"Sync {dest}",
        src=io.StringIO(rendered),
        dest=os.path.expanduser(dest),
        mode=mode,
    )


# ============================================================
# BOOTSTRAP: Load local .env (gitignored, never committed)
# ============================================================
_env_path = pathlib.Path(__file__).parent / ".env"
_env_example_path = pathlib.Path(__file__).parent / ".env.example"

if not _env_path.exists():
    shutil.copy(_env_example_path, _env_path)
    raise SystemExit(
        ".env not found — created one from .env.example.\n"
        "Fill in your values and re-run: uv run pyinfra @local deploy.py"
    )

for _line in _env_path.read_text().splitlines():
    _line = _line.strip()
    if _line and not _line.startswith("#") and "=" in _line:
        _k, _v = _line.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

# ============================================================
# DATA: All managed packages — single source of truth
# Packages defined here are installed AND protected from cleanup.
# Anything in brew but NOT listed below will be flagged for removal.
# ============================================================

TAPS = [
    "anomalyco/tap",
    "databricks/tap",
]

# ============================================================
# TAP TRUST: Ensure taps are trusted before installing packages.
# Uses os.system (real TTY) so brew can process the confirmation.
# ============================================================
for _tap in TAPS:
    os.system(f"brew trust {_tap} 2>/dev/null")

PERSONAL_CASKS = [
    "league-of-legends",  # Games
    "claude",             # Anthropic desktop app
    "brave-browser",      # Privacy-focused browser
    "spotify",            # Music streaming
    "logi-options+",      # Logitech mouse/keyboard software
    "ente-auth",          # 2FA authenticator
    "ilok-license-manager", # Audio plugin licenses
]

EVAL_CASKS = [          # Trying these out — promote or drop as needed
    "zen",
    "keepingyouawake",
    "headlamp",         # docker desktop equivalent for k8s
]

GUI_CASKS = [
    "ghostty",
    "vscodium",
    "bruno",
    "font-jetbrains-mono-nerd-font",
    "bitwarden",
    "obsidian",
    "opencode-desktop",

    # Opensource macos cleanup tool
    "puremac",

    # Communication tools
    "mattermost",
    "whatsapp",
    "signal",

    # Music
    "reaper",

    # Video editing
    "kdenlive",

    # Container management (replaces Docker Desktop)
    "podman-desktop",

    # JetBrains IDE manager
    "jetbrains-toolbox",
]

CODING_FORMULAE = [
    "anomalyco/tap/opencode",  # Installing opencode via tap gives the quickest updates
    "mistral-vibe",            # Mistral's vibe coding agent — evaluating alongside opencode
]

WORK_FORMULAE = [
    "databricks",
    "awscli",
    "openbao",   # Drop-in replacement for HashiCorp Vault (alias keeps 'vault' command working)
    "jira-cli",  # Feature-rich interactive Jira CLI (ankitpokhrel/jira-cli)
    "opentofu",  # Open source and drop-in replacement for terraform
    "prek",
]

CLI_FORMULAE = [
    # Core replacements
    "eza",        # Better ls
    "bat",        # Better cat
    "zoxide",     # Better cd
    "ripgrep",    # Better grep
    "fd",         # Better find
    "fastfetch",  # System info
    # System monitors
    "dust",       # Better du
    "btop",       # Better top
    "procs",      # Better ps
    # Git & Dev Environment
    "lazygit",         # TUI for Git
    "git-delta",       # Syntax-highlighted diffs (integrates with git, lazygit, bat)
    "gitleaks",        # Scan repos for accidentally committed secrets
    "git-filter-repo", # Rewrite/clean git history (remove files, sensitive data)
    "gh",         # GitHub CLI
    "glab",       # GitLab CLI
    "mise",       # Polyglot runtime manager (Node, Python, etc.)
    "direnv",     # Per-project environment variables
    # Shell essentials
    "atuin",      # Shell history
    "starship",   # Prompt (beautiful terminal!)
    "antidote",   # Plugin manager
    # Terminal Image & Media Tools
    "viu",        # Rust-based image viewer (like 'cat' for images)
    "lsix",       # Grid-based 'ls' for images
    "yazi",       # Rust-based terminal file manager (with image previews)
    # Extra tools that Bluefin uses
    "tealdeer",   # Better man pages (tldr)
    "television", # Bluefin's preferred fuzzy finder (replaces fzf)
    "trash-cli",  # Safe 'rm' alternative
    "dysk",       # Better disk/mount info
    "yq",         # YAML processor
    # Container & Cluster Tools
    "podman",         # Docker-compatible container runtime (rootless, daemonless)
    "podman-compose", # docker-compose compatible (aliased as docker-compose in zshrc)
    "lazydocker",  # TUI for Docker
    "k9s",         # TUI for Kubernetes
    "kubectx",     # Fast K8s context/namespace switching
    "kubectl",     # Kubernetes CLI
    "helm",        # Kubernetes package manager
    # Modern Text Editor
    "micro",  # nano replacement using nano as alias
]

# ============================================================
# SECTION 1: TAPS & TRUST
# Both taps must be declared and trusted before any packages
# from those taps are installed.
# ============================================================
brew.tap(name="Tap AnomalyCo Opencode", src="anomalyco/tap")
brew.tap(name="Tap Databricks", src="databricks/tap")

server.shell(
    name="Trust managed taps",
    commands=[f"brew trust {t}" for t in TAPS],
)


# ============================================================
# SECTION 2: GUI APPS, FONTS & WORKSPACE
# ============================================================
brew.casks(
    name="Personal Apps",
    casks=PERSONAL_CASKS,
    upgrade=False,
)

brew.casks(
    name="Temporary apps under evaluation — promote or drop as needed.",
    casks=EVAL_CASKS,
)

brew.casks(
    name="Install GUI Apps, Fonts and tools",
    casks=GUI_CASKS,
)


# ============================================================
# SECTION 3: Coding Agents
# ============================================================
brew.packages(
    name="Install Coding Agents",
    packages=CODING_FORMULAE,
    update=True,
    latest=True,
)


# ============================================================
# SECTION 4: WORK CLI TOOLS (OpenBao & Databricks)
# ============================================================
brew.packages(
    name="Install Work CLI Tools",
    packages=WORK_FORMULAE,
    latest=True,
)


# ============================================================
# SECTION 5: MODERN TERMINAL (The Rust-based "Bluefin" Set)
# ============================================================
brew.packages(
    name="Install modern CLI tools",
    packages=CLI_FORMULAE,
    latest=True,
)


# ============================================================
# SECTION 6: CONFIG DEPLOYMENT
# ============================================================
# Ensure directories exist
config_dirs = [
    "~/.config/ghostty",
    "~/.config/starship",
    "~/.config/.jira",
    "~/.aws",
]

for d in config_dirs:
    files.directory(
        name=f"Ensure directory exists: {d}",
        path=os.path.expanduser(d),
        present=True,
    )

# Deploy Configuration Files
configs_to_sync = {
    "files/zshrc": "~/.zshrc",
    "files/zsh_plugins.txt": "~/.zsh_plugins.txt",
    "files/starship.toml": "~/.config/starship.toml",
    "files/ghostty_config": "~/.config/ghostty/config",
}

for src, dest in configs_to_sync.items():
    files.put(
        name=f"Sync {dest}",
        src=src,
        dest=os.path.expanduser(dest),
    )

files.put(
    name="Sync ~/.brew_tap_trust",
    src=io.StringIO("\n".join(f"brew trust {t} 2>/dev/null || true" for t in TAPS) + "\n"),
    dest=os.path.expanduser("~/.brew_tap_trust"),
)

_template_configs = [
    ("~/.secrets", "secrets", ["JIRA_API_TOKEN"], "0600"),
    ("~/.config/.jira/.config.yml", "jira_config", [
        "JIRA_LOGIN", "JIRA_SERVER", "JIRA_PROJECT_KEY", "JIRA_BOARD_ID",
    ], None),
    ("~/.databrickscfg", "databrickscfg", [
        "DATABRICKS_DEV_HOST", "DATABRICKS_PROD_HOST", "DATABRICKS_ACCOUNT_ID",
        "DATABRICKS_DEV_WORKSPACE_ID", "DATABRICKS_PROD_WORKSPACE_ID",
    ], None),
    ("~/.aws/config", "aws_config", [
        "AWS_ACCOUNT_ID", "AWS_LOGIN_EMAIL",
        "AWS_AIRFLOW_PROD_ACCESS_KEY_ID", "AWS_AIRFLOW_PROD_SECRET_ACCESS_KEY",
        "AWS_AIRFLOW_DEV_ACCESS_KEY_ID", "AWS_AIRFLOW_DEV_SECRET_ACCESS_KEY",
    ], "0600"),
]

for _dest, _tmpl, _vars, _mode in _template_configs:
    _deploy_template(_dest, _tmpl, _vars, _mode)

# Hush the macOS "Last Login" message (remove it as it is pretty ugly)
files.file(
    name="Hush macOS last login message",
    path=os.path.expanduser("~/.hushlogin"),
    present=True,
)


# ============================================================
# SECTION 7: CLEANUP UNMANAGED PACKAGES
# Generates a Brewfile from the lists above, shows a dry-run
# preview of what would be removed, and asks for confirmation
# before actually removing anything.
# ============================================================
def _short_name(f):
    parts = f.split("/")
    return parts[-1] if len(parts) == 3 else f

_brewfile_lines = (
    [f'tap "{t}"' for t in TAPS]
    + [f'brew "{_short_name(f)}"' for f in CODING_FORMULAE + WORK_FORMULAE + CLI_FORMULAE]
    + [f'cask "{c}"' for c in PERSONAL_CASKS + EVAL_CASKS + GUI_CASKS]
)

files.put(
    name="Write managed Brewfile for drift cleanup",
    src=io.StringIO("\n".join(_brewfile_lines) + "\n"),
    dest="/tmp/pyinfra-managed-brewfile",
)

_user_confirmed = [False]


def _preview_and_confirm():
    import subprocess
    for _tap in TAPS:
        os.system(f"brew trust {_tap} 2>/dev/null")
    print("\n--- Brew drift preview (packages not in deploy.py) ---")
    subprocess.run(
        ["brew", "bundle", "cleanup", "--file=/tmp/pyinfra-managed-brewfile"]
    )
    print()
    response = input("Proceed with removal? [y/N] ")
    _user_confirmed[0] = response.lower() == "y"


python.call(
    name="Preview packages to remove",
    function=_preview_and_confirm,
)

server.shell(
    name="Remove packages not in deploy.py",
    commands=[
        *[f"brew trust {t} 2>/dev/null || true" for t in TAPS],
        "brew bundle cleanup --force --file=/tmp/pyinfra-managed-brewfile",
        "brew autoremove",
    ],
    _if=lambda: _user_confirmed[0],
)


# ============================================================
# SECTION 8: OPENCODE CONFIG
# ============================================================
_deploy_dir = str(pathlib.Path(__file__).resolve().parent)
os.environ.setdefault(
    "OPENCODE_SKILLS_PATH",
    os.path.join(_deploy_dir, "opencode-config", "skills"),
)

files.directory(
    name="Ensure ~/.config/opencode exists",
    path=os.path.expanduser("~/.config/opencode"),
    present=True,
)

_deploy_template(
    "~/.config/opencode/opencode.jsonc",
    "opencode_config.jsonc",
    ["OPENCODE_SKILLS_PATH"],
)

files.put(
    name="Sync OpenCode AGENTS.md",
    src=str(pathlib.Path(__file__).parent / "files" / "opencode_agents.md"),
    dest=os.path.expanduser("~/.config/opencode/AGENTS.md"),
)

files.put(
    name="Sync OpenCode package.json",
    src=str(pathlib.Path(__file__).parent / "opencode-config" / "package.json"),
    dest=os.path.expanduser("~/.config/opencode/package.json"),
)

server.shell(
    name="Install OpenCode plugins",
    commands=["cd ~/.config/opencode && npm install --silent"],
    _if=lambda: not os.path.exists(
        os.path.expanduser("~/.config/opencode/node_modules")
    ),
)

files.directory(
    name="Ensure ~/.config/opencode/plugins exists",
    path=os.path.expanduser("~/.config/opencode/plugins"),
    present=True,
)

files.put(
    name="Sync skill-freshness plugin",
    src=str(pathlib.Path(__file__).parent / "opencode-config" / "plugins" / "skill-freshness.ts"),
    dest=os.path.expanduser("~/.config/opencode/plugins/skill-freshness.ts"),
)


# ============================================================
# SECTION 9: REAPER CONFIG
# ============================================================
_reaper_dir = os.path.expanduser("~/Library/Application Support/REAPER")

files.directory(
    name="Ensure REAPER ColorThemes dir exists",
    path=os.path.join(_reaper_dir, "ColorThemes"),
    present=True,
)

files.put(
    name="Sync Reapertips theme",
    src=str(pathlib.Path(__file__).parent / "reaper-config" / "ColorThemes" / "Reapertips Theme.ReaperThemeZip"),
    dest=os.path.join(_reaper_dir, "ColorThemes", "Reapertips Theme.ReaperThemeZip"),
)

files.put(
    name="Sync reaper-themeconfig.ini",
    src=str(pathlib.Path(__file__).parent / "reaper-config" / "reaper-themeconfig.ini"),
    dest=os.path.join(_reaper_dir, "reaper-themeconfig.ini"),
)

files.put(
    name="Sync reaper-mouse.ini",
    src=str(pathlib.Path(__file__).parent / "reaper-config" / "reaper-mouse.ini"),
    dest=os.path.join(_reaper_dir, "reaper-mouse.ini"),
)



# ============================================================
# SECTION 10: MACOS SYSTEM PREFERENCES (GNOME-LIKE SETUP)
# ============================================================

server.shell(
    name="Configure Dock (GNOME-like)",
    commands=[
        # Auto-hide the Dock — like GNOME's hidden bottom bar
        "defaults write com.apple.dock autohide -bool true",
        # Don't show recent apps in Dock
        "defaults write com.apple.dock show-recents -bool false",
        # Faster Dock show/hide animation (snappier like GNOME)
        "defaults write com.apple.dock autohide-delay -float 0.0",
        "defaults write com.apple.dock autohide-time-modifier -float 0.4",
        # Faster Mission Control / Expose animation
        "defaults write com.apple.dock expose-animation-duration -float 0.1",
        # Don't auto-rearrange Spaces — GNOME keeps workspaces in fixed order
        "defaults write com.apple.dock mru-spaces -bool false",
        # Hot corner: top-left = Mission Control (like GNOME Activities overview)
        "defaults write com.apple.dock wvous-tl-corner -int 2",
        "defaults write com.apple.dock wvous-tl-modifier -int 0",
        "killall Dock",
    ],
)

server.shell(
    name="Configure Finder (GNOME-like)",
    commands=[
        # Show hidden files — Linux default behavior
        "defaults write com.apple.finder AppleShowAllFiles -bool true",
        # List view as default — closer to Nautilus list view
        "defaults write com.apple.finder FXPreferredViewStyle -string 'Nlsv'",
        # Show external drives on Desktop
        "defaults write com.apple.finder ShowExternalHardDrivesOnDesktop -bool true",
        "killall Finder",
    ],
)

server.shell(
    name="Configure global macOS settings (GNOME-like)",
    commands=[
        # Dark mode
        "defaults write NSGlobalDomain AppleInterfaceStyle -string 'Dark'",
        # Double-click title bar maximizes window — GNOME default behavior
        "defaults write NSGlobalDomain AppleActionOnDoubleClick -string 'Maximize'",
        # Disable swipe back/forward in browsers (conflicts with workspace gestures)
        "defaults write NSGlobalDomain AppleEnableSwipeNavigateWithScrolls -bool false",
        # Always use tabs when opening documents
        "defaults write NSGlobalDomain AppleWindowTabbingMode -string 'always'",
        # Full keyboard access — Tab cycles through all UI controls, not just text fields
        "defaults write NSGlobalDomain AppleKeyboardUIMode -int 3",
        # Faster key repeat — Linux/GNOME terminal feel
        "defaults write NSGlobalDomain KeyRepeat -int 2",
        "defaults write NSGlobalDomain InitialKeyRepeat -int 25",
        # Disable automatic window animations (snappier)
        "defaults write NSGlobalDomain NSAutomaticWindowAnimationsEnabled -bool false",
        # Custom menu keyboard shortcuts: Cmd+L = Lock Screen, Cmd+. = Emoji & Symbols
        "defaults write NSGlobalDomain NSUserKeyEquivalents -dict-add 'Lock Screen' '@l' 'Emoji & Symbols' '@.'",
    ],
)

server.shell(
    name="Configure trackpad (GNOME-like)",
    commands=[
        # Tap to click — common on Linux trackpads
        "defaults write com.apple.AppleMultitouchTrackpad Clicking -bool true",
        "defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad Clicking -bool true",
        # Three-finger drag to move windows — closest to GNOME's Super+drag-to-move
        "defaults write com.apple.AppleMultitouchTrackpad TrackpadThreeFingerDrag -bool true",
        "defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad TrackpadThreeFingerDrag -bool true",
    ],
)
