import hashlib
import json
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from psycopg import Connection
from psycopg.errors import CheckViolation, ForeignKeyViolation, UniqueViolation

from dynamicore_wallet_credit_api.modules.transactions.schemas import (
    DepositRequest,
    TransactionResponse,
    TransferRequest,
    WithdrawalRequest,
)


def _json_default(value: Any) -> str:
    if isinstance(value, UUID | Decimal):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _request_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, default=_json_default, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _require_owned_wallet(connection: Connection, user_id: UUID, wallet_id: UUID) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM wallets WHERE id = %s AND user_id = %s AND status = 'active'",
            (wallet_id, user_id),
        )
        exists = cursor.fetchone()

    if exists is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="wallet not found")


def _get_completed_idempotency_response(
    connection: Connection,
    user_id: UUID,
    idempotency_key: str,
    request_path: str,
    request_hash: str,
) -> dict[str, Any] | None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT request_hash, status::TEXT AS status, response_status_code, response_body
            FROM idempotency_keys
            WHERE user_id = %s
              AND idempotency_key = %s
            FOR UPDATE
            """,
            (user_id, idempotency_key),
        )
        existing = cursor.fetchone()

        if existing is None:
            cursor.execute(
                """
                INSERT INTO idempotency_keys (
                    user_id,
                    idempotency_key,
                    request_method,
                    request_path,
                    request_hash
                )
                VALUES (%s, %s, 'POST', %s, %s)
                """,
                (user_id, idempotency_key, request_path, request_hash),
            )
            return None

        if existing["request_hash"] != request_hash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="idempotency key reused with a different request body",
            )

        if existing["status"] == "completed":
            return existing["response_body"]

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="request with this idempotency key is already processing",
        )


def _complete_idempotency_request(
    connection: Connection,
    user_id: UUID,
    idempotency_key: str,
    response_body: dict[str, Any],
) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE idempotency_keys
            SET
                status = 'completed',
                response_status_code = 201,
                response_body = %s::JSONB
            WHERE user_id = %s
              AND idempotency_key = %s
            """,
            (json.dumps(response_body, default=_json_default), user_id, idempotency_key),
        )


def _fetch_transaction_by_reference(connection: Connection, external_reference: str) -> TransactionResponse:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                id,
                transaction_type::TEXT AS transaction_type,
                status::TEXT AS status,
                amount,
                currency,
                source_wallet_id,
                destination_wallet_id,
                external_reference
            FROM wallet_transactions
            WHERE external_reference = %s
            """,
            (external_reference,),
        )
        transaction = cursor.fetchone()

    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="transaction was processed but could not be found",
        )

    return TransactionResponse(**transaction)


def _process_transaction(
    connection: Connection,
    user_id: UUID,
    idempotency_key: str,
    request_path: str,
    payload: dict[str, Any],
    source_wallet_id: UUID | None,
    destination_wallet_id: UUID | None,
    amount: Decimal,
    transaction_type: str,
    description: str | None,
) -> TransactionResponse:
    request_hash = _request_hash(payload)
    external_reference = f"{request_path}:{idempotency_key}"

    with connection.transaction():
        existing_response = _get_completed_idempotency_response(
            connection,
            user_id,
            idempotency_key,
            request_path,
            request_hash,
        )
        if existing_response is not None:
            return TransactionResponse(**existing_response)

        if source_wallet_id is not None:
            _require_owned_wallet(connection, user_id, source_wallet_id)
        if transaction_type == "deposit" and destination_wallet_id is not None:
            _require_owned_wallet(connection, user_id, destination_wallet_id)

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT procesar_transaccion(%s, %s, %s, %s, %s, %s, %s)",
                    (
                        source_wallet_id,
                        destination_wallet_id,
                        amount,
                        transaction_type,
                        user_id,
                        external_reference,
                        description,
                    ),
                )
        except (CheckViolation, ForeignKeyViolation) as exc:
            raise HTTPException(
                status_code=422,
                detail=str(exc).splitlines()[0],
            ) from exc
        except UniqueViolation as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="transaction reference already exists",
            ) from exc

        transaction = _fetch_transaction_by_reference(connection, external_reference)
        _complete_idempotency_request(
            connection,
            user_id,
            idempotency_key,
            transaction.model_dump(mode="json"),
        )

    return transaction


def deposit(
    connection: Connection,
    user_id: UUID,
    idempotency_key: str,
    payload: DepositRequest,
) -> TransactionResponse:
    return _process_transaction(
        connection=connection,
        user_id=user_id,
        idempotency_key=idempotency_key,
        request_path="/transactions/deposit",
        payload=payload.model_dump(),
        source_wallet_id=None,
        destination_wallet_id=payload.wallet_id,
        amount=payload.amount,
        transaction_type="deposit",
        description=payload.description,
    )


def withdraw(
    connection: Connection,
    user_id: UUID,
    idempotency_key: str,
    payload: WithdrawalRequest,
) -> TransactionResponse:
    return _process_transaction(
        connection=connection,
        user_id=user_id,
        idempotency_key=idempotency_key,
        request_path="/transactions/withdraw",
        payload=payload.model_dump(),
        source_wallet_id=payload.wallet_id,
        destination_wallet_id=None,
        amount=payload.amount,
        transaction_type="withdrawal",
        description=payload.description,
    )


def transfer(
    connection: Connection,
    user_id: UUID,
    idempotency_key: str,
    payload: TransferRequest,
) -> TransactionResponse:
    return _process_transaction(
        connection=connection,
        user_id=user_id,
        idempotency_key=idempotency_key,
        request_path="/transactions/transfer",
        payload=payload.model_dump(),
        source_wallet_id=payload.source_wallet_id,
        destination_wallet_id=payload.destination_wallet_id,
        amount=payload.amount,
        transaction_type="transfer",
        description=payload.description,
    )
