"""k3s: the single-node cluster (phase 7, v2).

Not implemented yet. The plan says use v1 for a week before starting v2.

When this section is written it does the following, in this order:

1. Write /etc/rancher/k3s/config.yaml before the install: kubeconfig mode 0600,
   node name briareus, the LAN IP and both names in tls-san, the local storage
   path, secrets encryption, Traefik and ServiceLB kept.
2. Create /srv/k3s/storage as 0700 root and /srv/data as 0755 root.
3. Install the pinned release from versions.K3S_VERSION with
   INSTALL_K3S_SYMLINK=skip.
4. Copy the kubeconfig to the admin user.
5. Wait for the API server and for the node to become Ready.
6. Add the local-path-retain storage class in k8s/manifests/storage.
7. Restart the OpenCode unit so its sandbox hides the new k3s paths.

The pinned version goes in versions.py, from a live release page.
"""

from pyinfra import logger

logger.info("PHASE=k3s is a placeholder. v2 starts after a week of v1 use.")
