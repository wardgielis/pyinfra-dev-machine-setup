"""fastfetch in every interactive terminal, and silence everywhere else.

The hook runs only when the shell is interactive and only once per shell. The
guard variable is not exported: an exported variable is inherited by tmux and su,
and then those shells stay silent.
"""

from pyinfra.operations import files

files.put(
    name="Install the fastfetch config",
    src="files/fastfetch_config.jsonc",
    dest="/etc/fastfetch/config.jsonc",
    mode="0644",
    _sudo=True,
)

files.put(
    name="Install the fastfetch hook for login shells",
    src="files/fastfetch_hook.sh",
    dest="/etc/profile.d/99-fastfetch.sh",
    mode="0644",
    _sudo=True,
)

files.block(
    name="Run the fastfetch hook from interactive bash",
    path="/etc/bash.bashrc",
    content=". /etc/profile.d/99-fastfetch.sh",
    marker="# {mark} HOMELAB FASTFETCH",
    _sudo=True,
)
