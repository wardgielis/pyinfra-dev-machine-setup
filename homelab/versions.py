"""Pinned versions for the homelab host.

Fill every value from a live source at the moment you implement the phase that
uses it. Never guess a version.

v1 uses no pinned host binary: the Claude Code cask cannot be pinned, and
Tailscale, restic and fastfetch come from apt. Record the installed Claude Code
version in docs/runbook.md instead.

Chart versions do not live here. They live in the Argo CD Application files
under k8s/apps/, so the bootstrap and the self-managing app cannot drift.
"""

# v2, phase 7: the k3s release installed with INSTALL_K3S_VERSION.
# Look it up at https://github.com/k3s-io/k3s/releases before phase 7.
K3S_VERSION = ""

# v2, phase 9: the OpenCloud image tag. Use a stable tag, never the rolling one.
# Look it up at https://hub.docker.com/r/opencloudeu/opencloud/tags before phase 9.
OPENCLOUD_IMAGE = ""
