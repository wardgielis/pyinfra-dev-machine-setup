# Bootstrap briareus

This page lists the steps in order, from a fresh Debian install to a working
agent server. Do the steps by hand before the first deploy, then run the deploy
one phase at a time.

## 1. Before the first deploy

1. Install Debian 13 with only SSH server and standard system utilities. Use the
   hostname briareus and leave the root password empty.
2. Set a DHCP reservation for enp1s0 on the router. Write the address down.
3. Set power on after AC power loss in the BIOS, and disable sleep.
4. Copy your SSH key: `ssh-copy-id me@briareus.local`.
5. Tailscale: enable MagicDNS and HTTPS certificates in the admin console. Create
   a tagged auth key (tag:server).
6. Healthchecks.io: create an account and one check with email alerts, period five
   minutes. Copy the ping URL.
7. Backblaze B2: create a private bucket and a key limited to it.

## 2. Fill in homelab/.env

```sh
cd homelab
cp .env.example .env
```

Set NUC_HOST, NUC_USER and NUC_PUBKEY. Leave NUC_SSH_KEY empty to use the SSH
agent. Add the secrets you have now; the deploy skips what is missing and prints a
warning.

The laptop resolves briareus.local through mDNS, which returns only link-local
IPv6 addresses. pyinfra uses paramiko, which cannot use those, so use the LAN IP
until phase 5 gives you the tailnet name.

## 3. Run the phases

Run each command twice. The second run must report no changes, except the apt
index refresh, which runs at most once a day.

```sh
uv run pyinfra inventory.py deploy.py --dry      # preview everything
PHASE=base      uv run pyinfra inventory.py deploy.py
PHASE=shell     uv run pyinfra inventory.py deploy.py
PHASE=homebrew  uv run pyinfra inventory.py deploy.py
PHASE=tailscale uv run pyinfra inventory.py deploy.py
PHASE=opencode  uv run pyinfra inventory.py deploy.py
PHASE=sync      uv run pyinfra inventory.py deploy.py
PHASE=backup    uv run pyinfra inventory.py deploy.py
```

### Checks after phase base

- `ss -ltn` shows only SSH, plus nothing on port 53.
- `/sbin/swapon --show` lists /dev/sda3.
- `cat /etc/resolv.conf` shows only 192.168.68.1.
- `ip route show default` shows exactly one line, on enp1s0.
- A password login is refused and a key login works.
- `systemctl list-timers` shows homelab-heartbeat and homelab-health.

### Checks after phase shell

- `ssh me@briareus` shows fastfetch.
- `ssh me@briareus true` prints nothing.
- scp works.
- A new tmux window shows fastfetch.

### Checks after phase homebrew

- `brew doctor` is clean as the admin user.
- As the agent user, `opencode --version` and `claude --version` work.
- `brew install hello` as the agent user is refused.
- `which -a opencode` and `which -a claude` each print one line.

### The claude-agent gate

Before phase opencode, prove that the provider works from the server. As the
agent user, run `claude auth login`, start `opencode serve` by hand, tunnel to it
from the laptop and send one prompt with a claude model.

If the provider is not offered over `--server`, the Claude Code job becomes a
plain `claude` session in tmux started by `systemd-run` with the same sandbox
properties. Record the outcome here.

Outcome: not tested yet.

### Checks after phase tailscale

- `tailscale status` lists the server and the laptop sees it.
- `tailscale cert briareus.<tailnet>.ts.net` works.
- pyinfra connects when NUC_HOST is the tailnet name.

### Checks after phase opencode

- `systemctl status opencode` is active.
- `curl -u "opencode:$OPENCODE_PASSWORD" http://127.0.0.1:4096/api/config` answers.
- Through the bash tool of the agent: `sudo -n true` fails, `kubectl get nodes`
  fails, reading the secrets file fails, and requests to a pod address and a LAN
  address fail.
- The bash tool output has no fastfetch text.
- `systemctl restart opencode` works, and the service comes back after a reboot.

### Checks after phase sync

- Run `/usr/local/bin/opencode-sync` twice. The second run reports no change.
- Push a skill edit on main. The file lands in /opt/opencode-skills and
  /run/opencode-config-pending appears. The service did not restart.
- Break the clone on purpose (a local edit). The sync fails loudly.

### Checks after phase backup

- Run the first backup by hand:
  `sudo systemctl start restic-backup`.
- `restic snapshots` shows one snapshot.
- Restore it into /var/tmp/restore-test and diff against the live tree.

## 4. Manual steps the deploy cannot do

1. As the agent user: `opencode auth login`.
2. As the agent user: `claude auth login`, then check `claude auth status`.
3. Add the laptop client function that points at
   `https://briareus.<tailnet>.ts.net:8443`.
4. Put an encrypted archive of both .env files and the gitignored skills into the
   password manager.

## 5. After a week

Use v1 for a week. Then start v2: k3s, Argo CD, the apps and the full backup set.
Phase 7 begins with the second 8 GB memory stick if the agent and the cluster must
run together.
