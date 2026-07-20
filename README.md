 # pyinfra-dev-machine-setup

A [Pyinfra](https://pyinfra.com) managed repository to bootstrap a modern development machine. Uses Homebrew as the package backend and deploys a ZSH-based shell configuration — works on macOS.

## Prerequisites

- [ZSH](https://www.zsh.org/)
- [Homebrew](https://brew.sh/)
- [uv](https://docs.astral.sh/uv/) — Python package manager
- [Bitwarden](https://bitwarden.com/) — desktop app installed and logged in (used to fetch the Jira API token)

## Quickstart

**1. Clone and install dependencies**

```sh
uv sync
```

**2. Create your `.env` file**

```sh
cp .env.example .env
```

Fill in `.env` with your values:

```
BW_SSO_ORG=YourOrg               # Bitwarden SSO organization name
JIRA_LOGIN=you@company.com        # Your Jira email
JIRA_SERVER=https://your-org.atlassian.net
JIRA_PROJECT_KEY=YOURKEY          # Default Jira project key
```

**3. Set up Bitwarden**

The deploy fetches your Jira API token from Bitwarden. Make sure you have:
- A Bitwarden login item named exactly `jira-cli` with the API token as its password
- Touch ID unlock enabled in the Bitwarden desktop app (Settings → Security) for a seamless experience

**4. Run the deploy**

```sh
uv run pyinfra @local deploy.py
```

## What it does

- **GUI Apps & Fonts** — Ghostty terminal, VSCodium, Bruno API client, JetBrains Mono Nerd Font, Bitwarden, Obsidian
- **Work CLI Tools** — Databricks CLI, AWS CLI, OpenBao (Vault drop-in), OpenTofu (Terraform drop-in), Jira CLI, prek
- **Coding agents** — OpenCode, Mistral Vibe
- **Modern CLI replacements** — eza, bat, zoxide, ripgrep, fd, fastfetch, dust, btop, procs, lazygit, git-delta, gitleaks, git-filter-repo, gh, glab, mise, direnv, atuin, starship, antidote, viu, lsix, yazi, tealdeer, television, trash-cli, dysk, yq, lazydocker, k9s, kubectx, kubectl, helm, micro
- **Shell configuration** — daily brew auto-update on first terminal open, Starship prompt, Ghostty config, ZSH plugins (autosuggestions, syntax highlighting, completions via Antidote), aliases mapping classic commands to modern replacements
- **Secret management** — fetches Jira API token from Bitwarden and writes it to `~/.secrets`
- **Drift cleanup** — generates a Brewfile from the managed package lists, shows a preview of unmanaged packages, and removes them after your confirmation
- **Housekeeping** — silences macOS "Last Login" message, renders Jira CLI config from `.env` template

## Customizing

All managed packages are defined as named lists at the top of `deploy.py` — that same list drives both installation and drift cleanup, so there's a single source of truth. Add/remove packages there, drop config templates into `files/`, and re-run the deploy.
