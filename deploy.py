import io
import os
import pathlib
import shutil
import string
from pyinfra.operations import brew, files, python, server

from bitwarden_secrets import write_secret

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

PERSONAL_CASKS = [
    "league-of-legends",  # Games
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

    # Opensource macos cleanup tool
    "puremac",

    # Communication tools
    "mattermost",
    "whatsapp",
    "signal",

    # Music
    "reaper",
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
    "lazydocker",  # TUI for Docker
    "k9s",         # TUI for Kubernetes
    "kubectx",     # Fast K8s context/namespace switching
    "kubectl",     # Kubernetes CLI
    "helm",        # Kubernetes package manager
    # Modern Text Editor
    "micro",  # nano replacement using nano as alias
]

# Installed by side-effects (not via brew.packages/brew.casks) but still managed
# here so the cleanup step doesn't flag them for removal.
_SIDEEFFECT_FORMULAE = ["bitwarden-cli"]  # installed by bitwarden_secrets.py if missing
_SIDEEFFECT_CASKS    = ["docker-desktop"] # installed via os.system below if docker absent


# ============================================================
# SECTION 0: SECRET MANAGEMENT
# ============================================================
write_secret("jira-cli", "JIRA_API_TOKEN")

# Docker Desktop needs os.system for the launchctl sudo prompt (only if not installed)
if not shutil.which("docker"):
    print("Installing docker-desktop...")
    os.system("brew install --cask docker-desktop")


# ============================================================
# SECTION 0.5: TAPS & TRUST
# Both taps must be declared and trusted before any packages
# from those taps are installed.
# ============================================================
brew.tap(name="Tap AnomalyCo Opencode", src="anomalyco/tap")
brew.tap(name="Tap Databricks", src="databricks/tap")

server.shell(
    name="Trust all managed taps",
    commands=[f"brew trust {t}" for t in TAPS],
)


# ============================================================
# SECTION 1: GUI APPS, FONTS & WORKSPACE
# ============================================================
brew.casks(
    name="Personal Apps",
    casks=PERSONAL_CASKS,
    upgrade=False,
)

brew.casks(
    name="Temporary apps that im evaluation, if i like it move to another section.",
    casks=EVAL_CASKS,
)

brew.casks(
    name="Install GUI Apps, Fonts and tools",
    casks=GUI_CASKS,
)


# ============================================================
# SECTION 2: Coding Agents
# ============================================================
brew.packages(
    name="Install Coding Agents",
    packages=CODING_FORMULAE,
    update=True,
    latest=True,
)


# ============================================================
# SECTION 3: WORK CLI TOOLS (OpenBao & Databricks)
# ============================================================
brew.packages(
    name="Install Work CLI Tools",
    packages=WORK_FORMULAE,
    update=True,
    latest=True,
)


# ============================================================
# SECTION 4: MODERN TERMINAL (The Rust-based "Bluefin" Set)
# ============================================================
brew.packages(
    name="Install modern CLI tools",
    packages=CLI_FORMULAE,
    update=True,
    latest=True,
)


# ============================================================
# SECTION 5: CONFIG DEPLOYMENT
# ============================================================
# Ensure directories exist
config_dirs = [
    "~/.config/ghostty",
    "~/.config/starship",
    "~/.config/.jira",
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

# Render and deploy jira config from template + .env values
_jira_rendered = string.Template(
    (pathlib.Path(__file__).parent / "files" / "jira_config").read_text()
).substitute(
    JIRA_LOGIN=os.environ["JIRA_LOGIN"],
    JIRA_SERVER=os.environ["JIRA_SERVER"],
    JIRA_PROJECT_KEY=os.environ["JIRA_PROJECT_KEY"],
)

files.put(
    name="Sync ~/.config/.jira/.config.yml",
    src=io.StringIO(_jira_rendered),
    dest=os.path.expanduser("~/.config/.jira/.config.yml"),
)

# Hush the macOS "Last Login" message (remove it as it is pretty ugly)
files.file(
    name="Hush macOS last login message",
    path=os.path.expanduser("~/.hushlogin"),
    present=True,
)


# ============================================================
# SECTION 6: CLEANUP UNMANAGED PACKAGES
# Generates a Brewfile from the lists above, shows a dry-run
# preview of what would be removed, and asks for confirmation
# before actually removing anything.
# ============================================================
def _short_name(f):
    parts = f.split("/")
    return parts[-1] if len(parts) == 3 else f

_brewfile_lines = (
    [f'tap "{t}"' for t in TAPS]
    + [f'brew "{_short_name(f)}"' for f in CODING_FORMULAE + WORK_FORMULAE + CLI_FORMULAE + _SIDEEFFECT_FORMULAE]
    + [f'cask "{c}"' for c in PERSONAL_CASKS + EVAL_CASKS + GUI_CASKS + _SIDEEFFECT_CASKS]
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
        subprocess.run(["brew", "trust", _tap], capture_output=True)
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
        "brew bundle cleanup --force --file=/tmp/pyinfra-managed-brewfile",
        "brew autoremove",
    ],
    _if=lambda: _user_confirmed[0],
)
