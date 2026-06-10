from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class CreditCreateRequest(BaseModel):
    disbursement_wallet_id: UUID
    principal_amount: Decimal = Field(gt=0, decimal_places=2)
    annual_interest_rate: Decimal = Field(ge=0, decimal_places=4)
    term_months: int = Field(gt=0, le=120)
    purpose: str | None = Field(default=None, max_length=255)


class CreditApproveRequest(BaseModel):
    annual_interest_rate: Decimal | None = Field(default=None, ge=0, decimal_places=4)
    term_months: int | None = Field(default=None, gt=0, le=120)


class CreditRejectRequest(BaseModel):
    rejection_reason: str = Field(min_length=1, max_length=255)


class CreditPaymentRequest(BaseModel):
    schedule_id: UUID
    amount: Decimal = Field(gt=0, decimal_places=2)
    payment_method: str = Field(pattern="^(wallet|external_transfer|cash)$")
    wallet_id: UUID | None = None
    external_reference: str | None = Field(default=None, max_length=160)


class CreditResponse(BaseModel):
    id: UUID
    user_id: UUID
    disbursement_wallet_id: UUID | None
    status: str
    principal_amount: Decimal
    annual_interest_rate: Decimal
    term_months: int
    purpose: str | None
    monthly_payment: Decimal | None


class CreditScheduleItem(BaseModel):
    id: UUID
    installment_number: int
    due_date: str
    principal_amount: Decimal
    interest_amount: Decimal
    total_amount: Decimal
    remaining_amount: Decimal
    status: str


class CreditPaymentResponse(BaseModel):
    id: UUID
    credit_id: UUID
    schedule_id: UUID | None
    wallet_transaction_id: UUID | None
    payment_method: str
    amount: Decimal
    external_reference: str | None
    paid_at: str
