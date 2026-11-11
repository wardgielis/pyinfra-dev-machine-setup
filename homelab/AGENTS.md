# Rules for agents editing the homelab code

These rules apply to every file under `homelab/`.

## Running

- Run from `homelab/`: `cd homelab && uv run pyinfra inventory.py deploy.py`.
  From the repository root, `files/x` resolves to the laptop tree and the task
  modules are not found.
- Preview with `--dry` before a real run, and again before any change to sshd,
  swap, the resolver or the network.
- Run the same section twice. The second run must report no changes. Every
  `server.shell` needs a guard, or it must be listed as an accepted exception in
  `docs/runbook.md`.

## Code rules

- Do not move the laptop `deploy.py`. pyinfra resolves `files.put(src=...)` and
  `local.include()` from the working directory.
- Never set `config.SUDO` globally. Homebrew must never run as root. Put
  `_sudo=True` on each apt, systemd and file operation that needs it.
- Pin every remote version in `versions.py`. The one exception is the
  `claude-code` brew cask, which cannot be pinned; record its version in the
  runbook.
- Never add `brew.upgrade` or `brew.cask_upgrade`. An upgrade can restart the
  agent and kill a running session.
- Never run `brew uninstall --cask --zap claude-code`. It deletes the login.
- Chart versions live in `homelab/k8s/apps/`, not in `versions.py`.
- Set `_env` with the Homebrew PATH on every operation that calls `brew`, `helm`
  or `kubectl`. Non-interactive SSH shells do not have `brew` on PATH.
- Keep the shared OpenCode config in one file. Both targets render
  `files/opencode_config.jsonc`; only the MCP block and the skills path differ.

## Security

- The repository is public. No secret goes into git, ever. Only
  `homelab/.env` may hold one.
- The agent user has no sudo and no repository write key. Do not add one.
- The systemd sandbox in `files/opencode.service.j2` is the security boundary for
  the agent. The permission policy is not.

## Text

- Docstrings and comments follow the plain-english skill: short sentences,
  active voice, no backticks, no em dashes.
