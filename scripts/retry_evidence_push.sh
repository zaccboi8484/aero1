#!/usr/bin/env bash
# Safe concurrent GitHub Actions evidence publication. Never force-pushes.
# Source data changes must be replayed on top of current main or fail explicitly;
# silent overwriting, dropping or inventing property/permit rows is forbidden.
set -euo pipefail
target="${1:-main}"
case "$target" in main) ;; *) echo "Unexpected destination branch" >&2; exit 2;; esac
for attempt in 1 2 3 4 5; do
  git fetch --no-tags origin "$target"
  if ! git -c rebase.autoStash=true rebase "origin/$target"; then
    echo "GateKeeper: source conflict while rebasing evidence; no overwrite attempted" >&2
    git rebase --abort || true
    exit 3
  fi
  if git push origin "HEAD:$target"; then
    echo "GateKeeper: published evidence safely (attempt $attempt)"
    exit 0
  fi
  echo "Evidence push raced another crawler; retrying on newest commit (attempt $attempt)" >&2
  sleep $((attempt * 3))
done
echo "GateKeeper: evidence publication exhausted retries; source files not overwritten" >&2
exit 4
