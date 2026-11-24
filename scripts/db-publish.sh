#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
parts="${1:-out/db-dump/parts}"
tag="db-$(date -u +%Y%m%d-%H%M)"
gh release create "$tag" --repo devodii/state-of-soroban --title "database $tag" --notes "pg_dump of the state-of-soroban database in 1.9 GB parts. Restore with scripts/db-import.sh." --prerelease
for file in "$parts"/*; do
  gh release upload "$tag" "$file" --repo devodii/state-of-soroban --clobber
done
echo "$tag"
