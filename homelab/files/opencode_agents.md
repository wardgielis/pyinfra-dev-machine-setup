# AGENTS.md for the server

This host is briareus, a small home server. You run as the user agent, without
sudo, inside a systemd sandbox.

The workspace is /home/agent/code. Work there. Files outside it are read-only,
and the sandbox hides /srv, the k3s files and /etc/opencode-secrets.

The skills are in /opt/opencode-skills. They are copied from the public
repository on a daily timer and are read-only.

Network: the LAN and the cluster ranges are blocked. Loopback and the internet
work. The resolver is the router.

Rules:

- Commit locally. The admin reviews the diff and pushes from the laptop. You have
  no write key, by design.
- Do not look for credentials outside your environment. The tokens you need are
  already set.
- Long tasks are fine. The service restarts only at a chosen time, and a restart
  ends the session.
