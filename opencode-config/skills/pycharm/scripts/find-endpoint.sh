#!/bin/sh
# Print the streamable-HTTP MCP endpoint of every running JetBrains IDE on this machine.
#
# Why: the IDE picks its MCP port automatically at launch, so the port in the opencode
# config can go stale when PyCharm restarts. This finds the current one without opening
# the IDE settings UI.
#
# Usage: sh find-endpoint.sh
# Then set PYCHARM_MCP_URL in the repo .env and re-run the deploy (repo-first rule).

for port in $(lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null \
    | awk '/[Jj]etbrains|[Pp]ycharm|[Ii]ntellij|[Gg]oland|[Ww]ebstorm|[Cc]lion|[Rr]ider/ {print $9}' \
    | sed 's/.*://' | sort -un); do
  body=$(curl -s -m 2 -X POST \
      -H 'Content-Type: application/json' \
      -H 'Accept: application/json, text/event-stream' \
      -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"probe","version":"0"}}}' \
      "http://127.0.0.1:$port/stream" 2>/dev/null)
  case "$body" in
    *"MCP Server"*) echo "http://127.0.0.1:$port/stream  <= $body"; found=1 ;;
  esac
done

# Silence is not proof that no endpoint exists: this matches IDE process names, which misses
# unusual launchers (and Linux, where the process is `java`). Fall back to the IDE's
# Settings | Tools | MCP Server panel.
[ -n "$found" ] || echo "no MCP endpoint found on this machine" >&2
