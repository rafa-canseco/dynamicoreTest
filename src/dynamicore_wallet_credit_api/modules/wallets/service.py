from uuid import UUID

from fastapi import HTTPException, status
from psycopg import Connection
from psycopg.errors import UniqueViolation

from dynamicore_wallet_credit_api.modules.wallets.schemas import (
    WalletCreateRequest,
    WalletResponse,
    WalletTransactionHistoryItem,
)


def create_wallet(connection: Connection, user_id: UUID, payload: WalletCreateRequest) -> WalletResponse:
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO wallets (user_id, currency)
                VALUES (%s, %s)
                RETURNING
                    id,
                    user_id,
                    currency,
                    status::TEXT AS status,
                    balance,
                    available_balance
                """,
                (user_id, payload.currency),
            )
            wallet = cursor.fetchone()
    except UniqueViolation as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="active wallet already exists for this currency",
        ) from exc

    return WalletResponse(**wallet)


def list_wallets(connection: Connection, user_id: UUID) -> list[WalletResponse]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                id,
                user_id,
                currency,
                status::TEXT AS status,
                balance,
                available_balance
            FROM wallets
            WHERE user_id = %s
            ORDER BY currency, created_at
            """,
            (user_id,),
        )
        return [WalletResponse(**row) for row in cursor.fetchall()]


def get_wallet(connection: Connection, user_id: UUID, wallet_id: UUID) -> WalletResponse:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                id,
                user_id,
                currency,
                status::TEXT AS status,
                balance,
                available_balance
            FROM wallets
            WHERE id = %s
              AND user_id = %s
            """,
            (wallet_id, user_id),
        )
        wallet = cursor.fetchone()

    if wallet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="wallet not found")

    return WalletResponse(**wallet)


def get_wallet_history(
    connection: Connection,
    user_id: UUID,
    wallet_id: UUID,
    limit: int,
) -> list[WalletTransactionHistoryItem]:
    get_wallet(connection, user_id, wallet_id)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                wt.id AS transaction_id,
                wt.transaction_type::TEXT AS transaction_type,
                wt.status::TEXT AS transaction_status,
                wte.direction::TEXT AS direction,
                wte.amount,
                wte.balance_after,
                CASE
                    WHEN wt.source_wallet_id = %(wallet_id)s THEN wt.destination_wallet_id
                    ELSE wt.source_wallet_id
                END AS counterparty_wallet_id,
                wt.description,
                wte.created_at::TEXT AS created_at
            FROM wallet_transaction_entries wte
            JOIN wallet_transactions wt ON wt.id = wte.transaction_id
            WHERE wte.wallet_id = %(wallet_id)s
            ORDER BY wte.created_at DESC
            LIMIT %(limit)s
            """,
            {"wallet_id": wallet_id, "limit": limit},
        )
        return [WalletTransactionHistoryItem(**row) for row in cursor.fetchall()]
