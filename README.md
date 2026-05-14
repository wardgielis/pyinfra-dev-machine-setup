 # pyinfra-dev-machine-setup

A [Pyinfra](https://pyinfra.com) managed repository to bootstrap a modern development machine. Uses Homebrew as the package backend and deploy ZSH-based shell configuration — works on macOS and Linux.

## Prerequisites

- [ZSH](https://www.zsh.org/)
- [Homebrew](https://brew.sh/)

## Quickstart

```sh
# Install dependencies
uv sync

# Apply the full setup to the local machine
uv run pyinfra @local deploy.py
```

## What it does

The `deploy.py` script automates:

- **GUI Apps & Fonts** — Ghostty terminal, VSCodium, Bruno API client, JetBrains Mono Nerd Font
- **Work CLI Tools** — Databricks CLI, AWS CLI, OpenBao (Vault successor)
- **Modern CLI replacements** — eza, bat, zoxide, ripgrep, fd, fastfetch, dust, btop, procs, lazygit, gh, glab, mise, direnv, atuin, starship, antidote, viu, lsix, yazi, tealdeer, television, trash-cli, dysk, yq, lazydocker, k9s, kubectx, micro
- **Shell configuration** — Starship prompt, Ghostty terminal config, ZSH plugins (autosuggestions, syntax highlighting, completions via Antidote), aliases mapping classic commands to modern replacements
- **Housekeeping** — Silences macOS "Last Login" message

## Customizing

Edit `deploy.py` to add/remove packages or configuration files. Drop config templates into `files/`.
