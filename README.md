# Dynamicore Wallet Credit API

Backend technical assessment for a financial platform that combines digital wallets and credit management.

## Scope

- PostgreSQL financial schema with referential integrity, constraints, indexes, functions, and triggers.
- FastAPI REST API for authentication, wallets, transactions, and credits.
- JWT authentication, role-based authorization, rate limiting, validation, and idempotency for financial operations.
- Automated tests and Postman collection for API validation.

## Project Structure

```text
sql/       PostgreSQL schema, functions, triggers, reports, and seed data.
docs/      ER diagram and design/security decisions.
postman/   API collection for manual validation.
src/       FastAPI application source code.
tests/     Automated test suite.
```

## Local Database

Start PostgreSQL:

```bash
docker compose up -d postgres
```

Validate the current schema:

```bash
sh scripts/validate_schema.sh
```

Run the API locally:

```bash
uv run dynamicore-api
```

Run tests:

```bash
uv run pytest
```
