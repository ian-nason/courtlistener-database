#!/usr/bin/env bash
# CourtListener bulk data (Free Law Project): the latest non-empty file of every kind listed
# in docs/bulk_manifest.json (judges, positions, courts, financial disclosures, ...).
# https://www.courtlistener.com/help/api/bulk-data/
set -uo pipefail
cd "$(dirname "$0")"
mkdir -p data/raw
failed=0
python3 -c "import json; [print(v['url']) for v in json.load(open('docs/bulk_manifest.json')).values()]" | while read -r url; do
  f="data/raw/$(basename "$url")"
  [[ -s "$f" ]] && continue
  curl --fail -L --retry 5 --retry-delay 15 -sS -A "Mozilla/5.0 (datapond-maintenance)" -o "$f.part" "$url" && mv "$f.part" "$f" && echo "ok $f $(stat -c %s "$f")" || { rm -f "$f.part"; echo "FAIL $f" >&2; failed=$((failed + 1)); }
done
ls data/raw | wc -l
