#!/usr/bin/env bash
# Compatibility entry point: every download uses the verified, non-overwriting path.
set -euo pipefail
root="$(cd "$(dirname "$0")" && pwd)"
exec "${PYTHON:-python3}" "$root/download_sources.py" \
  --manifest "$root/docs/bulk_manifest.json" --raw-dir "$root/data/raw" \
  --receipt "$root/data/verified-manifest.json" "$@"
