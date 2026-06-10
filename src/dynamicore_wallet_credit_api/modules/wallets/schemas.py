from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class WalletCreateRequest(BaseModel):
    currency: str = Field(default="MXN", min_length=3, max_length=3, pattern="^[A-Z]{3}$")


class WalletResponse(BaseModel):
    id: UUID
    user_id: UUID
    currency: str
    status: str
    balance: Decimal
    available_balance: Decimal


class WalletTransactionHistoryItem(BaseModel):
    transaction_id: UUID
    transaction_type: str
    transaction_status: str
    direction: str
    amount: Decimal
    balance_after: Decimal
    counterparty_wallet_id: UUID | None
    description: str | None
    created_at: str
