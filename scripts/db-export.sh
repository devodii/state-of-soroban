#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
out="${1:-out/db-dump}"
rm -rf "$out"
mkdir -p "$out/parts"
docker compose up -d --wait db
docker compose exec -T db rm -rf /tmp/dump
docker compose exec -T db pg_dump -U soroban -d soroban -Fd -j 6 -Z 6 -f /tmp/dump
docker compose cp db:/tmp/dump "$out/dump"
docker compose exec -T db rm -rf /tmp/dump
tar -C "$out" -cf - dump | split -b 1900m - "$out/parts/state-of-soroban-db.tar."
rm -rf "$out/dump"
(cd "$out/parts" && shasum -a 256 * > SHA256SUMS)
ls -lh "$out/parts"
