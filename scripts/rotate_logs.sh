#!/usr/bin/env bash
# Keep the last N weeks of run logs and throw the rest away.
#
# A weekly run writes a dated directory with the prompt, every stage's output
# and the render log. Those are worth keeping while a failure is still being
# understood and worth nothing a month later, and a render log is large.
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KEEP="${KEEP_WEEKS:-8}"

cd "$REPO/logs" 2>/dev/null || exit 0
# shellcheck disable=SC2012
ls -1d 20*-*-* 2>/dev/null | sort -r | tail -n +$((KEEP + 1)) | while read -r old; do
  echo "removing $old"
  rm -rf "$old"
done

# the agents' own stdout files grow forever; truncate anything over 5MB
for f in *.out.log *.err.log; do
  [[ -f "$f" ]] || continue
  size=$(stat -f%z "$f" 2>/dev/null || echo 0)
  if (( size > 5242880 )); then
    tail -c 1048576 "$f" > "$f.tmp" && mv "$f.tmp" "$f"
    echo "truncated $f"
  fi
done
