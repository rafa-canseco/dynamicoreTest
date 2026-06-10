from uuid import UUID

from fastapi import HTTPException, status
from psycopg import Connection
from psycopg.errors import CheckViolation, UniqueViolation

from dynamicore_wallet_credit_api.modules.credits.schemas import (
    CreditApproveRequest,
    CreditCreateRequest,
    CreditResponse,
    CreditScheduleItem,
)


def _fetch_credit(connection: Connection, credit_id: UUID, user_id: UUID | None = None) -> CreditResponse:
    conditions = ["id = %s"]
    params: list[object] = [credit_id]

    if user_id is not None:
        conditions.append("user_id = %s")
        params.append(user_id)

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT
                id,
                user_id,
                disbursement_wallet_id,
                status::TEXT AS status,
                principal_amount,
                annual_interest_rate,
                term_months,
                purpose,
                monthly_payment
            FROM credits
            WHERE {" AND ".join(conditions)}
            """,
            params,
        )
        credit = cursor.fetchone()

    if credit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="credit not found")

    return CreditResponse(**credit)


def create_credit(connection: Connection, user_id: UUID, payload: CreditCreateRequest) -> CreditResponse:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1
            FROM wallets
            WHERE id = %s
              AND user_id = %s
              AND status = 'active'
            """,
            (payload.disbursement_wallet_id, user_id),
        )
        wallet = cursor.fetchone()

        if wallet is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="wallet not found")

        cursor.execute(
            """
            INSERT INTO credits (
                user_id,
                disbursement_wallet_id,
                principal_amount,
                annual_interest_rate,
                term_months,
                purpose
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                user_id,
                payload.disbursement_wallet_id,
                payload.principal_amount,
                payload.annual_interest_rate,
                payload.term_months,
                payload.purpose,
            ),
        )
        credit_id = cursor.fetchone()["id"]

    return _fetch_credit(connection, credit_id, user_id)


def list_credits(connection: Connection, user_id: UUID) -> list[CreditResponse]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                id,
                user_id,
                disbursement_wallet_id,
                status::TEXT AS status,
                principal_amount,
                annual_interest_rate,
                term_months,
                purpose,
                monthly_payment
            FROM credits
            WHERE user_id = %s
            ORDER BY created_at DESC
            """,
            (user_id,),
        )
        return [CreditResponse(**row) for row in cursor.fetchall()]


def get_credit(connection: Connection, user_id: UUID, credit_id: UUID) -> CreditResponse:
    return _fetch_credit(connection, credit_id, user_id)


def get_credit_schedule(connection: Connection, user_id: UUID, credit_id: UUID) -> list[CreditScheduleItem]:
    get_credit(connection, user_id, credit_id)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                id,
                installment_number,
                due_date::TEXT AS due_date,
                principal_amount,
                interest_amount,
                total_amount,
                remaining_amount,
                status::TEXT AS status
            FROM credit_payment_schedule
            WHERE credit_id = %s
            ORDER BY installment_number
            """,
            (credit_id,),
        )
        return [CreditScheduleItem(**row) for row in cursor.fetchall()]


def approve_credit(
    connection: Connection,
    credit_id: UUID,
    officer_id: UUID,
    payload: CreditApproveRequest,
) -> CreditResponse:
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE credits
                    SET
                        status = 'approved',
                        annual_interest_rate = COALESCE(%s, annual_interest_rate),
                        term_months = COALESCE(%s, term_months),
                        approved_by = %s,
                        approved_at = now(),
                        reviewed_at = now()
                    WHERE id = %s
                      AND status IN ('requested', 'under_review')
                    RETURNING id
                    """,
                    (
                        payload.annual_interest_rate,
                        payload.term_months,
                        officer_id,
                        credit_id,
                    ),
                )
                updated = cursor.fetchone()

                if updated is None:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="credit cannot be approved from its current state",
                    )

                cursor.execute("SELECT generar_plan_pagos(%s)", (credit_id,))
    except (CheckViolation, UniqueViolation) as exc:
        raise HTTPException(status_code=422, detail=str(exc).splitlines()[0]) from exc

    return _fetch_credit(connection, credit_id)
