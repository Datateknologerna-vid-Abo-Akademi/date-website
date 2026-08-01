#!/bin/sh

set -eu

legacy_pgdata="/var/lib/postgresql/data"
target_pgdata="${PGDATA:-$legacy_pgdata}"

if [ "$target_pgdata" != "$legacy_pgdata" ]; then
  case "$target_pgdata" in
    "$legacy_pgdata"/*) ;;
    *)
      echo "Refusing to migrate PostgreSQL data to unexpected PGDATA path: $target_pgdata" >&2
      exit 1
      ;;
  esac

  if [ -f "$legacy_pgdata/PG_VERSION" ] && [ ! -f "$target_pgdata/PG_VERSION" ]; then
    echo "Migrating existing PostgreSQL data directory into $target_pgdata"
    mkdir -p "$target_pgdata"

    for entry in "$legacy_pgdata"/* "$legacy_pgdata"/.[!.]* "$legacy_pgdata"/..?*; do
      [ -e "$entry" ] || continue
      [ "$entry" = "$target_pgdata" ] && continue
      mv "$entry" "$target_pgdata"/
    done
  fi
fi

if [ "$#" -eq 0 ]; then
  set -- postgres
fi

exec docker-entrypoint.sh "$@"
