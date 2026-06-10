from uuid import uuid4

from fastapi.testclient import TestClient

from dynamicore_wallet_credit_api.main import app


client = TestClient(app)


def _register_user_token() -> str:
    email = f"wallet-user-{uuid4()}@example.com"
    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "super-secret-123",
            "first_name": "Wallet",
            "last_name": "User",
        },
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def test_wallet_endpoints_require_authentication() -> None:
    response = client.get("/wallets")

    assert response.status_code == 401
    assert response.json() == {"detail": "missing bearer token"}


def test_create_list_get_wallet_and_empty_history() -> None:
    token = _register_user_token()
    headers = {"Authorization": f"Bearer {token}"}

    create_response = client.post("/wallets", json={"currency": "MXN"}, headers=headers)

    assert create_response.status_code == 201
    wallet = create_response.json()
    assert wallet["currency"] == "MXN"
    assert wallet["status"] == "active"
    assert wallet["balance"] == "0.00"
    assert wallet["available_balance"] == "0.00"

    list_response = client.get("/wallets", headers=headers)
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [wallet["id"]]

    get_response = client.get(f"/wallets/{wallet['id']}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["id"] == wallet["id"]

    history_response = client.get(f"/wallets/{wallet['id']}/transactions", headers=headers)
    assert history_response.status_code == 200
    assert history_response.json() == []


def test_create_wallet_rejects_duplicate_active_currency() -> None:
    token = _register_user_token()
    headers = {"Authorization": f"Bearer {token}"}

    first_response = client.post("/wallets", json={"currency": "MXN"}, headers=headers)
    second_response = client.post("/wallets", json={"currency": "MXN"}, headers=headers)

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json() == {"detail": "active wallet already exists for this currency"}
