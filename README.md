 # pyinfra-dev-machine-setup

A [Pyinfra](https://pyinfra.com) managed repository to bootstrap a modern development machine. Uses Homebrew as the package backend and deploys a ZSH-based shell configuration — works on macOS.

## Prerequisites

- [ZSH](https://www.zsh.org/)
- [Homebrew](https://brew.sh/)
- [uv](https://docs.astral.sh/uv/) — Python package manager

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
JIRA_LOGIN=you@company.com
JIRA_SERVER=https://your-org.atlassian.net
JIRA_PROJECT_KEY=YOURKEY
JIRA_BOARD_ID=65
JIRA_API_TOKEN=your_jira_api_token   # generate at id.atlassian.com → Security → API tokens

DATABRICKS_DEV_HOST=https://your-dev-workspace.cloud.databricks.com
DATABRICKS_PROD_HOST=https://your-prod-workspace.cloud.databricks.com
DATABRICKS_ACCOUNT_ID=your-account-uuid
DATABRICKS_DEV_WORKSPACE_ID=your-dev-workspace-id
DATABRICKS_PROD_WORKSPACE_ID=your-prod-workspace-id

AWS_ACCOUNT_ID=your-aws-account-id
AWS_LOGIN_EMAIL=you@yourorg.com
AWS_AIRFLOW_PROD_ACCESS_KEY_ID=...
AWS_AIRFLOW_PROD_SECRET_ACCESS_KEY=...
AWS_AIRFLOW_DEV_ACCESS_KEY_ID=...
AWS_AIRFLOW_DEV_SECRET_ACCESS_KEY=...
```

**3. Run the deploy**

```sh
uv run pyinfra @local deploy.py
```

## What it does

- **GUI Apps & Fonts** — Ghostty terminal, VSCodium, Bruno API client, JetBrains Mono Nerd Font, Bitwarden, Obsidian
- **Work CLI Tools** — Databricks CLI, AWS CLI, OpenBao (Vault drop-in), OpenTofu (Terraform drop-in), Jira CLI, prek
- **Coding agents** — OpenCode, Mistral Vibe
- **Modern CLI replacements** — eza, bat, zoxide, ripgrep, fd, fastfetch, dust, btop, procs, lazygit, git-delta, gitleaks, git-filter-repo, gh, glab, mise, direnv, atuin, starship, antidote, viu, lsix, yazi, tealdeer, television, trash-cli, dysk, yq, lazydocker, k9s, kubectx, kubectl, helm, micro
- **Shell configuration** — daily brew auto-update on first terminal open, Starship prompt, Ghostty config, ZSH plugins (autosuggestions, syntax highlighting, completions via Antidote), aliases mapping classic commands to modern replacements
- **Config deployment** — renders Jira, Databricks, and AWS config files from `.env` templates and deploys them to their expected locations (`~/.config/.jira/.config.yml`, `~/.databrickscfg`, `~/.aws/config`); writes `JIRA_API_TOKEN` to `~/.secrets` for shell sourcing
- **Drift cleanup** — generates a Brewfile from the managed package lists, shows a preview of unmanaged packages, and removes them after your confirmation
- **Housekeeping** — silences macOS "Last Login" message, renders Jira CLI config from `.env` template

## Customizing

All managed packages are defined as named lists at the top of `deploy.py` — that same list drives both installation and drift cleanup, so there's a single source of truth. Add/remove packages there, drop config templates into `files/`, and re-run the deploy.
