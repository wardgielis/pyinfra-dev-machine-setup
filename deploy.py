import os
from pyinfra.operations import brew, files

# --- SECTION 1: GUI APPS, FONTS & WORKSPACE ---
brew.casks(
    name="Install GUI Apps, Fonts and tools",
    casks=[
        "ghostty",
        "vscodium",
        "bruno",
        "font-jetbrains-mono-nerd-font",
    ],
    upgrade=True,
)

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
        "databricks",
        "awscli",
        "openbao",  # Successor to Vault for Naturalis keyvault (we use alias so we can still use vault command)
        "jira-cli", # Feature-rich interactive Jira CLI (ankitpokhrel/jira-cli)
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
        "k9s",  # TUI for Kubernetes
        "kubectx",  # Fast K8s context/namespace switching
        "kubectl", # Kubernetes CLI
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