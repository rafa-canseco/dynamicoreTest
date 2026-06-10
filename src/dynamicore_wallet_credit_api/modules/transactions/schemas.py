from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class DepositRequest(BaseModel):
    wallet_id: UUID
    amount: Decimal = Field(gt=0, decimal_places=2)
    description: str | None = Field(default=None, max_length=255)


class WithdrawalRequest(BaseModel):
    wallet_id: UUID
    amount: Decimal = Field(gt=0, decimal_places=2)
    description: str | None = Field(default=None, max_length=255)


class TransferRequest(BaseModel):
    source_wallet_id: UUID
    destination_wallet_id: UUID
    amount: Decimal = Field(gt=0, decimal_places=2)
    description: str | None = Field(default=None, max_length=255)


class TransactionResponse(BaseModel):
    id: UUID
    transaction_type: str
    status: str
    amount: Decimal
    currency: str
    source_wallet_id: UUID | None
    destination_wallet_id: UUID | None
    external_reference: str
