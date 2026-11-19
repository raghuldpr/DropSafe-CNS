#!/bin/sh
# Zoho Catalyst AppSail (managed Python runtime) entrypoint.
# Dependencies are bundled in ./packages (see deploy/catalyst/build-appsail.ps1).
set -e
cd "$(dirname "$0")"
export PYTHONPATH="$PWD/packages:$PWD:${PYTHONPATH:-}"
PY="${PYTHON:-python3}"

# Migrations and seeding run once from the developer PC (see deploy/catalyst/deploy.ps1) so the API
# can start listening immediately. Set RUN_MIGRATIONS_ON_START=true to run them here instead.
if [ "${RUN_MIGRATIONS_ON_START:-false}" = "true" ]; then
  echo "[start] applying database migrations"
  $PY -m alembic upgrade head
  if [ "${SEED_DEMO_DATA:-false}" = "true" ]; then $PY seed.py || echo "[start] seed failed (continuing)"; fi
fi

echo "[start] starting audit anchoring worker"
( while true; do $PY -m app.worker.worker; echo "[worker] exited, restarting in 5s"; sleep 5; done ) &

PORT_TO_USE="${X_ZOHO_CATALYST_LISTEN_PORT:-9000}"
echo "[start] starting API on port ${PORT_TO_USE}"
exec $PY -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT_TO_USE}" --proxy-headers --forwarded-allow-ips '*'
