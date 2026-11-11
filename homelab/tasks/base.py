"""Base system: packages, timezone, updates, sleep, swap, resolver, monitoring, users, ssh.

Every operation that changes a system file uses sudo on the operation itself.
`config.SUDO` stays off, because Homebrew must never run as root.
"""

import io
import os
from pathlib import Path

from pyinfra import host, logger
from pyinfra.facts.server import Command
from pyinfra.operations import apt, files, server, systemd
from pyinfra.operations.util import any_changed

ADMIN_USER = host.data.admin_user
AGENT_USER = host.data.agent_user
HOSTNAME = host.data.hostname
TIMEZONE = host.data.timezone
LAN_GATEWAY = host.data.lan_gateway
WIRED = host.data.wired_interface
WIRELESS = host.data.wireless_interface
PUBKEY_PATH = Path(os.path.expanduser(host.data.ssh_pubkey))


# ------------------------------------------------------------
# 1. Packages
# ------------------------------------------------------------
apt.packages(
    name="Install base packages",
    packages=[
        "build-essential",
        "procps",
        "curl",
        "file",
        "git",
        "ca-certificates",
        "unattended-upgrades",
        "fastfetch",
        "tmux",
        "jq",
        "unzip",
        "htop",
        "rsync",
        "python3",
        "util-linux",
        "openresolv",
        "sqlite3",
    ],
    update=True,
    # Refresh the package index at most once a day, so a second run in the same
    # day reports no change.
    cache_time=86400,
    _sudo=True,
)


# ------------------------------------------------------------
# 2. Timezone and hostname
# Both are already right on the box, so this should report no change.
# ------------------------------------------------------------
server.timezone(name="Set the timezone", timezone=TIMEZONE, _sudo=True)

server.hostname(name="Set the hostname", hostname=HOSTNAME, _sudo=True)


# ------------------------------------------------------------
# 3. Automatic security updates
# Automatic reboot stays off: a reboot would kill an overnight agent run.
# ------------------------------------------------------------
files.put(
    name="Enable automatic security updates and disable automatic reboot",
    src=io.StringIO(
        'APT::Periodic::Update-Package-Lists "1";\n'
        'APT::Periodic::Unattended-Upgrade "1";\n'
        'APT::Periodic::Automatic-Reboot "false";\n'
    ),
    dest="/etc/apt/apt.conf.d/20auto-upgrades",
    mode="0644",
    _sudo=True,
)

systemd.service(
    name="Enable the unattended-upgrades service",
    service="unattended-upgrades",
    running=True,
    enabled=True,
    _sudo=True,
)


# ------------------------------------------------------------
# 4. Disable sleep
# A masked target is a symlink to /dev/null, which is what systemctl mask does.
# ------------------------------------------------------------
for _target in (
    "sleep.target",
    "suspend.target",
    "hibernate.target",
    "hybrid-sleep.target",
    "suspend-then-hibernate.target",
):
    files.link(
        name=f"Mask {_target}",
        path=f"/etc/systemd/system/{_target}",
        target="/dev/null",
        _sudo=True,
    )


# ------------------------------------------------------------
# 5. Swap
# Keep the existing swap partition. Only the swappiness changes.
# ------------------------------------------------------------
_swap = host.get_fact(Command, command="/sbin/swapon --show || true")
if not _swap:
    logger.warning("No active swap. The plan expects /dev/sda3 from /etc/fstab.")

server.sysctl(
    name="Set vm.swappiness to 10",
    key="vm.swappiness",
    value=10,
    persist=True,
    persist_file="/etc/sysctl.d/99-homelab.conf",
    _sudo=True,
)


# ------------------------------------------------------------
# 6. Resolver and address
# ifupdown starts a dhcpcd instance per interface. dhcpcd writes the resolver and
# takes a default route on both NICs. Stop both behaviours in dhcpcd, and write
# the resolver once.
# ------------------------------------------------------------
files.block(
    name="Stop dhcpcd from writing the resolver and from routing over wifi",
    path="/etc/dhcpcd.conf",
    content=f"nohook resolv.conf\ninterface {WIRELESS}\nnogateway\n",
    marker="# {mark} HOMELAB DHCPCD",
    _sudo=True,
)

files.put(
    name="Write the resolver",
    src=io.StringIO(f"nameserver {LAN_GATEWAY}\n"),
    dest="/etc/resolv.conf",
    mode="0644",
    _sudo=True,
)

# The wifi lease still holds a default route until dhcpcd restarts. Drop it now
# so the source address is predictable. A prepare-time fact is fine: the op is
# only declared while the extra route exists.
_default_routes = host.get_fact(Command, command="ip route show default || true") or ""
if WIRELESS in _default_routes:
    server.shell(
        name="Drop the wireless default route",
        commands=[f"ip route del default dev {WIRELESS}"],
        _sudo=True,
    )


# ------------------------------------------------------------
# 7. Monitoring
# One outside service covers two jobs: it alerts when the pings stop, and it
# accepts a failure post from the units below.
# ------------------------------------------------------------
files.directory(
    name="Create /etc/homelab",
    path="/etc/homelab",
    mode="0700",
    _sudo=True,
)

files.put(
    name="Write the monitoring secrets",
    src=io.StringIO(
        f"HEALTHCHECKS_PING_URL={os.environ.get('HEALTHCHECKS_PING_URL', '')}\n"
        f"OPENCODE_PASSWORD={os.environ.get('OPENCODE_PASSWORD', '')}\n"
    ),
    dest="/etc/homelab/monitoring.env",
    mode="0600",
    _sudo=True,
)

files.put(
    name="Install the failure notifier",
    src="files/homelab-notify",
    dest="/usr/local/bin/homelab-notify",
    mode="0700",
    _sudo=True,
)

files.put(
    name="Install the heartbeat probe",
    src="files/homelab-heartbeat",
    dest="/usr/local/bin/homelab-heartbeat",
    mode="0700",
    _sudo=True,
)

files.put(
    name="Install the daily health check",
    src="files/homelab-health",
    dest="/usr/local/bin/homelab-health",
    mode="0700",
    _sudo=True,
)

files.put(
    name="Install notify-failure@.service",
    src="files/notify-failure@.service",
    dest="/etc/systemd/system/notify-failure@.service",
    mode="0644",
    _sudo=True,
)

_unit_writes = []
for _unit in ("homelab-heartbeat", "homelab-health"):
    _unit_writes.append(
        files.put(
            name=f"Install {_unit}.service",
            src=f"files/{_unit}.service",
            dest=f"/etc/systemd/system/{_unit}.service",
            mode="0644",
            _sudo=True,
        )
    )
    _unit_writes.append(
        files.put(
            name=f"Install {_unit}.timer",
            src=f"files/{_unit}.timer",
            dest=f"/etc/systemd/system/{_unit}.timer",
            mode="0644",
            _sudo=True,
        )
    )

systemd.daemon_reload(
    name="Reload systemd after the monitoring unit changes",
    _if=any_changed(*_unit_writes),
    _sudo=True,
)

for _unit in ("homelab-heartbeat", "homelab-health"):
    systemd.service(
        name=f"Enable the {_unit} timer",
        service=f"{_unit}.timer",
        running=True,
        enabled=True,
        _sudo=True,
    )

_journald = files.block(
    name="Cap the journal at 1 GiB",
    path="/etc/systemd/journald.conf",
    content="SystemMaxUse=1G\nSystemKeepFree=1G",
    line=r"^\[Journal\]$",
    after=True,
    marker="# {mark} HOMELAB JOURNALD",
    _sudo=True,
)

systemd.service(
    name="Restart systemd-journald after the size change",
    service="systemd-journald",
    restarted=True,
    _if=lambda: _journald.did_change(),
    _sudo=True,
)


# ------------------------------------------------------------
# 8. The agent user
# No sudo, no extra groups, no access to the k3s files.
# ------------------------------------------------------------
_authorized_key = PUBKEY_PATH.read_text(encoding="utf-8").strip() if PUBKEY_PATH.is_file() else ""
if not _authorized_key:
    logger.warning("No public key at %s. The agent user gets no SSH key.", PUBKEY_PATH)

server.user(
    name="Create the agent user",
    user=AGENT_USER,
    home=f"/home/{AGENT_USER}",
    shell="/bin/bash",
    create_home=True,
    groups=[],
    public_keys=[_authorized_key] if _authorized_key else None,
    _sudo=True,
)


# ------------------------------------------------------------
# 9. SSH hardening
# Last in the section, and only when the admin user already has an authorized
# key. Keep one session open while testing.
# ------------------------------------------------------------
_admin_keys = host.get_fact(Command, command=f"test -s /home/{ADMIN_USER}/.ssh/authorized_keys && echo yes || true")

if _admin_keys:
    _sshd_config = files.template(
        name="Write the sshd drop-in",
        src="files/sshd_homelab.conf.j2",
        dest="/etc/ssh/sshd_config.d/10-homelab.conf",
        mode="0644",
        admin_user=ADMIN_USER,
        agent_user=AGENT_USER,
        _sudo=True,
    )

    server.shell(
        name="Validate and reload sshd",
        commands=["/usr/sbin/sshd -t", "systemctl reload ssh"],
        _if=lambda: _sshd_config.did_change(),
        _sudo=True,
    )
else:
    logger.warning("No authorized_keys for %s. Skipping the sshd hardening.", ADMIN_USER)


# ------------------------------------------------------------
# 10. Port 53 must stay free for Pi-hole in v2
# ------------------------------------------------------------
_port_53 = host.get_fact(Command, command="ss -lunH 'sport = :53' || true") or ""
if _port_53.strip():
    logger.warning("Something already listens on UDP port 53. Pi-hole needs it in v2.")

if not os.environ.get("HEALTHCHECKS_PING_URL"):
    logger.warning("HEALTHCHECKS_PING_URL is empty. The heartbeat cannot alert anyone.")
    print(
        "Monitoring is installed. Without HEALTHCHECKS_PING_URL the timers run but "
        "report nothing. Fill it in homelab/.env and re-run PHASE=base."
    )
