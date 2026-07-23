#!/usr/bin/env bash
set -euo pipefail

mapfile -t tracked_ignored < <(git ls-files -ci --exclude-standard)
if ((${#tracked_ignored[@]})); then
  printf 'Tracked files match .gitignore:\n' >&2
  printf '  %s\n' "${tracked_ignored[@]}" >&2
  exit 1
fi

node -e '
  const manifest = require("./gre-vocab-front-end/package.json");
  const lock = require("./gre-vocab-front-end/package-lock.json");
  const locked = lock.packages[""].engines;
  if (JSON.stringify(manifest.engines) !== JSON.stringify(locked)) {
    throw new Error("package-lock.json engines do not match package.json");
  }
'

echo "Repository hygiene checks passed."
