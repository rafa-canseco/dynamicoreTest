# Design Decisions

## Financial Ledger

Wallet balances are stored in `wallets` for fast reads, but every posted movement is also recorded in `wallet_transactions` and `wallet_transaction_entries`.

This gives the platform:

- Auditable transaction history.
- A clear separation between high-level operations and per-wallet debit/credit entries.
- Fast balance reads without losing traceability.

## PostgreSQL Consistency

Critical financial operations are implemented in PostgreSQL functions instead of relying only on application logic.

- `procesar_transaccion(...)` validates transaction shape, locks wallets with `FOR UPDATE`, verifies balances, updates balances, and writes ledger entries.
- `verificar_fondos_suficientes()` prevents insufficient-fund withdrawals/transfers at the database level.
- `generar_plan_pagos(...)` calculates and inserts credit installments in a single database transaction.

This reduces the chance of inconsistent balances when concurrent requests happen.

## Idempotency

Financial endpoints require an `Idempotency-Key` header. The API stores request hashes and completed responses in `idempotency_keys`.

Behavior:

- Same key and same body returns the original response.
- Same key with a different body returns `409 Conflict`.
- This prevents duplicate deposits, withdrawals, or transfers after client retries.

## Authorization

Authentication uses JWT access tokens. Roles are stored in `roles` and `user_roles`.

- Normal users can manage their own wallets, transactions, and credit applications.
- Only `admin` or `credit_officer` can approve credits.

## Security Considerations

- Passwords are hashed with Argon2 through `pwdlib`.
- JWT secrets are configurable through environment variables.
- Inputs are validated with Pydantic and database constraints.
- Rate limiting is applied globally, excluding health checks.
- Database foreign keys and check constraints protect core invariants.

## Indexing

Indexes are included for high-volume access patterns:

- User lookup by case-insensitive email.
- Wallet lookup by user and currency.
- Transaction history by wallet and creation date.
- Monthly transaction reporting by type/date.
- Credit dashboards by status, user, due date, and late installments.

## Local Validation

The project includes Docker-based validation:

```bash
sh scripts/validate_schema.sh
```

This creates a temporary PostgreSQL database, applies schema/functions/reports/seed data, and executes reports against both empty and seeded data.
