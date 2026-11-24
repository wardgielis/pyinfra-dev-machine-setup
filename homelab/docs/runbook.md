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

## Naturalis VPN and ClickHouse tunnels

Two ClickHouse MCP servers need the Naturalis eduVPN link and an SSH tunnel. The
laptop reaches production through its own tunnel script. The server uses these parts:

- `openvpn-client@naturalis` (or `wg-quick@naturalis` for a WireGuard file): the
  profile from https://naturalis.eduvpn.nl/. The deploy changes it to a split tunnel.
  For OpenVPN it adds `route-nopull`, so the pushed routes and DNS are ignored, and one
  host route per ClickHouse address. For WireGuard it limits AllowedIPs and removes the
  DNS line. Never use a full tunnel, because it would cut off Tailscale and SSH.
- `chtunnel-prod` and `chtunnel-dev`: SSH tunnels run by the user `chtunnel`, which
  holds the personal Naturalis key. Production listens on 127.0.0.1:8123 and
  development on 127.0.0.1:8124. The OpenCode agent can use the ports and cannot read
  the key.
- `naturalis-check.timer`: every hour it checks the VPN handshake, both tunnels and
  the profile age. A problem posts to Healthchecks.io.

Set up or renew the profile (a person must do this about every 90 days):

1. Log in at https://naturalis.eduvpn.nl/ and download a profile for this server
   (OpenVPN or WireGuard). Each device needs its own profile.
2. Save it outside the repo with mode 0600. Put the path in `homelab/.env` as
   `VPN_PROFILE`.
3. Run `PHASE=naturalis uv run pyinfra inventory.py deploy.py` from `homelab/`.

The expiry date comes from the client certificate in an OpenVPN profile. For a
WireGuard profile it is the file date plus `VPN_PROFILE_DAYS` (default 90). The check
warns 7 days before.

Checks on the server:

```sh
sudo systemctl status openvpn-client@naturalis   # or: sudo wg show naturalis
systemctl status chtunnel-prod chtunnel-dev
curl -s http://127.0.0.1:8123/ping     # prints Ok.
```

The deploy resolves the two host names when it writes the profile. If a ClickHouse
address changes, run the deploy again.

Known limit: the personal Naturalis key sits on this box. Ask infra for a dedicated
read-only key and a longer-lived server profile, then replace both.

## One writer for the OpenCode config

`opencode-sync` writes `/etc/opencode/opencode.jsonc` and `AGENTS.md` from git main.
The deploy runs it once. The deploy stops with an error when `files/`,
`homelab/files/`, `scripts/` or `opencode-config/` differ from `origin/main`, so
commit and push first. `ALLOW_UNPUSHED=1` overrides this for a dry run of local work.

The server restarts only when the unit or the secrets changed, or when the sync left
`/run/opencode-config-pending`. The second case ends running sessions, so deploy when
the server is idle.

Accepted exceptions to the guard rule for `server.shell`: the sync run and the
marker-based restart always report a change. Their commands do nothing when there
is nothing to do.

The private skills (the ones git does not hold) are copied by the deploy and listed
in `/etc/opencode/private-skills.list`. The sync reads that list, so it never deletes
them.

## Check that the server matches the laptop

```sh
python3 scripts/parity_check.py
```

It compares the skill names, the MCP names, the config hash and the AGENTS core hash
between the laptop and the server, and prints every difference.

## Stop the server for a while

```sh
ssh me@briareus.dove-cobia.ts.net
sudo systemctl stop opencode     # ends the sessions cleanly, up to 90 seconds
sudo systemctl poweroff
```

Start it with the power button. A normal shutdown is not a power loss, so the BIOS
setting does not bring it back on its own. After boot, OpenCode starts by itself, the
node rejoins the tailnet with its tag, and the sync timer catches up on a missed run.

## Permission policy for unattended runs

The server config allows read, edit, shell, web fetch and web search, because a prompt
would stall an overnight run. It hard-denies four things:

- reading `.env` and `.env.*` files, so a stray `cat` cannot print secrets
- `sudo`
- `rm -rf /`
- `git push --force`

The laptop keeps the defaults, where anything unusual asks first.

The systemd sandbox, not this policy, is the security boundary. The policy stops
accidents, not a determined agent.

## The terminal client

`opencode-remote` runs the terminal client against the server:

```sh
opencode-remote                     # uses https://briareus.dove-cobia.ts.net:8443
OPENCODE_SERVER_URL=https://other:8443 opencode-remote   # another server
```

It needs the Tailscale app connected. The function reads the password from
`homelab/.env` for that one command and never prints it.

## Restore from backup

The small test after phase 6:

```sh
sudo systemctl start restic-backup
sudo restic snapshots
sudo restic restore latest --target /var/tmp/restore-test --include /home/agent/dev
diff -r /home/agent/dev /var/tmp/restore-test/home/agent/dev
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
