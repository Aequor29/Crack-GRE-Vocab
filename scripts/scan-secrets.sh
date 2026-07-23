#!/usr/bin/env bash
set -euo pipefail

case "${1:-current}" in
  current)
    gitleaks dir --redact --no-banner .
    ;;
  history)
    gitleaks git --redact --no-banner --log-opts="--all" .
    ;;
  *)
    echo "usage: $0 [current|history]" >&2
    exit 2
    ;;
esac
