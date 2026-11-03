#!/usr/bin/env bash
#
# cask-doctor — repair Homebrew casks left half-installed.
#
# An interrupted `brew upgrade` (or a cask whose download dies) removes the
# old version directory *before* staging the new one. What survives is
# Caskroom/<cask>/.metadata/ with no version directory and no binary — and in
# that state:
#
#   brew list --cask                      -> still lists the cask
#   brew list --cask --versions <cask>    -> errors
#   brew info --cask <cask>               -> "Not installed"
#
# Every pyinfra run then dies in Section 2, because `brew.casks()` needs the
# BrewCasks fact and that fact raises. This script finds that state and
# reinstalls the affected casks so the deploy can proceed.
#
# Safe by design:
#   * `--force`, never `--zap` — zap would delete ~/.claude.json and the
#     CLI credentials, forcing a fresh login.
#   * Healthy casks are never touched; a clean machine exits in well under
#     a second with no output beyond the summary line.
#
# Used by deploy.py Section 0 and by the fail-safe note in AGENTS.md.

set -euo pipefail

caskroom="${HOMEBREW_CASKROOM:-$(brew --caskroom)}"
broken=()

# A healthy cask has at least one version directory next to .metadata/
for dir in "$caskroom"/*/; do
    [[ -d "$dir" ]] || continue
    if ! find "$dir" -mindepth 1 -maxdepth 1 -type d ! -name .metadata \
        -print -quit | grep -q .; then
        broken+=("$(basename "$dir")")
    fi
done

if [[ ${#broken[@]} -eq 0 ]]; then
    echo "cask-doctor: all casks healthy"
    exit 0
fi

for cask in "${broken[@]}"; do
    echo "cask-doctor: repairing '$cask' — only .metadata left in $caskroom/$cask"
    # The cask is not really installed, so uninstall may fail on the corrupt
    # receipt. --force clears what it can; the rm -rf clears the rest.
    brew uninstall --cask "$cask" --force >/dev/null 2>&1 || true
    rm -rf "${caskroom:?}/$cask"
    brew install --cask "$cask"
done

echo "cask-doctor: repaired ${#broken[@]} cask(s): ${broken[*]}"
