import os
import shutil
from pyinfra.operations import brew, files

from bitwarden_secrets import write_secret

# --- SECTION 0: SECRET MANAGEMENT ---
write_secret("jira-cli", "JIRA_API_TOKEN")

# Docker Desktop needs os.system for the launchctl sudo prompt (only if not installed)
if not shutil.which("docker"):
    print("Installing docker-desktop...")
    os.system("brew install --cask docker-desktop")

# --- SECTION 1: GUI APPS, FONTS & WORKSPACE ---
brew.casks(
    name="Temporary apps that im evaluation, if i like it move to another section.",
    casks=[
        "zen",
        "keepingyouawake",
        "headlamp", # docker desktop equivalent for k8s
    ],
    upgrade=True,
)

brew.casks(
    name="Install GUI Apps, Fonts and tools",
    casks=[
        "ghostty",
        "vscodium",
        "bruno",
        "font-jetbrains-mono-nerd-font",
        "bitwarden",
        "obsidian",

        # Communication tools
        "mattermost",
        "whatsapp",
        "signal",
    ],
    upgrade=True,
)

# --- SECTION 1.5: AUTO-UPDATE (daily brew updates via launchd) ---
if not os.path.exists(os.path.expanduser("~/Library/LaunchAgents/homebrew.autoupdate.plist")):
    print("Enabling daily brew auto-updates...")
    os.system("brew tap homebrew/autoupdate && brew autoupdate start 86400 --cleanup")

# --- SECTION 2: Coding Agents
brew.tap(name="Tap AnomalyCo Opencode", src="anomalyco/tap")
brew.packages(
    name="Install Coding Agents",
    packages=[
        "anomalyco/tap/opencode", # Installing opencode via tap gives the quickest updates
        "mistral-vibe", # Still comparing vibe and opencode, might remove later
    ],
    update=True,
)

# --- SECTION 3: WORK CLI TOOLS (OpenBao & Databricks) ---
brew.tap(name="Tap Databricks", src="databricks/tap")

brew.packages(
    name="Install Work CLI Tools",
    packages=[
        "wireguard-tools", # to use EDUVPN without installing the eduvpn client
        "databricks",
        "awscli",
        "openbao",  # Successor to Vault for Naturalis keyvault (we use alias so we can still use vault command)
        "jira-cli", # Feature-rich interactive Jira CLI (ankitpokhrel/jira-cli)
        "opentofu", # Open source and drop-in replacement for terraform
    ],
    update=True,
)

# --- SECTION 4: MODERN TERMINAL (The Rust-based "Bluefin" Set) ---
brew.packages(
    name="Install modern CLI tools",
    packages=[
        # Core replacements
        "eza",        # Better lss
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
        "lazygit",    # TUI for Git
        "gh",         # GitHub CLI
        "glab",       # GitLab CLI
        "mise",       # Polyglot runtime manager (Node, Python, etc.)
        "direnv",       # Per-project environment variables
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
        "k9s",  # TUI for Kubernetes
        "kubectx",  # Fast K8s context/namespace switching
        "kubectl", # Kubernetes CLI
        "helm", # Kubernetes package manager
        # Modern Text Editor
        "micro",  # nano replacement using nano as alias
    ],
    update=True,
)

# --- SECTION 5: CONFIG DEPLOYMENT ---
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

# 3. Deploy Configuration Files
# (Assuming you have a 'files/' directory next to your deploy.py containing these configs)
configs_to_sync = {
    "files/zshrc": "~/.zshrc",
    "files/zsh_plugins.txt": "~/.zsh_plugins.txt",
    "files/starship.toml": "~/.config/starship.toml",
    "files/ghostty_config": "~/.config/ghostty/config",
    "files/jira_config": "~/.config/.jira/.config.yml",
}

for src, dest in configs_to_sync.items():
    files.put(
        name=f"Sync {dest}",
        src=src,
        dest=os.path.expanduser(dest),
    )

# 4. Hush the macOS "Last Login" message (remove it as it is pretty ugly)
files.file(
    name="Hush macOS last login message",
    path=os.path.expanduser("~/.hushlogin"),
    present=True,
)