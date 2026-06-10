from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from dynamicore_wallet_credit_api.core.security import hash_password
from dynamicore_wallet_credit_api.db.connection import get_connection
from dynamicore_wallet_credit_api.main import app


client = TestClient(app)


def _register_user_token(prefix: str) -> str:
    response = client.post(
        "/auth/register",
        json={
            "email": f"{prefix}-{uuid4()}@example.com",
            "password": "super-secret-123",
            "first_name": "Credit",
            "last_name": "User",
        },
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def _create_wallet(token: str) -> dict:
    response = client.post(
        "/wallets",
        json={"currency": "MXN"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    return response.json()


def _create_credit_officer_token() -> str:
    email = f"officer-{uuid4()}@example.com"
    password = "super-secret-123"

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
                    VALUES (%s, %s, 'Credit', 'Officer', 'active', now())
                    RETURNING id
                    """,
                    (email, hash_password(password)),
                )
                user_id = cursor.fetchone()["id"]
                cursor.execute(
                    """
                    INSERT INTO user_roles (user_id, role_id)
                    SELECT %s, id
                    FROM roles
                    WHERE name = 'credit_officer'
                    """,
                    (user_id,),
                )

    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_create_list_get_credit_and_empty_schedule() -> None:
    token = _register_user_token("credit-create")
    headers = {"Authorization": f"Bearer {token}"}
    wallet = _create_wallet(token)

    create_response = client.post(
        "/credits",
        json={
            "disbursement_wallet_id": wallet["id"],
            "principal_amount": "5000.00",
            "annual_interest_rate": "18.0000",
            "term_months": 12,
            "purpose": "Inventory",
        },
        headers=headers,
    )

    assert create_response.status_code == 201
    credit = create_response.json()
    assert credit["status"] == "requested"
    assert credit["monthly_payment"] is None

    list_response = client.get("/credits", headers=headers)
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [credit["id"]]

    get_response = client.get(f"/credits/{credit['id']}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["id"] == credit["id"]

    schedule_response = client.get(f"/credits/{credit['id']}/schedule", headers=headers)
    assert schedule_response.status_code == 200
    assert schedule_response.json() == []


def test_approve_credit_generates_payment_schedule() -> None:
    user_token = _register_user_token("credit-approve")
    user_headers = {"Authorization": f"Bearer {user_token}"}
    officer_token = _create_credit_officer_token()
    officer_headers = {"Authorization": f"Bearer {officer_token}"}
    wallet = _create_wallet(user_token)

    create_response = client.post(
        "/credits",
        json={
            "disbursement_wallet_id": wallet["id"],
            "principal_amount": "12000.00",
            "annual_interest_rate": "18.0000",
            "term_months": 12,
        },
        headers=user_headers,
    )
    credit = create_response.json()

    forbidden_response = client.post(
        f"/credits/{credit['id']}/approve",
        json={},
        headers=user_headers,
    )
    assert forbidden_response.status_code == 403

    approve_response = client.post(
        f"/credits/{credit['id']}/approve",
        json={},
        headers=officer_headers,
    )

    assert approve_response.status_code == 200
    approved_credit = approve_response.json()
    assert approved_credit["status"] == "approved"
    assert approved_credit["monthly_payment"] is not None

    schedule_response = client.get(f"/credits/{credit['id']}/schedule", headers=user_headers)
    assert schedule_response.status_code == 200
    schedule = schedule_response.json()
    assert len(schedule) == 12
    assert schedule[0]["installment_number"] == 1


def test_reject_credit_requires_credit_officer() -> None:
    user_token = _register_user_token("credit-reject")
    user_headers = {"Authorization": f"Bearer {user_token}"}
    officer_token = _create_credit_officer_token()
    officer_headers = {"Authorization": f"Bearer {officer_token}"}
    wallet = _create_wallet(user_token)

    create_response = client.post(
        "/credits",
        json={
            "disbursement_wallet_id": wallet["id"],
            "principal_amount": "4000.00",
            "annual_interest_rate": "18.0000",
            "term_months": 10,
        },
        headers=user_headers,
    )
    credit_id = create_response.json()["id"]

    forbidden_response = client.post(
        f"/credits/{credit_id}/reject",
        json={"rejection_reason": "Insufficient income history"},
        headers=user_headers,
    )
    assert forbidden_response.status_code == 403

    reject_response = client.post(
        f"/credits/{credit_id}/reject",
        json={"rejection_reason": "Insufficient income history"},
        headers=officer_headers,
    )

    assert reject_response.status_code == 200
    assert reject_response.json()["status"] == "rejected"


def test_pay_credit_installment_with_external_transfer_and_wallet() -> None:
    user_token = _register_user_token("credit-payment")
    user_headers = {"Authorization": f"Bearer {user_token}"}
    officer_token = _create_credit_officer_token()
    officer_headers = {"Authorization": f"Bearer {officer_token}"}
    wallet = _create_wallet(user_token)

    deposit_response = client.post(
        "/transactions/deposit",
        json={"wallet_id": wallet["id"], "amount": "1000.00"},
        headers={**user_headers, "Idempotency-Key": f"credit-payment-deposit-{uuid4()}"},
    )
    assert deposit_response.status_code == 201

    create_response = client.post(
        "/credits",
        json={
            "disbursement_wallet_id": wallet["id"],
            "principal_amount": "1200.00",
            "annual_interest_rate": "12.0000",
            "term_months": 2,
        },
        headers=user_headers,
    )
    credit = create_response.json()

    approve_response = client.post(
        f"/credits/{credit['id']}/approve",
        json={},
        headers=officer_headers,
    )
    assert approve_response.status_code == 200

    schedule = client.get(f"/credits/{credit['id']}/schedule", headers=user_headers).json()
    first_installment = schedule[0]
    second_installment = schedule[1]

    external_payment_response = client.post(
        f"/credits/{credit['id']}/payments",
        json={
            "schedule_id": first_installment["id"],
            "amount": first_installment["remaining_amount"],
            "payment_method": "external_transfer",
            "external_reference": f"external-payment-{uuid4()}",
        },
        headers=user_headers,
    )
    assert external_payment_response.status_code == 201
    assert external_payment_response.json()["payment_method"] == "external_transfer"

    wallet_payment_response = client.post(
        f"/credits/{credit['id']}/payments",
        json={
            "schedule_id": second_installment["id"],
            "amount": second_installment["remaining_amount"],
            "payment_method": "wallet",
            "wallet_id": wallet["id"],
            "external_reference": f"wallet-credit-payment-{uuid4()}",
        },
        headers=user_headers,
    )
    assert wallet_payment_response.status_code == 201
    assert wallet_payment_response.json()["wallet_transaction_id"] is not None

    paid_schedule = client.get(f"/credits/{credit['id']}/schedule", headers=user_headers).json()
    assert [item["status"] for item in paid_schedule] == ["paid", "paid"]

    paid_credit = client.get(f"/credits/{credit['id']}", headers=user_headers).json()
    assert paid_credit["status"] == "paid"

    wallet_response = client.get(f"/wallets/{wallet['id']}", headers=user_headers)
    assert wallet_response.status_code == 200
    assert Decimal(wallet_response.json()["balance"]) < Decimal("1000.00")


def test_user_cannot_access_another_users_credit() -> None:
    owner_token = _register_user_token("credit-owner")
    other_token = _register_user_token("credit-other")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    other_headers = {"Authorization": f"Bearer {other_token}"}
    wallet = _create_wallet(owner_token)

    create_response = client.post(
        "/credits",
        json={
            "disbursement_wallet_id": wallet["id"],
            "principal_amount": "3000.00",
            "annual_interest_rate": "15.0000",
            "term_months": 6,
        },
        headers=owner_headers,
    )
    credit_id = create_response.json()["id"]

    response = client.get(f"/credits/{credit_id}", headers=other_headers)

    assert response.status_code == 404
