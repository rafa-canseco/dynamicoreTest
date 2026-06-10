# Dynamicore Wallet Credit API

Prueba tecnica backend para una plataforma financiera que combina wallets digitales y gestion de creditos.

El proyecto esta construido con FastAPI, PostgreSQL, Alembic, JWT, control de roles, rate limiting, idempotencia para operaciones financieras y una coleccion Postman para validacion manual.

## Alcance

- Modelo financiero en PostgreSQL con integridad referencial, constraints, indices, funciones y triggers.
- API REST para autenticacion, wallets, transacciones y creditos.
- Autenticacion con JWT y autorizacion por roles.
- Idempotencia en depositos, retiros y transferencias.
- Rate limiting global.
- Tests automatizados, incluyendo concurrencia real en transferencias.
- Migraciones con Alembic.
- Documentacion de diseno, diagrama ER, queries SQL y coleccion Postman.

## Estructura

```text
sql/         Schema, funciones, triggers, reportes y seed data.
docs/        Diagrama ER, decisiones de diseno y checklist de evaluacion.
postman/     Coleccion para probar la API manualmente.
src/         Codigo fuente de FastAPI.
tests/       Suite de tests automatizados.
migrations/  Migraciones Alembic.
scripts/     Scripts locales de validacion y reset de base de datos.
```

## Requisitos Locales

- Python 3.12
- uv
- Docker

## Levantar Desde Cero Para Evaluacion

Clonar el repositorio:

```bash
git clone git@github.com:rafa-canseco/dynamicoreTest.git
cd dynamicoreTest
```

Instalar dependencias con `uv`:

```bash
uv sync
```

Levantar PostgreSQL local con Docker:

```bash
docker compose up -d postgres
```

Crear la base desde cero con Alembic y cargar datos demo:

```bash
sh scripts/reset_local_db.sh
```

Validar que todo funcione:

```bash
uv run pytest
sh scripts/validate_schema.sh
```

Levantar la API:

```bash
uv run dynamicore-api
```

Abrir la documentacion interactiva:

```text
http://localhost:8000/docs
```

La configuracion local por default apunta a:

```text
postgresql://dynamicore:dynamicore@localhost:5432/dynamicore
```

No es necesario crear un archivo `.env` para probar localmente. Si se desea cambiar la configuracion, se puede usar `.env.example` como referencia.

## Como Levantar El Proyecto

Desde la raiz del repo:

```bash
docker compose up -d postgres
```

Reiniciar la base local con migraciones Alembic y datos demo:

```bash
sh scripts/reset_local_db.sh
```

Correr la API:

```bash
uv run dynamicore-api
```

Abrir Swagger:

```text
http://localhost:8000/docs
```

Correr tests:

```bash
uv run pytest
```

Resultado esperado:

```text
20 passed
```

## Validacion SQL

Validar schema, funciones, triggers, seed data y reportes:

```bash
sh scripts/validate_schema.sh
```

Ejecutar migraciones manualmente:

```bash
uv run alembic upgrade head
```

## Endpoints Principales

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
POST /credits/{credit_id}/reject
POST /credits/{credit_id}/payments
```

Los endpoints financieros de transacciones requieren:

```text
Authorization: Bearer <access_token>
Idempotency-Key: <client-generated-unique-key>
```

La aprobacion y rechazo de creditos requiere rol `admin` o `credit_officer`.

## Flujo Rapido Para Probar En Swagger

1. Registrar usuario con `POST /auth/register`.
2. Copiar el `access_token`.
3. Usar `Authorize` en Swagger con `Bearer <access_token>`.
4. Crear wallet con `POST /wallets`.
5. Depositar fondos con `POST /transactions/deposit` usando un `Idempotency-Key` unico.
6. Solicitar credito con `POST /credits`.
7. Asignar rol `credit_officer` al usuario si se quiere probar aprobacion/rechazo localmente.
8. Hacer login de nuevo para obtener un JWT con el rol actualizado.
9. Aprobar credito con `POST /credits/{credit_id}/approve`.
10. Consultar plan de pagos con `GET /credits/{credit_id}/schedule`.
11. Pagar una cuota con `POST /credits/{credit_id}/payments`.

## Probar Rol Credit Officer Localmente

Para aprobar o rechazar creditos, el JWT debe incluir `credit_officer` o `admin`.

Despues de registrar un usuario, se puede promover localmente con:

```bash
docker compose exec postgres psql -U dynamicore -d dynamicore -c "
INSERT INTO user_roles (user_id, role_id)
SELECT '<USER_ID>', id
FROM roles
WHERE name = 'credit_officer'
ON CONFLICT DO NOTHING;
"
```

Despues de cambiar el rol, hacer login otra vez. Los roles van embebidos en el JWT, por lo que un token anterior no refleja cambios posteriores en base de datos.

## Ejemplos curl

Registrar usuario:

```bash
curl -s -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "curl.user.001@example.com",
    "password": "super-secret-123",
    "first_name": "Curl",
    "last_name": "User",
    "phone_number": "+525500000001",
    "tax_id": "RFCURL001",
    "credit_score": 700,
    "monthly_income": 45000
  }'
```

Login:

```bash
curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "curl.user.001@example.com",
    "password": "super-secret-123"
  }'
```

Crear wallet:

```bash
curl -s -X POST http://localhost:8000/wallets \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"currency": "MXN"}'
```

Depositar fondos:

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

Solicitar credito:

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

Aprobar credito:

```bash
curl -s -X POST http://localhost:8000/credits/$CREDIT_ID/approve \
  -H "Authorization: Bearer $CREDIT_OFFICER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "annual_interest_rate": "18.0000",
    "term_months": 12
  }'
```

Pagar cuota:

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

## Postman

Importar:

```text
postman/dynamicore-wallet-credit-api.postman_collection.json
```

La coleccion guarda automaticamente variables como:

```text
access_token
wallet_id
credit_id
schedule_id
```

Esto permite correr el flujo manual sin copiar todos los IDs entre requests.

## Entregables SQL

```text
sql/001_schema.sql              Tablas, enums, constraints, foreign keys e indices.
sql/002_functions_triggers.sql  Funciones y triggers PostgreSQL.
sql/003_reports.sql             Consultas avanzadas de reportes fintech.
sql/004_seed.sql                Datos demo para validacion local.
```

## Documentacion

- [Diagrama ER](docs/er-diagram.md)
- [Decisiones de diseno](docs/design-decisions.md)
- [Checklist de evaluacion](docs/evaluation-checklist.md)
- [Coleccion Postman](postman/dynamicore-wallet-credit-api.postman_collection.json)
