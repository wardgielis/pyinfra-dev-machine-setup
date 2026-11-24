"""Naturalis access: the eduVPN link and the ClickHouse tunnels.

The ClickHouse hosts accept SSH from the Naturalis eduVPN range only, and they
accept ClickHouse traffic from nowhere over the VPN, so a tunnel is needed.

Design:
- The VPN is a profile from https://naturalis.eduvpn.nl/. Both kinds work: an
  OpenVPN file (.ovpn, run by openvpn-client@naturalis) or a WireGuard file (.conf,
  run by wg-quick@naturalis). The deploy rewrites it to a split tunnel: only the two
  ClickHouse addresses are routed. A full tunnel would cut off Tailscale and SSH.
- A separate system user, chtunnel, holds the personal Naturalis SSH key and runs
  the two tunnel units. The OpenCode agent only sees 127.0.0.1:8123 and :8124 and
  never reads the key.
- A timer checks the link, the tunnels and the profile age every hour.

Without the profile file or the key file the section installs what it can, enables
nothing, and prints what is missing.
"""

import io
import os
import socket
import subprocess
from datetime import date, datetime, timedelta
from pathlib import Path

from pyinfra import host, logger
from pyinfra.operations import apt, files, server, systemd
from pyinfra.operations.util import any_changed

VPN_NAME = "naturalis"
TUNNEL_USER = "chtunnel"
TUNNEL_HOME = "/var/lib/chtunnel"
REMOTE_USER = "development"
REMOTE_CLICKHOUSE_PORT = 8123

# The prod port matches the laptop MCP entry. Dev uses 8124 on the server.
TUNNELS = [
    {"name": "prod", "host": "tools-production-clickhouse.hosts.naturalis.io", "port": 8123},
    {"name": "dev", "host": "tools-development-clickhouse.hosts.naturalis.io", "port": 8124},
]

# eduVPN sessions last 90 days by default. The check warns this many days before.
# An OpenVPN profile carries its own end date in the client certificate, so this
# value is only the fallback for a WireGuard profile.
PROFILE_DAYS = int(os.environ.get("VPN_PROFILE_DAYS") or os.environ.get("WIREGUARD_PROFILE_DAYS") or "90")
WARN_DAYS = 7

# wg-quick runs these as root, so a profile that holds one is refused.
FORBIDDEN_KEYS = {"preup", "postup", "predown", "postdown", "saveconfig"}

# OpenVPN directives that run programs or load code. A profile that holds one is
# refused, because the service runs as root.
FORBIDDEN_OPENVPN = {
    "script-security", "up", "down", "route-up", "route-pre-down", "ipchange", "plugin",
    "learn-address", "client-connect", "client-disconnect", "tls-verify", "up-restart",
    "auth-user-pass-verify", "management", "setenv-safe", "push-peer-info",
}

KEY_PATH = Path(os.path.expanduser(os.environ.get("NATURALIS_SSH_KEY", ""))) if os.environ.get("NATURALIS_SSH_KEY") else None
_profile_setting = os.environ.get("VPN_PROFILE") or os.environ.get("WIREGUARD_PROFILE") or ""
PROFILE_PATH = Path(os.path.expanduser(_profile_setting)) if _profile_setting else None


def _resolve(hostname: str) -> str:
    """Return the IPv4 address of a host name.

    Args:
        hostname: The name to look up.

    Returns:
        The first IPv4 address.
    """
    return socket.getaddrinfo(hostname, None, socket.AF_INET)[0][4][0]


def _split_tunnel_profile(text: str, addresses: list[str]) -> str:
    """Turn an eduVPN WireGuard profile into a split tunnel.

    Removes the DNS line, so the server resolver stays the router. Limits
    AllowedIPs to the given addresses. Refuses a profile with script hooks.

    Args:
        text: The profile as downloaded from the portal.
        addresses: The IPv4 addresses that the tunnel may route.

    Returns:
        The profile text for /etc/wireguard.
    """
    out = []
    for line in text.splitlines():
        key = line.split("=", 1)[0].strip().lower()
        if key in FORBIDDEN_KEYS:
            raise SystemExit(f"The WireGuard profile has a {key} line. Remove it, wg-quick runs it as root.")
        if key == "dns":
            continue
        if key == "allowedips":
            line = "AllowedIPs = " + ", ".join(f"{address}/32" for address in addresses)
        out.append(line)
    return "\n".join(out) + "\n"


def _profile_kind(path: Path) -> str:
    """Tell an OpenVPN profile from a WireGuard profile.

    Args:
        path: The profile file.

    Returns:
        Either openvpn or wireguard.
    """
    text = path.read_text(encoding="utf-8")
    if "[Interface]" in text:
        return "wireguard"
    if "\nremote " in "\n" + text or path.suffix == ".ovpn":
        return "openvpn"
    raise SystemExit(f"{path} is neither a WireGuard nor an OpenVPN profile.")


def _split_tunnel_openvpn(text: str, addresses: list[str]) -> str:
    """Turn an eduVPN OpenVPN profile into a split tunnel.

    route-nopull makes OpenVPN ignore the routes, the default gateway and the DNS
    servers that the VPN server pushes. Then one host route per address is added.
    Refuses a profile that holds a directive that runs a program.

    Args:
        text: The profile as downloaded from the portal.
        addresses: The IPv4 addresses that the tunnel may route.

    Returns:
        The profile text for /etc/openvpn/client.
    """
    in_block = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("<") and not stripped.startswith("</"):
            in_block = True
        elif stripped.startswith("</"):
            in_block = False
        elif not in_block and stripped.split(" ", 1)[0].lower() in FORBIDDEN_OPENVPN:
            raise SystemExit(f"The OpenVPN profile has a {stripped.split(' ', 1)[0]} line. Remove it, the service runs as root.")

    lines = [text.rstrip(), "", "# Added by the homelab deploy: split tunnel, no pushed routes or DNS.", "route-nopull"]
    lines += [f"route {address} 255.255.255.255" for address in addresses]
    return "\n".join(lines) + "\n"


def _openvpn_expiry(text: str) -> date | None:
    """Read the end date of the client certificate in an OpenVPN profile.

    Args:
        text: The profile text with an embedded cert block.

    Returns:
        The end date, or None when it cannot be read.
    """
    start, end = text.find("<cert>"), text.find("</cert>")
    if start == -1 or end == -1:
        return None
    certificate = text[start + len("<cert>"):end].strip()
    result = subprocess.run(
        ["openssl", "x509", "-noout", "-enddate"], input=certificate, capture_output=True, text=True, check=False
    )
    if result.returncode != 0 or "=" not in result.stdout:
        return None
    month, day, _clock, year = result.stdout.split("=", 1)[1].split()[:4]
    return datetime.strptime(f"{month} {day} {year}", "%b %d %Y").date()


def _pinned_host_keys(hostnames: list[str]) -> str | None:
    """Read the pinned host keys of the hosts from the laptop known_hosts file.

    Args:
        hostnames: Hosts that must each have a pinned key.

    Returns:
        The known_hosts lines, or None when a host has no pinned key.
    """
    lines = []
    for hostname in hostnames:
        result = subprocess.run(["ssh-keygen", "-F", hostname], capture_output=True, text=True, check=False)
        found = [line for line in result.stdout.splitlines() if line and not line.startswith("#")]
        if not found:
            logger.warning("No pinned host key for %s in ~/.ssh/known_hosts. Connect once by hand first.", hostname)
            return None
        lines.extend(found)
    return "\n".join(lines) + "\n"


_key_ok = KEY_PATH is not None and KEY_PATH.is_file()
_profile_ok = PROFILE_PATH is not None and PROFILE_PATH.is_file()
_hosts = [tunnel["host"] for tunnel in TUNNELS]
_known_hosts = _pinned_host_keys(_hosts) if _key_ok else None
_ready = _key_ok and _profile_ok and _known_hosts is not None

if not _key_ok:
    logger.warning("NATURALIS_SSH_KEY is not set or the file is missing. The tunnels stay off.")
if not _profile_ok:
    logger.warning("VPN_PROFILE is not set or the file is missing. The VPN stays off.")

VPN_KIND = _profile_kind(PROFILE_PATH) if _profile_ok else "wireguard"
VPN_UNIT = f"openvpn-client@{VPN_NAME}" if VPN_KIND == "openvpn" else f"wg-quick@{VPN_NAME}"
VPN_CONF = (
    f"/etc/openvpn/client/{VPN_NAME}.conf" if VPN_KIND == "openvpn" else f"/etc/wireguard/{VPN_NAME}.conf"
)

# ------------------------------------------------------------
# 1. Packages and the tunnel user
# ------------------------------------------------------------
apt.packages(
    name="Install the VPN tools and the SSH client",
    packages=["wireguard-tools", "openvpn", "openssh-client", "curl", "openssl"],
    _sudo=True,
)

server.user(
    name="Create the tunnel user",
    user=TUNNEL_USER,
    home=TUNNEL_HOME,
    shell="/usr/sbin/nologin",
    system=True,
    create_home=True,
    groups=[],
    _sudo=True,
)

files.directory(
    name="Create the tunnel SSH folder",
    path=f"{TUNNEL_HOME}/.ssh",
    user=TUNNEL_USER,
    group=TUNNEL_USER,
    mode="0700",
    _sudo=True,
)

if _key_ok:
    files.put(
        name="Install the Naturalis key for the tunnel user",
        src=str(KEY_PATH),
        dest=f"{TUNNEL_HOME}/.ssh/id_ed25519",
        user=TUNNEL_USER,
        group=TUNNEL_USER,
        mode="0600",
        _sudo=True,
    )

if _known_hosts:
    files.put(
        name="Pin the ClickHouse host keys",
        src=io.StringIO(_known_hosts),
        dest=f"{TUNNEL_HOME}/.ssh/known_hosts",
        user=TUNNEL_USER,
        group=TUNNEL_USER,
        mode="0644",
        _sudo=True,
    )

# ------------------------------------------------------------
# 2. The VPN profile
# Split tunnel: only the ClickHouse addresses are routed.
# ------------------------------------------------------------
_conf = None
if _profile_ok:
    _addresses = sorted({_resolve(hostname) for hostname in _hosts})
    _profile_text = PROFILE_PATH.read_text(encoding="utf-8")
    if VPN_KIND == "openvpn":
        files.directory(
            name="Create the OpenVPN client folder",
            path="/etc/openvpn/client",
            mode="0750",
            _sudo=True,
        )
        _vpn_text = _split_tunnel_openvpn(_profile_text, _addresses)
    else:
        _vpn_text = _split_tunnel_profile(_profile_text, _addresses)
    _conf = files.put(
        name=f"Install the eduVPN {VPN_KIND} profile",
        src=io.StringIO(_vpn_text),
        dest=VPN_CONF,
        user="root",
        group="root",
        mode="0600",
        _sudo=True,
    )
    logger.info("The %s VPN routes only: %s", VPN_KIND, ", ".join(_addresses))

# ------------------------------------------------------------
# 3. The tunnel units
# ------------------------------------------------------------
_units = []
for _tunnel in TUNNELS:
    _units.append(
        files.template(
            name=f"Install the {_tunnel['name']} ClickHouse tunnel unit",
            src="files/chtunnel.service.j2",
            dest=f"/etc/systemd/system/chtunnel-{_tunnel['name']}.service",
            mode="0644",
            tunnel_user=TUNNEL_USER,
            tunnel_home=TUNNEL_HOME,
            vpn_unit=VPN_UNIT,
            remote_user=REMOTE_USER,
            remote_port=REMOTE_CLICKHOUSE_PORT,
            name_of_tunnel=_tunnel["name"],
            local_port=_tunnel["port"],
            remote_host=_tunnel["host"],
            _sudo=True,
        )
    )

# ------------------------------------------------------------
# 4. The hourly check
# ------------------------------------------------------------
if _profile_ok and VPN_KIND == "openvpn":
    # The client certificate ends with the session, so read the real date.
    _expires = _openvpn_expiry(_profile_text) or (
        datetime.fromtimestamp(PROFILE_PATH.stat().st_mtime).date() + timedelta(days=PROFILE_DAYS)
    )
elif _profile_ok:
    _expires = datetime.fromtimestamp(PROFILE_PATH.stat().st_mtime).date() + timedelta(days=PROFILE_DAYS)
else:
    _expires = date.today() + timedelta(days=PROFILE_DAYS)

files.directory(
    name="Create /etc/homelab for the VPN check",
    path="/etc/homelab",
    mode="0755",
    _sudo=True,
)

files.put(
    name="Write the VPN check settings",
    src=io.StringIO(
        f"VPN_NAME={VPN_NAME}\nVPN_KIND={VPN_KIND}\nVPN_UNIT={VPN_UNIT}\n"
        f"EXPIRES={_expires.isoformat()}\nWARN_DAYS={WARN_DAYS}\n"
    ),
    dest="/etc/homelab/naturalis.env",
    mode="0644",
    _sudo=True,
)

files.put(
    name="Install the VPN check script",
    src="files/naturalis-check",
    dest="/usr/local/bin/naturalis-check",
    mode="0755",
    _sudo=True,
)

_check_service = files.put(
    name="Install the VPN check service",
    src="files/naturalis-check.service",
    dest="/etc/systemd/system/naturalis-check.service",
    mode="0644",
    _sudo=True,
)

_check_timer = files.put(
    name="Install the VPN check timer",
    src="files/naturalis-check.timer",
    dest="/etc/systemd/system/naturalis-check.timer",
    mode="0644",
    _sudo=True,
)

systemd.daemon_reload(
    name="Reload systemd after the Naturalis unit changes",
    _if=any_changed(_check_service, _check_timer, *_units),
    _sudo=True,
)

# ------------------------------------------------------------
# 5. Start everything, but only when the key, the profile and the pinned host
# keys are all there. Restart the VPN only when the profile changed.
# ------------------------------------------------------------
if _ready:
    systemd.service(
        name="Enable and start the eduVPN link",
        service=VPN_UNIT,
        running=True,
        enabled=True,
        _sudo=True,
    )
    systemd.service(
        name="Restart the eduVPN link after a profile change",
        service=VPN_UNIT,
        restarted=True,
        _if=_conf.did_change,
        _sudo=True,
    )
    for _tunnel, _unit in zip(TUNNELS, _units):
        systemd.service(
            name=f"Enable and start the {_tunnel['name']} ClickHouse tunnel",
            service=f"chtunnel-{_tunnel['name']}",
            running=True,
            enabled=True,
            _sudo=True,
        )
        systemd.service(
            name=f"Restart the {_tunnel['name']} tunnel after a unit change",
            service=f"chtunnel-{_tunnel['name']}",
            restarted=True,
            _if=_unit.did_change,
            _sudo=True,
        )
    systemd.service(
        name="Enable the VPN check timer",
        service="naturalis-check.timer",
        running=True,
        enabled=True,
        _sudo=True,
    )
else:
    print(
        "Naturalis access is installed but switched off. To switch it on:\n"
        "  1. Log in at https://naturalis.eduvpn.nl/ and download a profile (OpenVPN\n"
        "     or WireGuard) for this server. Save it outside the repo, mode 0600.\n"
        "  2. Put its path in homelab/.env as VPN_PROFILE.\n"
        "  3. Make sure NATURALIS_SSH_KEY points at the key file, and that both\n"
        "     ClickHouse hosts are in ~/.ssh/known_hosts.\n"
        "  4. Run: PHASE=naturalis uv run pyinfra inventory.py deploy.py"
    )
