from typing import Any

from fastapi import HTTPException, status
from psycopg import Connection
from psycopg.errors import UniqueViolation

from dynamicore_wallet_credit_api.core.security import create_access_token, hash_password, verify_password
from dynamicore_wallet_credit_api.modules.auth.schemas import LoginRequest, RegisterRequest, TokenResponse, UserResponse


def _get_user_roles(connection: Connection, user_id: str) -> list[str]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT r.name::TEXT AS name
            FROM user_roles ur
            JOIN roles r ON r.id = ur.role_id
            WHERE ur.user_id = %s
            ORDER BY r.name
            """,
            (user_id,),
        )
        return [row["name"] for row in cursor.fetchall()]


def _build_token_response(user: dict[str, Any], roles: list[str]) -> TokenResponse:
    access_token = create_access_token(user["id"], roles)
    return TokenResponse(
        access_token=access_token,
        user=UserResponse(
            id=user["id"],
            email=user["email"],
            first_name=user["first_name"],
            last_name=user["last_name"],
            status=user["status"],
            roles=roles,
        ),
    )


def register_user(connection: Connection, payload: RegisterRequest) -> TokenResponse:
    password_digest = hash_password(payload.password)

    try:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO users (
                        email,
                        password_hash,
                        first_name,
                        last_name,
                        phone_number,
                        tax_id,
                        status,
                        credit_score,
                        monthly_income,
                        verified_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, 'active', %s, %s, now())
                    RETURNING
                        id,
                        email,
                        first_name,
                        last_name,
                        status::TEXT AS status
                    """,
                    (
                        payload.email.lower(),
                        password_digest,
                        payload.first_name,
                        payload.last_name,
                        payload.phone_number,
                        payload.tax_id,
                        payload.credit_score,
                        payload.monthly_income,
                    ),
                )
                user = cursor.fetchone()

                cursor.execute(
                    """
                    INSERT INTO user_roles (user_id, role_id)
                    SELECT %s, id
                    FROM roles
                    WHERE name = 'user'
                    """,
                    (user["id"],),
                )
    except UniqueViolation as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="email or tax_id already exists",
        ) from exc

    roles = _get_user_roles(connection, user["id"])
    return _build_token_response(user, roles)


def login_user(connection: Connection, payload: LoginRequest) -> TokenResponse:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                id,
                email,
                password_hash,
                first_name,
                last_name,
                status::TEXT AS status
            FROM users
            WHERE lower(email) = lower(%s)
            """,
            (payload.email,),
        )
        user = cursor.fetchone()

    if user is None or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid credentials",
        )

    if user["status"] != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="user is not active",
        )

    roles = _get_user_roles(connection, user["id"])
    return _build_token_response(user, roles)
