"""Argo CD: helm bootstrap, then the app-of-apps (phase 8, v2).

Not implemented yet. The plan says use v1 for a week before starting v2.

When this section is written it does the following, in this order:

1. tasks/secrets.py creates the app namespaces and their Secrets first.
2. Helm installs Argo CD from the chart version in k8s/apps/argocd.yaml, with the
   values from k8s/values/argocd.yaml, dex and notifications off, TLS ended at
   Traefik.
3. No repository Secret: the repository is public, so Argo CD clones over
   anonymous HTTPS.
4. Apply k8s/project.yaml, because k8s/apps does not hold it.
5. Apply k8s/root.yaml, which watches homelab/k8s/apps.
6. Print the command that shows the initial admin password.

Read the argocd skill before writing this module.
"""

from pyinfra import logger

logger.info("PHASE=argocd is a placeholder. v2 starts after a week of v1 use.")
