from uuid import UUID

from fastapi import APIRouter, Depends

from dynamicore_wallet_credit_api.api.dependencies import CurrentUser, get_current_user, require_credit_officer
from dynamicore_wallet_credit_api.db.connection import get_connection
from dynamicore_wallet_credit_api.modules.credits.schemas import (
    CreditApproveRequest,
    CreditCreateRequest,
    CreditResponse,
    CreditScheduleItem,
)
from dynamicore_wallet_credit_api.modules.credits.service import (
    approve_credit,
    create_credit,
    get_credit,
    get_credit_schedule,
    list_credits,
)

router = APIRouter(prefix="/credits", tags=["credits"])


@router.post("", response_model=CreditResponse, status_code=201)
def create_credit_endpoint(
    payload: CreditCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> CreditResponse:
    with get_connection() as connection:
        return create_credit(connection, current_user.id, payload)


@router.get("", response_model=list[CreditResponse])
def list_credits_endpoint(current_user: CurrentUser = Depends(get_current_user)) -> list[CreditResponse]:
    with get_connection() as connection:
        return list_credits(connection, current_user.id)


@router.get("/{credit_id}", response_model=CreditResponse)
def get_credit_endpoint(
    credit_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
) -> CreditResponse:
    with get_connection() as connection:
        return get_credit(connection, current_user.id, credit_id)


@router.get("/{credit_id}/schedule", response_model=list[CreditScheduleItem])
def get_credit_schedule_endpoint(
    credit_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
) -> list[CreditScheduleItem]:
    with get_connection() as connection:
        return get_credit_schedule(connection, current_user.id, credit_id)


@router.post("/{credit_id}/approve", response_model=CreditResponse)
def approve_credit_endpoint(
    credit_id: UUID,
    payload: CreditApproveRequest,
    current_user: CurrentUser = Depends(require_credit_officer),
) -> CreditResponse:
    with get_connection() as connection:
        return approve_credit(connection, credit_id, current_user.id, payload)
