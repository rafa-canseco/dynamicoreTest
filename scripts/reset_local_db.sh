#!/usr/bin/env sh
set -eu

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required to reset the local PostgreSQL database." >&2
  exit 127
fi

docker compose up -d postgres

until docker compose exec postgres pg_isready -U dynamicore -d dynamicore >/dev/null 2>&1; do
  sleep 1
done

docker compose exec -T postgres psql -U dynamicore -d postgres -v ON_ERROR_STOP=1 \
  -c "DROP DATABASE IF EXISTS dynamicore;"

docker compose exec -T postgres psql -U dynamicore -d postgres -v ON_ERROR_STOP=1 \
  -c "CREATE DATABASE dynamicore;"

docker compose exec -T postgres psql -U dynamicore -d dynamicore \
  -v ON_ERROR_STOP=1 \
  -f /workspace/sql/001_schema.sql

docker compose exec -T postgres psql -U dynamicore -d dynamicore \
  -v ON_ERROR_STOP=1 \
  -f /workspace/sql/002_functions_triggers.sql

docker compose exec -T postgres psql -U dynamicore -d dynamicore \
  -v ON_ERROR_STOP=1 \
  -f /workspace/sql/004_seed.sql
