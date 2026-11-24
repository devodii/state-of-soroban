#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source="${1:?usage: scripts/db-import.sh <folder with the db parts, or a release tag>}"
work="out/db-restore"
rm -rf "$work"
mkdir -p "$work"
if [ -d "$source" ]; then
  cp "$source"/state-of-soroban-db.tar.* "$source"/SHA256SUMS "$work"/
else
  gh release download "$source" --repo devodii/state-of-soroban --dir "$work" --pattern 'state-of-soroban-db.tar.*' --pattern SHA256SUMS
fi
(cd "$work" && shasum -a 256 -c SHA256SUMS)
cat "$work"/state-of-soroban-db.tar.* | tar -C "$work" -xf -
docker compose up -d --wait db
docker compose exec -T db psql -U soroban -d postgres -c "DROP DATABASE IF EXISTS soroban WITH (FORCE)" -c "CREATE DATABASE soroban"
docker compose cp "$work/dump" db:/tmp/dump
docker compose exec -T db pg_restore -U soroban -d soroban -j 6 --no-owner /tmp/dump
docker compose exec -T db rm -rf /tmp/dump
docker compose exec -T db psql -U soroban -d soroban -Atc "select count(*) as repos from repos"
rm -rf "$work"
