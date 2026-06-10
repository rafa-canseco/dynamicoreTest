from uuid import UUID

from fastapi import APIRouter, Depends, Query

from dynamicore_wallet_credit_api.api.dependencies import CurrentUser, get_current_user
from dynamicore_wallet_credit_api.db.connection import get_connection
from dynamicore_wallet_credit_api.modules.wallets.schemas import (
    WalletCreateRequest,
    WalletResponse,
    WalletTransactionHistoryItem,
)
from dynamicore_wallet_credit_api.modules.wallets.service import (
    create_wallet,
    get_wallet,
    get_wallet_history,
    list_wallets,
)

router = APIRouter(prefix="/wallets", tags=["wallets"])


@router.post("", response_model=WalletResponse, status_code=201)
def create_wallet_endpoint(
    payload: WalletCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> WalletResponse:
    with get_connection() as connection:
        return create_wallet(connection, current_user.id, payload)


@router.get("", response_model=list[WalletResponse])
def list_wallets_endpoint(current_user: CurrentUser = Depends(get_current_user)) -> list[WalletResponse]:
    with get_connection() as connection:
        return list_wallets(connection, current_user.id)


@router.get("/{wallet_id}", response_model=WalletResponse)
def get_wallet_endpoint(
    wallet_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
) -> WalletResponse:
    with get_connection() as connection:
        return get_wallet(connection, current_user.id, wallet_id)


@router.get("/{wallet_id}/transactions", response_model=list[WalletTransactionHistoryItem])
def get_wallet_history_endpoint(
    wallet_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[WalletTransactionHistoryItem]:
    with get_connection() as connection:
        return get_wallet_history(connection, current_user.id, wallet_id, limit)
