#!/usr/bin/env sh
# Container entrypoint: wait for dependencies, migrate, then exec the server.
set -eu

log() { printf '%s entrypoint: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1"; }

wait_for() {
    name="$1"
    attempts="${2:-60}"
    i=0
    while [ "$i" -lt "$attempts" ]; do
        if python - "$name" <<'PY'
import asyncio, sys

target = sys.argv[1]

async def main() -> int:
    if target == "database":
        from app.db.session import database_healthy
        return 0 if await database_healthy() else 1
    from app.core.redis import close_redis, init_redis
    try:
        await init_redis()
        return 0
    finally:
        await close_redis()

sys.exit(asyncio.run(main()))
PY
        then
            log "$name is ready"
            return 0
        fi
        i=$((i + 1))
        sleep 1
    done
    log "timed out waiting for $name"
    return 1
}

wait_for database
wait_for redis

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    log "applying database migrations"
    alembic upgrade head
fi

log "starting: $*"
exec "$@"
