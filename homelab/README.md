# Homelab on briareus

This directory manages the Fujitsu ESPRIMO Q556 mini PC called briareus. The
laptop configures it over SSH with pyinfra. The root of the repository still
manages the laptop. This directory only manages the server.

The server has four jobs:

1. Run OpenCode as an always-on server, so agent sessions keep running while
   the laptop is off.
2. Run Claude Code on the same host.
3. Run a small k3s cluster with Argo CD, Pi-hole and a drive replacement.
4. Show fastfetch in every interactive terminal.

## Run

Always run from this directory. Relative paths resolve here, and `import
versions` only works from here.

```sh
cd homelab
uv run pyinfra inventory.py deploy.py --dry   # preview
uv run pyinfra inventory.py deploy.py         # apply
```

Run one section only:

```sh
PHASE=base uv run pyinfra inventory.py deploy.py
```

`PHASE` accepts a section name (`base`, `shell`, `homebrew`, `tailscale`,
`opencode`, `sync`, `backup`, `k3s`, `argocd`), or a group: `v1` (the default,
phases 0 to 6), `v2` (the cluster), or `all`.

Never run the deploy from the repository root. From there `files/x` silently
picks the laptop file and the task modules are not found.

## Order

v1 first, use it for a week, then v2.

- v1, the agent server: base system, Homebrew, Tailscale, OpenCode service.
  This is phases 0 to 6 of the plan.
- v2, the cluster: k3s, Argo CD, apps, backups of cluster data, docs.

The module list under `tasks/` matches the plan. `k3s`, `argocd` and `secrets`
are placeholders until v2 starts.

## Secrets

`homelab/.env` holds the server values and is gitignored. The repository root
`.env` holds the laptop values. Never copy work tokens into this file.

Read `docs/bootstrap.md` before the first run. Read `docs/runbook.md` before an
upgrade or a restore.
