# Checklist De Evaluacion

Este documento mapea los requerimientos del examen contra la implementacion del proyecto.

## Ejercicio 1: Modelado De Base De Datos Financiera

| Requisito | Implementacion | Archivos |
| --- | --- | --- |
| Usuarios con informacion personal y crediticia | Tabla `users` con datos personales, `credit_score`, `monthly_income`, estado y verificacion | `sql/001_schema.sql` |
| Cuentas/wallets | Tabla `wallets` con moneda, estado, balance y available balance | `sql/001_schema.sql` |
| Transacciones financieras | `wallet_transactions` y `wallet_transaction_entries` para operaciones y ledger | `sql/001_schema.sql` |
| Depositos, retiros y transferencias | Funcion `procesar_transaccion(...)` con validaciones por tipo | `sql/002_functions_triggers.sql` |
| Solicitudes y manejo de creditos | `credits`, `credit_payment_schedule`, `credit_payments` | `sql/001_schema.sql` |
| Integridad referencial | Foreign keys entre usuarios, wallets, transacciones, creditos y pagos | `sql/001_schema.sql` |
| Diagrama ER | Diagrama Mermaid con entidades y relaciones principales | `docs/er-diagram.md` |
| Justificacion de diseno y seguridad | Documento de decisiones tecnicas y tradeoffs | `docs/design-decisions.md` |

## Ejercicio 2: Consultas Avanzadas En PostgreSQL

| Consulta | Implementacion | Archivo |
| --- | --- | --- |
| Balance por usuario mostrando wallets | Query de usuarios, wallets, balances y actividad | `sql/003_reports.sql` |
| Transacciones mensuales por tipo con crecimiento | Query con agregacion mensual y comparacion contra mes anterior | `sql/003_reports.sql` |
| Dashboard de estado de creditos y morosidad | Query por estado, montos y porcentaje de morosidad | `sql/003_reports.sql` |
| Usuarios con mejor comportamiento crediticio | Query con pagos a tiempo, pagos tardios y creditos aprobados | `sql/003_reports.sql` |

## Ejercicio 3: Funciones Y Triggers En PostgreSQL

| Requisito | Implementacion | Archivo |
| --- | --- | --- |
| Funcion para procesar transacciones entre wallets | `procesar_transaccion(...)` bloquea wallets, valida fondos, actualiza saldos y escribe ledger | `sql/002_functions_triggers.sql` |
| Trigger para impedir operaciones sin fondos | `verificar_fondos_suficientes()` y triggers asociados | `sql/002_functions_triggers.sql` |
| Funcion para generar cuotas de credito | `generar_plan_pagos(credito_id UUID)` calcula cuotas e inserta calendario | `sql/002_functions_triggers.sql` |
| Prevencion de inconsistencias | Constraints, triggers, transacciones y locks `FOR UPDATE` | `sql/001_schema.sql`, `sql/002_functions_triggers.sql` |

## Ejercicio 4: API REST Fintech

| Requisito | Implementacion | Archivos |
| --- | --- | --- |
| Registro y autenticacion | `POST /auth/register`, `POST /auth/login` | `src/dynamicore_wallet_credit_api/api/auth.py` |
| Manejo de wallets | Crear, listar, consultar saldo e historial | `src/dynamicore_wallet_credit_api/api/wallets.py` |
| Depositos, retiros y transferencias | Endpoints de transacciones con idempotencia | `src/dynamicore_wallet_credit_api/api/transactions.py` |
| Solicitud y gestion de creditos | Crear, listar, consultar, aprobar, rechazar, consultar plan y pagar cuota | `src/dynamicore_wallet_credit_api/api/credits.py` |
| Validacion rigurosa | Schemas Pydantic por modulo | `src/dynamicore_wallet_credit_api/modules/*/schemas.py` |
| Manejo de errores HTTP | `HTTPException` con codigos `401`, `403`, `404`, `409`, `422` | `src/dynamicore_wallet_credit_api/modules/*/service.py` |
| JWT y roles | JWT en auth, roles `user`, `admin`, `credit_officer` | `src/dynamicore_wallet_credit_api/core/security.py`, `src/dynamicore_wallet_credit_api/api/dependencies.py` |
| Rate limiting | Middleware global con headers de limite | `src/dynamicore_wallet_credit_api/middleware/rate_limit.py` |
| Tests por endpoint | Tests de auth, wallets, transacciones, creditos, rate limit y health | `tests/` |
| Tests de concurrencia | Transferencias simultaneas contra la misma wallet | `tests/test_concurrency.py` |
| Coleccion Postman | Coleccion con scripts para guardar variables | `postman/dynamicore-wallet-credit-api.postman_collection.json` |
| Documentacion API | Swagger automatico de FastAPI y README con flujo manual | `README.md`, `/docs` |

## Rendimiento Y Operacion

| Criterio | Implementacion |
| --- | --- |
| Indices apropiados | Indices para email, wallets por usuario, transacciones por wallet/fecha, creditos por estado y cuotas por vencimiento |
| Alto volumen | Ledger separado, consultas indexadas e idempotencia para reintentos |
| Migraciones | Alembic con migracion inicial reproducible |
| Validacion local | Scripts para resetear DB, validar schema y correr tests |

## Validacion Recomendada

```bash
docker compose up -d postgres
sh scripts/reset_local_db.sh
uv run pytest
sh scripts/validate_schema.sh
uv run dynamicore-api
```

Resultado esperado de tests:

```text
20 passed
```
