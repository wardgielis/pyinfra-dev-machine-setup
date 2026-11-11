#!/bin/sh
# Show host facts once per interactive shell, and nothing anywhere else.
#
# The guard variable is deliberately not exported: an exported variable is
# inherited by tmux and su, and those shells would stay silent.
case "$-" in
    *i*) ;;
    *) return 0 2>/dev/null || exit 0 ;;
esac

if [ -t 1 ] && [ -z "${HOMELAB_FASTFETCH_SHOWN:-}" ]; then
    HOMELAB_FASTFETCH_SHOWN=1
    if command -v fastfetch >/dev/null 2>&1; then
        fastfetch
    fi
fi
