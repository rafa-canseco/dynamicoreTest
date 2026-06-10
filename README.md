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

Prerequisites:

- Python 3.12
- uv
- Docker

Start PostgreSQL:

```bash
docker compose up -d postgres
```

Validate the current schema:

```bash
sh scripts/validate_schema.sh
```

Reset the local API database with demo data:

```bash
sh scripts/reset_local_db.sh
```

Run database migrations with Alembic:

```bash
uv run alembic upgrade head
```

Run the API locally:

```bash
uv run dynamicore-api
```

Open API docs:

```text
http://localhost:8000/docs
```

Run tests:

```bash
uv run pytest
```

## Main Endpoints

```text
POST /auth/register
POST /auth/login

POST /wallets
GET  /wallets
GET  /wallets/{wallet_id}
GET  /wallets/{wallet_id}/transactions

POST /transactions/deposit
POST /transactions/withdraw
POST /transactions/transfer

POST /credits
GET  /credits
GET  /credits/{credit_id}
GET  /credits/{credit_id}/schedule
POST /credits/{credit_id}/approve
```

Financial transaction endpoints require:

```text
Authorization: Bearer <access_token>
Idempotency-Key: <unique-client-generated-key>
```

## curl Examples

Register a user:

```bash
curl -s -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "curl.user@example.com",
    "password": "super-secret-123",
    "first_name": "Curl",
    "last_name": "User",
    "credit_score": 700,
    "monthly_income": 45000
  }'
```

Login:

```bash
curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "curl.user@example.com",
    "password": "super-secret-123"
  }'
```

Create a wallet:

```bash
curl -s -X POST http://localhost:8000/wallets \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"currency": "MXN"}'
```

Deposit funds:

```bash
curl -s -X POST http://localhost:8000/transactions/deposit \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Idempotency-Key: deposit-001" \
  -H "Content-Type: application/json" \
  -d '{
    "wallet_id": "'$WALLET_ID'",
    "amount": "1000.00",
    "description": "Initial deposit"
  }'
```

Request a credit:

```bash
curl -s -X POST http://localhost:8000/credits \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "disbursement_wallet_id": "'$WALLET_ID'",
    "principal_amount": "5000.00",
    "annual_interest_rate": "18.0000",
    "term_months": 12,
    "purpose": "Working capital"
  }'
```

Pay a credit installment:

```bash
curl -s -X POST http://localhost:8000/credits/$CREDIT_ID/payments \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "schedule_id": "'$SCHEDULE_ID'",
    "amount": "458.40",
    "payment_method": "external_transfer",
    "external_reference": "payment-001"
  }'
```

## SQL Deliverables

```text
sql/001_schema.sql              Tables, enums, constraints, foreign keys, indexes.
sql/002_functions_triggers.sql  PostgreSQL functions and triggers.
sql/003_reports.sql             Advanced reporting queries.
sql/004_seed.sql                Demo data for local testing.
```

## Documentation

- [ER diagram](docs/er-diagram.md)
- [Design decisions](docs/design-decisions.md)
- [Postman collection](postman/dynamicore-wallet-credit-api.postman_collection.json)
