# Print a reminder while a config change from git waits for a restart.
if [ -f /run/opencode-config-pending ]; then
    echo "opencode config changed in git, restart to apply: systemctl restart opencode"
fi
