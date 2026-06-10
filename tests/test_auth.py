from uuid import uuid4

from fastapi.testclient import TestClient

from dynamicore_wallet_credit_api.main import app


client = TestClient(app)


def test_register_and_login_user() -> None:
    email = f"user-{uuid4()}@example.com"
    password = "super-secret-123"

    register_response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "first_name": "Test",
            "last_name": "User",
            "credit_score": 700,
            "monthly_income": 45000,
        },
    )

    assert register_response.status_code == 201
    register_body = register_response.json()
    assert register_body["token_type"] == "bearer"
    assert register_body["access_token"]
    assert register_body["user"]["email"] == email
    assert register_body["user"]["roles"] == ["user"]

    login_response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )

    assert login_response.status_code == 200
    login_body = login_response.json()
    assert login_body["token_type"] == "bearer"
    assert login_body["access_token"]
    assert login_body["user"]["email"] == email


def test_login_rejects_invalid_password() -> None:
    response = client.post(
        "/auth/login",
        json={"email": "rafa@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid credentials"}
