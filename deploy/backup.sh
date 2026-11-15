#!/bin/sh
# Runs inside the backup container: one database dump per day in /backups, the newest 14 kept.
set -u
while true; do
  stamp=$(date +%F)
  if PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -h db -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f "/backups/flame-$stamp.dump"; then
    echo "backup written: flame-$stamp.dump"
    ls -1t /backups/flame-*.dump 2>/dev/null | tail -n +15 | while read -r old; do
      unlink "$old"
    done
  else
    echo "backup FAILED for $stamp" >&2
  fi
  sleep 86400
done
