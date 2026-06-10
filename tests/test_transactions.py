from uuid import uuid4

from fastapi.testclient import TestClient

from dynamicore_wallet_credit_api.main import app


client = TestClient(app)


def _register_user_token(prefix: str) -> str:
    response = client.post(
        "/auth/register",
        json={
            "email": f"{prefix}-{uuid4()}@example.com",
            "password": "super-secret-123",
            "first_name": "Transaction",
            "last_name": "User",
        },
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def _create_wallet(token: str, currency: str = "MXN") -> dict:
    response = client.post(
        "/wallets",
        json={"currency": currency},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    return response.json()


def test_deposit_withdraw_and_wallet_history() -> None:
    token = _register_user_token("deposit")
    headers = {"Authorization": f"Bearer {token}"}
    wallet = _create_wallet(token)

    deposit_response = client.post(
        "/transactions/deposit",
        json={"wallet_id": wallet["id"], "amount": "100.00", "description": "test deposit"},
        headers={**headers, "Idempotency-Key": f"deposit-{uuid4()}"},
    )

    assert deposit_response.status_code == 201
    deposit = deposit_response.json()
    assert deposit["transaction_type"] == "deposit"
    assert deposit["amount"] == "100.00"

    withdraw_response = client.post(
        "/transactions/withdraw",
        json={"wallet_id": wallet["id"], "amount": "25.00", "description": "test withdrawal"},
        headers={**headers, "Idempotency-Key": f"withdraw-{uuid4()}"},
    )

    assert withdraw_response.status_code == 201
    assert withdraw_response.json()["transaction_type"] == "withdrawal"

    wallet_response = client.get(f"/wallets/{wallet['id']}", headers=headers)
    assert wallet_response.status_code == 200
    assert wallet_response.json()["balance"] == "75.00"

    history_response = client.get(f"/wallets/{wallet['id']}/transactions", headers=headers)
    assert history_response.status_code == 200
    assert [item["transaction_type"] for item in history_response.json()] == ["withdrawal", "deposit"]


def test_transfer_between_wallets() -> None:
    source_token = _register_user_token("source")
    destination_token = _register_user_token("destination")
    source_headers = {"Authorization": f"Bearer {source_token}"}
    destination_headers = {"Authorization": f"Bearer {destination_token}"}
    source_wallet = _create_wallet(source_token)
    destination_wallet = _create_wallet(destination_token)

    deposit_response = client.post(
        "/transactions/deposit",
        json={"wallet_id": source_wallet["id"], "amount": "200.00"},
        headers={**source_headers, "Idempotency-Key": f"deposit-{uuid4()}"},
    )
    assert deposit_response.status_code == 201

    transfer_response = client.post(
        "/transactions/transfer",
        json={
            "source_wallet_id": source_wallet["id"],
            "destination_wallet_id": destination_wallet["id"],
            "amount": "80.00",
        },
        headers={**source_headers, "Idempotency-Key": f"transfer-{uuid4()}"},
    )

    assert transfer_response.status_code == 201
    assert transfer_response.json()["transaction_type"] == "transfer"

    source_balance = client.get(f"/wallets/{source_wallet['id']}", headers=source_headers).json()["balance"]
    destination_balance = client.get(
        f"/wallets/{destination_wallet['id']}",
        headers=destination_headers,
    ).json()["balance"]

    assert source_balance == "120.00"
    assert destination_balance == "80.00"


def test_withdraw_rejects_insufficient_funds() -> None:
    token = _register_user_token("insufficient")
    headers = {"Authorization": f"Bearer {token}"}
    wallet = _create_wallet(token)

    response = client.post(
        "/transactions/withdraw",
        json={"wallet_id": wallet["id"], "amount": "10.00"},
        headers={**headers, "Idempotency-Key": f"withdraw-{uuid4()}"},
    )

    assert response.status_code == 422
    assert "insufficient funds" in response.json()["detail"]


def test_transaction_idempotency_returns_same_response() -> None:
    token = _register_user_token("idempotent")
    headers = {"Authorization": f"Bearer {token}"}
    wallet = _create_wallet(token)
    idempotency_key = f"deposit-{uuid4()}"
    payload = {"wallet_id": wallet["id"], "amount": "50.00"}

    first_response = client.post(
        "/transactions/deposit",
        json=payload,
        headers={**headers, "Idempotency-Key": idempotency_key},
    )
    second_response = client.post(
        "/transactions/deposit",
        json=payload,
        headers={**headers, "Idempotency-Key": idempotency_key},
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert second_response.json() == first_response.json()

    wallet_response = client.get(f"/wallets/{wallet['id']}", headers=headers)
    assert wallet_response.json()["balance"] == "50.00"


def test_transaction_idempotency_rejects_different_body() -> None:
    token = _register_user_token("idempotency-conflict")
    headers = {"Authorization": f"Bearer {token}"}
    wallet = _create_wallet(token)
    idempotency_key = f"deposit-{uuid4()}"

    first_response = client.post(
        "/transactions/deposit",
        json={"wallet_id": wallet["id"], "amount": "50.00"},
        headers={**headers, "Idempotency-Key": idempotency_key},
    )
    second_response = client.post(
        "/transactions/deposit",
        json={"wallet_id": wallet["id"], "amount": "75.00"},
        headers={**headers, "Idempotency-Key": idempotency_key},
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409
