from fastapi import APIRouter

from dynamicore_wallet_credit_api.db.connection import get_connection
from dynamicore_wallet_credit_api.modules.auth.schemas import LoginRequest, RegisterRequest, TokenResponse
from dynamicore_wallet_credit_api.modules.auth.service import login_user, register_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(payload: RegisterRequest) -> TokenResponse:
    with get_connection() as connection:
        return register_user(connection, payload)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    with get_connection() as connection:
        return login_user(connection, payload)
