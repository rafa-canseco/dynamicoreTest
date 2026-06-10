from uuid import UUID

from fastapi import HTTPException, status
from psycopg import Connection
from psycopg.errors import CheckViolation, UniqueViolation

from dynamicore_wallet_credit_api.modules.credits.schemas import (
    CreditApproveRequest,
    CreditCreateRequest,
    CreditPaymentRequest,
    CreditPaymentResponse,
    CreditRejectRequest,
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


def reject_credit(
    connection: Connection,
    credit_id: UUID,
    officer_id: UUID,
    payload: CreditRejectRequest,
) -> CreditResponse:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE credits
            SET
                status = 'rejected',
                rejected_by = %s,
                rejection_reason = %s,
                reviewed_at = now(),
                closed_at = now()
            WHERE id = %s
              AND status IN ('requested', 'under_review')
            RETURNING id
            """,
            (officer_id, payload.rejection_reason, credit_id),
        )
        updated = cursor.fetchone()

    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="credit cannot be rejected from its current state",
        )

    return _fetch_credit(connection, credit_id)


def _fetch_payment(connection: Connection, payment_id: UUID) -> CreditPaymentResponse:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                id,
                credit_id,
                schedule_id,
                wallet_transaction_id,
                payment_method::TEXT AS payment_method,
                amount,
                external_reference,
                paid_at::TEXT AS paid_at
            FROM credit_payments
            WHERE id = %s
            """,
            (payment_id,),
        )
        payment = cursor.fetchone()

    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="payment was created but could not be found",
        )

    return CreditPaymentResponse(**payment)


def pay_credit_installment(
    connection: Connection,
    user_id: UUID,
    credit_id: UUID,
    payload: CreditPaymentRequest,
) -> CreditPaymentResponse:
    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        c.id,
                        c.status::TEXT AS status,
                        c.user_id,
                        cps.id AS schedule_id,
                        cps.remaining_amount,
                        cps.status::TEXT AS schedule_status
                    FROM credits c
                    JOIN credit_payment_schedule cps ON cps.credit_id = c.id
                    WHERE c.id = %s
                      AND c.user_id = %s
                      AND cps.id = %s
                    FOR UPDATE OF c, cps
                    """,
                    (credit_id, user_id, payload.schedule_id),
                )
                row = cursor.fetchone()

                if row is None:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="credit schedule not found")

                if row["status"] not in ("approved", "active"):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="credit is not payable in its current state",
                    )

                if row["schedule_status"] == "paid":
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="installment already paid")

                if payload.amount > row["remaining_amount"]:
                    raise HTTPException(
                        status_code=422,
                        detail="payment amount cannot exceed remaining installment amount",
                    )

                wallet_transaction_id = None
                if payload.payment_method == "wallet":
                    if payload.wallet_id is None:
                        raise HTTPException(status_code=422, detail="wallet_id is required for wallet payments")

                    cursor.execute(
                        "SELECT 1 FROM wallets WHERE id = %s AND user_id = %s AND status = 'active'",
                        (payload.wallet_id, user_id),
                    )
                    if cursor.fetchone() is None:
                        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="wallet not found")

                    external_reference = payload.external_reference or f"credit-payment:{payload.schedule_id}"
                    cursor.execute(
                        "SELECT procesar_transaccion(%s, NULL, %s, 'withdrawal', %s, %s, %s)",
                        (
                            payload.wallet_id,
                            payload.amount,
                            user_id,
                            external_reference,
                            "Credit installment payment",
                        ),
                    )
                    cursor.execute(
                        """
                        SELECT id
                        FROM wallet_transactions
                        WHERE external_reference = %s
                        """,
                        (external_reference,),
                    )
                    wallet_transaction_id = cursor.fetchone()["id"]
                elif payload.wallet_id is not None:
                    raise HTTPException(status_code=422, detail="wallet_id is only allowed for wallet payments")

                cursor.execute(
                    """
                    INSERT INTO credit_payments (
                        credit_id,
                        schedule_id,
                        wallet_transaction_id,
                        payment_method,
                        amount,
                        external_reference
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        credit_id,
                        payload.schedule_id,
                        wallet_transaction_id,
                        payload.payment_method,
                        payload.amount,
                        payload.external_reference,
                    ),
                )
                payment_id = cursor.fetchone()["id"]

                cursor.execute(
                    """
                    UPDATE credit_payment_schedule
                    SET
                        remaining_amount = remaining_amount - %s,
                        status = CASE
                            WHEN remaining_amount - %s = 0 THEN 'paid'::credit_payment_status
                            WHEN due_date < CURRENT_DATE THEN 'late'::credit_payment_status
                            ELSE status
                        END,
                        paid_at = CASE
                            WHEN remaining_amount - %s = 0 THEN now()
                            ELSE paid_at
                        END
                    WHERE id = %s
                    """,
                    (payload.amount, payload.amount, payload.amount, payload.schedule_id),
                )

                cursor.execute(
                    """
                    UPDATE credits
                    SET status = 'paid',
                        closed_at = now()
                    WHERE id = %s
                      AND NOT EXISTS (
                          SELECT 1
                          FROM credit_payment_schedule
                          WHERE credit_id = %s
                            AND remaining_amount > 0
                      )
                    """,
                    (credit_id, credit_id),
                )
    except (CheckViolation, UniqueViolation) as exc:
        raise HTTPException(status_code=422, detail=str(exc).splitlines()[0]) from exc

    return _fetch_payment(connection, payment_id)
