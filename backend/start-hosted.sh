#!/bin/sh
# Hosted entrypoint (Hugging Face Spaces / any container host).
# Runs migrations, optionally seeds demo users, starts the anchoring worker, then the API.
set -e

echo "[start] applying database migrations"
alembic upgrade head

if [ "${SEED_DEMO_DATA:-true}" = "true" ]; then
  echo "[start] seeding demo users and attribute definitions (idempotent)"
  python seed.py || echo "[start] seed failed (continuing)"
fi

echo "[start] starting audit anchoring worker"
( while true; do python -m app.worker.worker; echo "[worker] exited, restarting in 5s"; sleep 5; done ) &

echo "[start] starting API on port ${PORT:-7860}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-7860}" --proxy-headers --forwarded-allow-ips '*'
