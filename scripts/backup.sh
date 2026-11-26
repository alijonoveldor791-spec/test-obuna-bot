#!/bin/sh
# Run from the repository directory; credentials stay inside the container.
set -eu
mkdir -p backups
stamp=$(date -u +%Y%m%dT%H%M%SZ)
target="backups/bot-$stamp.dump"
docker compose exec -T postgres pg_dump -U bot -d bot -Fc > "$target.tmp"
test -s "$target.tmp"
mv "$target.tmp" "$target"
find backups -name 'bot-*.dump' -type f -mtime +14 -delete
