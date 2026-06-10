from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from psycopg.errors import CheckViolation

from dynamicore_wallet_credit_api.db.connection import get_connection


def _create_user_and_wallet(email_prefix: str, initial_balance: str = "0.00") -> tuple[str, str]:
    with get_connection() as connection:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO users (
                        email,
                        password_hash,
                        first_name,
                        last_name,
                        status,
                        verified_at
                    )
                    VALUES (%s, 'concurrency-test-hash-value-123', 'Concurrent', 'User', 'active', now())
                    RETURNING id
                    """,
                    (f"{email_prefix}-{uuid4()}@example.com",),
                )
                user_id = cursor.fetchone()["id"]
                cursor.execute(
                    """
                    INSERT INTO wallets (user_id, balance, available_balance)
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    (user_id, initial_balance, initial_balance),
                )
                wallet_id = cursor.fetchone()["id"]

    return str(user_id), str(wallet_id)


def _transfer_with_own_connection(
    barrier: Barrier,
    source_wallet_id: str,
    destination_wallet_id: str,
    actor_id: str,
) -> bool:
    barrier.wait()

    try:
        with get_connection() as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT procesar_transaccion(%s, %s, 80.00, 'transfer', %s, %s, 'concurrent transfer')",
                        (
                            source_wallet_id,
                            destination_wallet_id,
                            actor_id,
                            f"concurrent-transfer-{uuid4()}",
                        ),
                    )
        return True
    except CheckViolation:
        return False


def test_concurrent_transfers_do_not_overdraw_source_wallet() -> None:
    source_user_id, source_wallet_id = _create_user_and_wallet("source-concurrency", "100.00")
    _, destination_wallet_id = _create_user_and_wallet("destination-concurrency", "0.00")
    barrier = Barrier(2)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda _: _transfer_with_own_connection(
                    barrier,
                    source_wallet_id,
                    destination_wallet_id,
                    source_user_id,
                ),
                range(2),
            )
        )

    assert sorted(results) == [False, True]

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT balance FROM wallets WHERE id = %s", (source_wallet_id,))
            source_balance = cursor.fetchone()["balance"]
            cursor.execute("SELECT balance FROM wallets WHERE id = %s", (destination_wallet_id,))
            destination_balance = cursor.fetchone()["balance"]
            cursor.execute(
                """
                SELECT count(*) AS transaction_count
                FROM wallet_transactions
                WHERE source_wallet_id = %s
                  AND destination_wallet_id = %s
                  AND status = 'posted'
                """,
                (source_wallet_id, destination_wallet_id),
            )
            transaction_count = cursor.fetchone()["transaction_count"]

    assert source_balance == 20
    assert destination_balance == 80
    assert transaction_count == 1
