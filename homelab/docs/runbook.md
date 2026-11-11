# Runbook for briareus

## Where the secrets live

- `homelab/.env` on the laptop: every server value. Gitignored.
- `/etc/opencode-secrets/opencode.env` on the server: the OpenCode password and
  the Claude Code token. Mode 0600, owner root. The agent can read its own
  environment, so only tokens the agent may hold go here.
- `/etc/homelab/monitoring.env` on the server: the Healthchecks.io ping URL and
  the OpenCode password for the heartbeat. Mode 0600, owner root.
- `/etc/restic/restic.env` on the server: the B2 credentials. Mode 0600, owner
  root.

RESTIC_PASSWORD must be in the password manager. Without it the backup cannot be
restored.

## Upgrade OpenCode

OpenCode is installed with Homebrew and auto-update is off. Upgrade it at a chosen
time, because the restart kills a running session.

```sh
ssh me@briareus
brew upgrade --formula anomalyco/tap/opencode-v2
sudo systemctl restart opencode
opencode --version
```

The laptop and the server must report the same version, or the client refuses the
connection.

## Upgrade the Claude Code cask by hand

The cask cannot be pinned. Upgrade it only when you choose to, never from the
deploy.

```sh
brew upgrade --cask claude-code
brew list --cask --versions claude-code
```

The version must be 2.1.248 or newer, or the claude-agent provider refuses to
start. Record the version below.

| Date | Version |
|---|---|
| 2026-11-11 | 2.1.311 |

Never run `brew uninstall --cask --zap claude-code`. It deletes the login.

## Apply a config change from git

The daily timer pulls main, copies the skills and stages a config change. It never
restarts the service.

```sh
sudo systemctl start opencode-sync
cat /run/opencode-config-pending        # present when a restart is needed
sudo systemctl restart opencode
sudo rm -f /run/opencode-config-pending
```

A new session picks up a changed skill file without a restart. A changed
opencode.jsonc needs the restart.

## Restore from backup

The small test after phase 6:

```sh
sudo systemctl start restic-backup
sudo restic snapshots
sudo restic restore latest --target /var/tmp/restore-test --include /home/agent/code
diff -r /home/agent/code /var/tmp/restore-test/home/agent/code
```

Repeat it with the full path set after phase 10.

## If k3s breaks

OpenCode runs outside the cluster, so it keeps working. Use it to fix the cluster,
or run the fixes by hand. A broken cluster must never take the agent down.

## Rebuild the box

1. Install Debian 13 as in docs/bootstrap.md.
2. Copy the SSH key.
3. `cd homelab && uv run pyinfra inventory.py deploy.py`.
4. Restore from restic.
5. Run the manual steps at the end of the deploy output.

## Accepted exceptions to a clean second run

- The apt package index refreshes at most once a day, so a run on a new day reports
  one change on the package operation.
- `files.block` prints a beta warning.
- The heartbeat and health timers run on their own schedule.

## Known limits

- Port 53 must stay free on the host. A stub resolver or any other listener means
  Pi-hole never schedules in v2.
- Argo CD is served over plain HTTP on the LAN. Treat the admin password as a LAN
  secret.
- App SQLite files are copied while the app writes them. A restore means starting
  the app again from its config, not from a frozen copy.
- The agent keeps full internet egress. The unit sandbox limits the LAN and the pod
  ranges only, so a hijacked agent can still send data out.
- The systemd sandbox applies only inside the unit. An SSH shell as the agent user
  does not get it.
- pyinfra connects with paramiko, which cannot resolve briareus.local (mDNS
  returns only link-local IPv6). Use the LAN IP, then the tailnet name.
- pyinfra also needs the Bitwarden SSH agent to be unlocked and to approve the
  request. When it is not, the connection fails with No existing session from
  paramiko while plain ssh still works. A deploy key on disk would remove this.
- The Healthchecks probe uses /api/config. /api/hello returns 404 in OpenCode
  2.2.7. Check the route after an OpenCode upgrade.

## Manual steps for a rebuild of the agent

1. As the agent user, `opencode auth login`.
2. As the agent user, `claude auth login` and `claude auth status`.
3. Confirm `systemctl status opencode` is active and the heartbeat reports green.
