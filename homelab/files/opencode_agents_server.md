## This server: briareus

This host is briareus, a small home server that runs OpenCode for its owner. You run
as the user `agent`, without sudo, inside a systemd sandbox.

### Where things are

- The workspace is `/home/agent/dev`. Each repository is a folder there, for example
  `/home/agent/dev/biocloud-core`. Work in those folders.
- `/home/agent` is your home folder. Files outside `/home/agent` are read-only.
- The sandbox hides `/srv`, the k3s files and `/etc/opencode-secrets`.
- The skills are in `/opt/opencode-skills`. They are read-only. Tracked skills come
  from the public repository on a daily timer. Some org skills are copied by hand.

### Network

- The LAN and the cluster address ranges are blocked. Loopback and the internet work.
- The resolver is the router.
- The Naturalis ClickHouse servers are reached through local tunnels. Production is on
  127.0.0.1:8123 and development is on 127.0.0.1:8124. The tunnels need the Naturalis
  eduVPN link, which a person must renew about every 90 days. When a ClickHouse tool
  fails, report that the link or a tunnel may be down. Do not try to restart it.
- You hold no SSH key. The Naturalis key belongs to a separate user that you cannot
  read. Do not look for it and do not ask for it.
- The ClickHouse tools use the same accounts and the same write rights as on the
  owner's laptop. Treat every statement that changes data as the owner's decision.

### Tokens and git

- The tokens you need are already in your environment: GitLab, Grafana, ArgoCD and the
  Claude Agent provider. Do not look for other credentials on the machine.
- The GitLab token belongs to the owner's personal account. It can reach every project
  that account can reach, so use it with care.
- Use `glab` for merge requests. It reads the token from the environment.

### Rules for changes

- Commit locally in the repository you work on.
- Push only feature branches, never `main` or any other protected branch.
- Open a merge request for every change that should reach `main`. The owner reviews
  and merges it. Do not merge your own merge request.
- Force-push only to feature branches you created, and only after a rebase. Use
  `git push --force-with-lease`, never a plain `--force`.
- Never force-push to `main` or any other protected branch, and never delete branches
  that are not yours. Do not change repository settings.
- Long tasks are fine. The service restarts only at a chosen time, and a restart ends
  the session.
