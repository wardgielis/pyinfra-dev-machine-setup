"""Kubernetes Secrets for the app namespaces (phase 8, v2).

Not implemented yet. The plan says use v1 for a week before starting v2.

When this section is written it renders each manifest locally, pipes the values
on stdin and applies it with kubectl. Values come from homelab/.env and are never
written to disk, so a Secret cannot end up in git.

It creates the Pi-hole admin password and the OpenCloud admin password, plus the
namespaces they live in.
"""

from pyinfra import logger

logger.info("tasks/secrets.py is a placeholder. v2 starts after a week of v1 use.")
