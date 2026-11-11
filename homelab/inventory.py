"""Inventory for the briareus homelab host.

Read the values from homelab/.env without adding a dependency. When the file is
missing, fall back to placeholders so scripts/ci.sh runs on a fresh clone.
"""

import os
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent / ".env"


def read_env(path: Path) -> dict[str, str]:
    """Read a dotenv file into a dictionary.

    Args:
        path: File to read.

    Returns:
        The key and value pairs. Empty when the file does not exist.
    """
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


env = read_env(ENV_PATH)

HOST = env.get("NUC_HOST") or "192.168.68.102"
ADMIN_USER = env.get("NUC_USER") or "me"
SSH_KEY = os.path.expanduser(env.get("NUC_SSH_KEY") or "")
SSH_PUBKEY = os.path.expanduser(env.get("NUC_PUBKEY") or "~/.ssh/briareus.pub")

DATA = {
    "admin_user": ADMIN_USER,
    "agent_user": "agent",
    "hostname": "briareus",
    "lan_name": "briareus.local",
    "lan_ip": "192.168.68.102",
    "lan_gateway": "192.168.68.1",
    "lan_subnet": "192.168.68.0/24",
    "wired_interface": "enp1s0",
    "wireless_interface": "wlp2s0",
    "tailnet_name": env.get("TAILNET_NAME", ""),
    "timezone": "Europe/Brussels",
    "ssh_user": ADMIN_USER,
    "ssh_pubkey": SSH_PUBKEY,
    # The private key lives in the Bitwarden agent on the laptop. paramiko, which
    # pyinfra uses, cannot use that agent, so a dedicated key file is the
    # transport when NUC_SSH_KEY points at one.
    "ssh_allow_agent": True,
    "ssh_look_for_keys": True,
}

if SSH_KEY:
    DATA["ssh_key"] = SSH_KEY

all = ([HOST], DATA)
