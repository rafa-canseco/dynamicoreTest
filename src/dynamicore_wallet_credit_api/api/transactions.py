from typing import Annotated

from fastapi import APIRouter, Depends, Header

from dynamicore_wallet_credit_api.api.dependencies import CurrentUser, get_current_user
from dynamicore_wallet_credit_api.db.connection import get_connection
from dynamicore_wallet_credit_api.modules.transactions.schemas import (
    DepositRequest,
    TransactionResponse,
    TransferRequest,
    WithdrawalRequest,
)
from dynamicore_wallet_credit_api.modules.transactions.service import deposit, transfer, withdraw

router = APIRouter(prefix="/transactions", tags=["transactions"])

IdempotencyKey = Annotated[str, Header(min_length=8, max_length=160, alias="Idempotency-Key")]


@router.post("/deposit", response_model=TransactionResponse, status_code=201)
def deposit_endpoint(
    payload: DepositRequest,
    idempotency_key: IdempotencyKey,
    current_user: CurrentUser = Depends(get_current_user),
) -> TransactionResponse:
    with get_connection() as connection:
        return deposit(connection, current_user.id, idempotency_key, payload)


@router.post("/withdraw", response_model=TransactionResponse, status_code=201)
def withdraw_endpoint(
    payload: WithdrawalRequest,
    idempotency_key: IdempotencyKey,
    current_user: CurrentUser = Depends(get_current_user),
) -> TransactionResponse:
    with get_connection() as connection:
        return withdraw(connection, current_user.id, idempotency_key, payload)


@router.post("/transfer", response_model=TransactionResponse, status_code=201)
def transfer_endpoint(
    payload: TransferRequest,
    idempotency_key: IdempotencyKey,
    current_user: CurrentUser = Depends(get_current_user),
) -> TransactionResponse:
    with get_connection() as connection:
        return transfer(connection, current_user.id, idempotency_key, payload)
