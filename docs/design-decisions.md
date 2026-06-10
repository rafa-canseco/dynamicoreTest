# Decisiones De Diseno

Este documento resume las decisiones principales del proyecto y los tradeoffs considerados para una plataforma financiera con wallets y creditos.

## Modelo Financiero

El balance actual de cada wallet se guarda en `wallets` para lecturas rapidas, pero cada movimiento confirmado tambien se registra en:

- `wallet_transactions`: operacion financiera de alto nivel.
- `wallet_transaction_entries`: entradas de ledger por wallet afectada.

Esta combinacion permite consultar saldos sin recalcular todo el historial, pero conserva trazabilidad para auditoria. En un sistema productivo, tambien agregaria procesos de conciliacion periodica para comparar balance almacenado contra suma del ledger.

## Consistencia En PostgreSQL

Las operaciones financieras criticas se ejecutan dentro de PostgreSQL, no solamente en Python.

- `procesar_transaccion(...)` valida la forma de la transaccion, bloquea wallets con `FOR UPDATE`, verifica fondos, actualiza saldos y escribe el ledger.
- `verificar_fondos_suficientes()` impide retiros o transferencias sin balance suficiente desde la base de datos.
- `generar_plan_pagos(...)` calcula el plan de pagos de un credito aprobado en una transaccion.

La razon es reducir el riesgo de inconsistencias cuando hay requests concurrentes o cuando otra integracion escribe en la base en el futuro. La API valida antes, pero la base de datos conserva las invariantes finales.

## Concurrencia

Las wallets involucradas en una transaccion se bloquean con `FOR UPDATE`. Esto evita que dos retiros o transferencias simultaneas lean el mismo balance disponible y ambas intenten gastar los mismos fondos.

El proyecto incluye un test de concurrencia real que ejecuta dos transferencias simultaneas contra la misma wallet. El resultado esperado es que solo una transaccion sea aceptada y que el balance final permanezca consistente.

## Idempotencia

Los endpoints de deposito, retiro y transferencia requieren el header:

```text
Idempotency-Key
```

La API guarda el hash del request y la respuesta final en `idempotency_keys`.

Comportamiento:

- Misma key y mismo body: regresa la respuesta original.
- Misma key con body diferente: regresa `409 Conflict`.
- Key nueva: procesa una nueva operacion.

Esto previene cargos duplicados cuando un cliente reintenta una peticion por timeout, doble click o error de red.

## Estados De Credito

Los creditos usan estados explicitos para evitar transiciones ambiguas:

```text
requested -> approved/rejected -> active -> paid/defaulted/cancelled
```

La aprobacion y el rechazo requieren rol `admin` o `credit_officer`. Un usuario sin rol de aprobador puede solicitar credito y pagar cuotas, pero no puede aprobar ni rechazar creditos.

Al aprobar un credito se genera automaticamente el plan de pagos en `credit_payment_schedule`. Los pagos registrados en `credit_payments` actualizan el saldo pendiente de la cuota y pueden liquidar el credito completo cuando todas las cuotas quedan pagadas.

## Seguridad

Medidas implementadas:

- Passwords hasheados con Argon2 mediante `pwdlib`.
- JWT para autenticacion.
- Roles en `roles` y `user_roles`.
- Validacion de entrada con Pydantic.
- Constraints y foreign keys en PostgreSQL.
- Rate limiting global para reducir abuso.
- Separacion de permisos entre usuario normal y aprobador de credito.
- Idempotencia para evitar duplicidad de movimientos financieros.

Consideraciones para produccion:

- Rotacion y manejo seguro de secretos.
- Refresh tokens y revocacion de sesiones.
- Cifrado o tokenizacion de PII como `tax_id`.
- Auditoria de cambios administrativos.
- Logs estructurados sin exponer datos sensibles.

## Rendimiento E Indices

Se agregaron indices para patrones esperados de alto volumen:

- Busqueda de usuario por email case-insensitive.
- Wallets por usuario y moneda.
- Historial de transacciones por wallet y fecha.
- Reportes mensuales por tipo de transaccion.
- Dashboard de creditos por estado.
- Cuotas por credito, fecha de vencimiento y estado.
- Idempotency keys por usuario y endpoint.

Para produccion, agregaria paginacion cursor-based en historiales grandes y particionamiento de tablas de transacciones si el volumen lo justifica.

## Migraciones

El proyecto usa Alembic para aplicar el schema de forma reproducible.

```bash
uv run alembic upgrade head
```

Los scripts SQL siguen existiendo porque son parte explicita de la entrega y facilitan revisar schema, funciones, triggers y reportes por separado.

## Postman Y Swagger

Swagger permite validar rapidamente la API en:

```text
http://localhost:8000/docs
```

La coleccion Postman incluye scripts para guardar automaticamente:

- `access_token`
- `wallet_id`
- `credit_id`
- `schedule_id`

Esto reduce friccion al revisar el flujo completo.

## Mejoras Futuras

- Refresh tokens y revocacion de JWT.
- KYC/KYB real e integracion con proveedores externos.
- Cifrado de campos sensibles.
- Ledger doble entrada mas estricto con cuentas contables internas.
- Reversos, contracargos y conciliacion bancaria.
- Jobs para marcar cuotas vencidas automaticamente.
- Observabilidad con logs estructurados, metricas y tracing.
- CI con GitHub Actions.
- Paginacion cursor-based en historiales.
- Versionado de API.
- Pruebas de carga para endpoints financieros.
