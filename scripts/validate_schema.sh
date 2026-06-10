#!/usr/bin/env sh
set -eu

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required to validate the PostgreSQL schema locally." >&2
  exit 127
fi

docker compose up -d postgres

until docker compose exec postgres pg_isready -U dynamicore -d dynamicore >/dev/null 2>&1; do
  sleep 1
done

docker compose exec -T postgres psql -U dynamicore -d postgres -v ON_ERROR_STOP=1 \
  -c "DROP DATABASE IF EXISTS dynamicore_schema_validation;"

docker compose exec -T postgres psql -U dynamicore -d postgres -v ON_ERROR_STOP=1 \
  -c "CREATE DATABASE dynamicore_schema_validation;"

docker compose exec -T postgres psql -U dynamicore -d dynamicore_schema_validation \
  -v ON_ERROR_STOP=1 \
  -f /workspace/sql/001_schema.sql

docker compose exec -T postgres psql -U dynamicore -d dynamicore_schema_validation \
  -v ON_ERROR_STOP=1 \
  -f /workspace/sql/002_functions_triggers.sql

docker compose exec -T postgres psql -U dynamicore -d dynamicore_schema_validation \
  -v ON_ERROR_STOP=1 \
  -f /workspace/sql/003_reports.sql

docker compose exec -T postgres psql -U dynamicore -d dynamicore_schema_validation \
  -v ON_ERROR_STOP=1 \
  -f /workspace/sql/004_seed.sql

docker compose exec -T postgres psql -U dynamicore -d dynamicore_schema_validation \
  -v ON_ERROR_STOP=1 \
  -f /workspace/sql/003_reports.sql
