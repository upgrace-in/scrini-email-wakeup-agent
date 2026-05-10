#!/usr/bin/env sh
# Shell into the Docker-published Postgres (matches docker-compose db service).
# Usage: ./scripts/psql-wakeup.sh
#        WAKEUP_POSTGRES_PORT=5434 ./scripts/psql-wakeup.sh -c '\dt'
PORT="${WAKEUP_POSTGRES_PORT:-5433}"
exec psql "postgresql://wakeup:wakeup@127.0.0.1:${PORT}/wakeup" "$@"
