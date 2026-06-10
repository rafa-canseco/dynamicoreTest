-- Dynamicore Wallet and Credit Platform
-- Schema section 1: identity, roles, and user credit profile.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TYPE user_status AS ENUM (
    'pending_verification',
    'active',
    'suspended',
    'closed'
);

CREATE TYPE role_name AS ENUM (
    'user',
    'admin',
    'credit_officer'
);

CREATE TYPE wallet_status AS ENUM (
    'active',
    'frozen',
    'closed'
);

CREATE TYPE wallet_transaction_type AS ENUM (
    'deposit',
    'withdrawal',
    'transfer'
);

CREATE TYPE wallet_transaction_status AS ENUM (
    'pending',
    'posted',
    'failed',
    'reversed'
);

CREATE TYPE ledger_entry_direction AS ENUM (
    'debit',
    'credit'
);

CREATE TYPE credit_status AS ENUM (
    'requested',
    'under_review',
    'approved',
    'rejected',
    'active',
    'paid',
    'defaulted',
    'cancelled'
);

CREATE TYPE credit_payment_status AS ENUM (
    'pending',
    'paid',
    'late',
    'waived'
);

CREATE TYPE credit_payment_method AS ENUM (
    'wallet',
    'external_transfer',
    'cash'
);

CREATE TYPE idempotency_status AS ENUM (
    'processing',
    'completed',
    'failed'
);

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    phone_number TEXT,
    date_of_birth DATE,
    tax_id TEXT,
    status user_status NOT NULL DEFAULT 'pending_verification',
    credit_score SMALLINT,
    monthly_income NUMERIC(18, 2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    verified_at TIMESTAMPTZ,
    CONSTRAINT users_email_not_blank CHECK (length(trim(email)) > 3),
    CONSTRAINT users_password_hash_not_blank CHECK (length(trim(password_hash)) > 20),
    CONSTRAINT users_first_name_not_blank CHECK (length(trim(first_name)) > 0),
    CONSTRAINT users_last_name_not_blank CHECK (length(trim(last_name)) > 0),
    CONSTRAINT users_credit_score_range CHECK (credit_score IS NULL OR credit_score BETWEEN 300 AND 850),
    CONSTRAINT users_monthly_income_positive CHECK (monthly_income IS NULL OR monthly_income >= 0),
    CONSTRAINT users_verified_at_requires_active CHECK (
        verified_at IS NULL OR status IN ('active', 'suspended', 'closed')
    )
);

CREATE UNIQUE INDEX users_email_unique_idx ON users (lower(email));
CREATE UNIQUE INDEX users_tax_id_unique_idx ON users (tax_id) WHERE tax_id IS NOT NULL;
CREATE INDEX users_status_idx ON users (status);
CREATE INDEX users_created_at_idx ON users (created_at);

CREATE TABLE roles (
    id SMALLSERIAL PRIMARY KEY,
    name role_name NOT NULL UNIQUE,
    description TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT roles_description_not_blank CHECK (length(trim(description)) > 0)
);

CREATE TABLE user_roles (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id SMALLINT NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
    granted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    granted_by UUID REFERENCES users(id) ON DELETE SET NULL,
    PRIMARY KEY (user_id, role_id)
);

CREATE INDEX user_roles_role_id_idx ON user_roles (role_id);
CREATE INDEX user_roles_granted_by_idx ON user_roles (granted_by) WHERE granted_by IS NOT NULL;

INSERT INTO roles (name, description)
VALUES
    ('user', 'Standard customer role for wallet and credit operations.'),
    ('admin', 'Operational administrator with elevated platform permissions.'),
    ('credit_officer', 'Credit operations role allowed to review and approve credit requests.')
ON CONFLICT (name) DO NOTHING;

-- Schema section 2: wallets and auditable ledger.

CREATE TABLE wallets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    currency CHAR(3) NOT NULL DEFAULT 'MXN',
    status wallet_status NOT NULL DEFAULT 'active',
    balance NUMERIC(18, 2) NOT NULL DEFAULT 0,
    available_balance NUMERIC(18, 2) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at TIMESTAMPTZ,
    CONSTRAINT wallets_currency_uppercase CHECK (currency = upper(currency)),
    CONSTRAINT wallets_currency_iso_code CHECK (currency ~ '^[A-Z]{3}$'),
    CONSTRAINT wallets_balance_non_negative CHECK (balance >= 0),
    CONSTRAINT wallets_available_balance_non_negative CHECK (available_balance >= 0),
    CONSTRAINT wallets_available_not_greater_than_balance CHECK (available_balance <= balance),
    CONSTRAINT wallets_closed_at_requires_closed CHECK (closed_at IS NULL OR status = 'closed')
);

CREATE UNIQUE INDEX wallets_one_active_currency_per_user_idx
    ON wallets (user_id, currency)
    WHERE status <> 'closed';
CREATE INDEX wallets_user_id_idx ON wallets (user_id);
CREATE INDEX wallets_status_idx ON wallets (status);
CREATE INDEX wallets_created_at_idx ON wallets (created_at);

CREATE TABLE wallet_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_type wallet_transaction_type NOT NULL,
    status wallet_transaction_status NOT NULL DEFAULT 'pending',
    amount NUMERIC(18, 2) NOT NULL,
    currency CHAR(3) NOT NULL DEFAULT 'MXN',
    source_wallet_id UUID REFERENCES wallets(id) ON DELETE RESTRICT,
    destination_wallet_id UUID REFERENCES wallets(id) ON DELETE RESTRICT,
    external_reference TEXT,
    description TEXT,
    failure_reason TEXT,
    requested_by UUID REFERENCES users(id) ON DELETE SET NULL,
    posted_at TIMESTAMPTZ,
    reversed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT wallet_transactions_amount_positive CHECK (amount > 0),
    CONSTRAINT wallet_transactions_currency_uppercase CHECK (currency = upper(currency)),
    CONSTRAINT wallet_transactions_currency_iso_code CHECK (currency ~ '^[A-Z]{3}$'),
    CONSTRAINT wallet_transactions_external_reference_not_blank CHECK (
        external_reference IS NULL OR length(trim(external_reference)) > 0
    ),
    CONSTRAINT wallet_transactions_wallets_different CHECK (
        source_wallet_id IS NULL OR destination_wallet_id IS NULL OR source_wallet_id <> destination_wallet_id
    ),
    CONSTRAINT wallet_transactions_deposit_shape CHECK (
        transaction_type <> 'deposit'
        OR (source_wallet_id IS NULL AND destination_wallet_id IS NOT NULL)
    ),
    CONSTRAINT wallet_transactions_withdrawal_shape CHECK (
        transaction_type <> 'withdrawal'
        OR (source_wallet_id IS NOT NULL AND destination_wallet_id IS NULL)
    ),
    CONSTRAINT wallet_transactions_transfer_shape CHECK (
        transaction_type <> 'transfer'
        OR (source_wallet_id IS NOT NULL AND destination_wallet_id IS NOT NULL)
    ),
    CONSTRAINT wallet_transactions_posted_at_requires_posted CHECK (
        posted_at IS NULL OR status IN ('posted', 'reversed')
    ),
    CONSTRAINT wallet_transactions_reversed_at_requires_reversed CHECK (
        reversed_at IS NULL OR status = 'reversed'
    )
);

CREATE INDEX wallet_transactions_type_created_at_idx
    ON wallet_transactions (transaction_type, created_at);
CREATE INDEX wallet_transactions_status_idx ON wallet_transactions (status);
CREATE INDEX wallet_transactions_source_wallet_idx
    ON wallet_transactions (source_wallet_id, created_at DESC)
    WHERE source_wallet_id IS NOT NULL;
CREATE INDEX wallet_transactions_destination_wallet_idx
    ON wallet_transactions (destination_wallet_id, created_at DESC)
    WHERE destination_wallet_id IS NOT NULL;
CREATE INDEX wallet_transactions_requested_by_idx
    ON wallet_transactions (requested_by, created_at DESC)
    WHERE requested_by IS NOT NULL;
CREATE UNIQUE INDEX wallet_transactions_external_reference_unique_idx
    ON wallet_transactions (external_reference)
    WHERE external_reference IS NOT NULL;

CREATE TABLE wallet_transaction_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID NOT NULL REFERENCES wallet_transactions(id) ON DELETE RESTRICT,
    wallet_id UUID NOT NULL REFERENCES wallets(id) ON DELETE RESTRICT,
    direction ledger_entry_direction NOT NULL,
    amount NUMERIC(18, 2) NOT NULL,
    balance_after NUMERIC(18, 2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT wallet_transaction_entries_one_per_wallet UNIQUE (transaction_id, wallet_id),
    CONSTRAINT wallet_transaction_entries_amount_positive CHECK (amount > 0),
    CONSTRAINT wallet_transaction_entries_balance_after_non_negative CHECK (balance_after >= 0)
);

CREATE INDEX wallet_transaction_entries_transaction_id_idx
    ON wallet_transaction_entries (transaction_id);
CREATE INDEX wallet_transaction_entries_wallet_created_at_idx
    ON wallet_transaction_entries (wallet_id, created_at DESC);
CREATE INDEX wallet_transaction_entries_direction_idx
    ON wallet_transaction_entries (direction);

-- Schema section 3: credit lifecycle, payment schedule, and repayments.

CREATE TABLE credits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    disbursement_wallet_id UUID REFERENCES wallets(id) ON DELETE RESTRICT,
    status credit_status NOT NULL DEFAULT 'requested',
    principal_amount NUMERIC(18, 2) NOT NULL,
    annual_interest_rate NUMERIC(7, 4) NOT NULL,
    term_months SMALLINT NOT NULL,
    purpose TEXT,
    monthly_payment NUMERIC(18, 2),
    approved_by UUID REFERENCES users(id) ON DELETE SET NULL,
    rejected_by UUID REFERENCES users(id) ON DELETE SET NULL,
    rejection_reason TEXT,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at TIMESTAMPTZ,
    approved_at TIMESTAMPTZ,
    disbursed_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT credits_principal_amount_positive CHECK (principal_amount > 0),
    CONSTRAINT credits_annual_interest_rate_non_negative CHECK (annual_interest_rate >= 0),
    CONSTRAINT credits_term_months_positive CHECK (term_months > 0),
    CONSTRAINT credits_monthly_payment_positive CHECK (monthly_payment IS NULL OR monthly_payment > 0),
    CONSTRAINT credits_purpose_not_blank CHECK (purpose IS NULL OR length(trim(purpose)) > 0),
    CONSTRAINT credits_rejection_reason_not_blank CHECK (
        rejection_reason IS NULL OR length(trim(rejection_reason)) > 0
    ),
    CONSTRAINT credits_approval_fields_match_status CHECK (
        status NOT IN ('approved', 'active', 'paid', 'defaulted')
        OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)
    ),
    CONSTRAINT credits_rejection_fields_match_status CHECK (
        status <> 'rejected'
        OR (rejected_by IS NOT NULL AND rejection_reason IS NOT NULL)
    ),
    CONSTRAINT credits_disbursement_requires_active_or_later CHECK (
        disbursed_at IS NULL OR status IN ('active', 'paid', 'defaulted')
    ),
    CONSTRAINT credits_closed_at_terminal_status CHECK (
        closed_at IS NULL OR status IN ('paid', 'defaulted', 'cancelled', 'rejected')
    )
);

CREATE INDEX credits_user_status_idx ON credits (user_id, status);
CREATE INDEX credits_status_idx ON credits (status);
CREATE INDEX credits_requested_at_idx ON credits (requested_at);
CREATE INDEX credits_approved_by_idx ON credits (approved_by) WHERE approved_by IS NOT NULL;
CREATE INDEX credits_disbursement_wallet_idx
    ON credits (disbursement_wallet_id)
    WHERE disbursement_wallet_id IS NOT NULL;

CREATE TABLE credit_payment_schedule (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    credit_id UUID NOT NULL REFERENCES credits(id) ON DELETE RESTRICT,
    installment_number SMALLINT NOT NULL,
    due_date DATE NOT NULL,
    principal_amount NUMERIC(18, 2) NOT NULL,
    interest_amount NUMERIC(18, 2) NOT NULL,
    total_amount NUMERIC(18, 2) NOT NULL,
    remaining_amount NUMERIC(18, 2) NOT NULL,
    status credit_payment_status NOT NULL DEFAULT 'pending',
    paid_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT credit_payment_schedule_installment_positive CHECK (installment_number > 0),
    CONSTRAINT credit_payment_schedule_principal_non_negative CHECK (principal_amount >= 0),
    CONSTRAINT credit_payment_schedule_interest_non_negative CHECK (interest_amount >= 0),
    CONSTRAINT credit_payment_schedule_total_positive CHECK (total_amount > 0),
    CONSTRAINT credit_payment_schedule_remaining_non_negative CHECK (remaining_amount >= 0),
    CONSTRAINT credit_payment_schedule_remaining_not_greater_than_total CHECK (remaining_amount <= total_amount),
    CONSTRAINT credit_payment_schedule_total_matches_components CHECK (
        total_amount = principal_amount + interest_amount
    ),
    CONSTRAINT credit_payment_schedule_paid_state_consistent CHECK (
        status <> 'paid' OR (paid_at IS NOT NULL AND remaining_amount = 0)
    ),
    CONSTRAINT credit_payment_schedule_unpaid_state_consistent CHECK (
        status = 'paid' OR paid_at IS NULL
    ),
    CONSTRAINT credit_payment_schedule_unique_installment UNIQUE (credit_id, installment_number)
);

CREATE INDEX credit_payment_schedule_credit_status_idx
    ON credit_payment_schedule (credit_id, status);
CREATE INDEX credit_payment_schedule_due_date_idx
    ON credit_payment_schedule (due_date)
    WHERE status IN ('pending', 'late');
CREATE INDEX credit_payment_schedule_late_idx
    ON credit_payment_schedule (credit_id, due_date)
    WHERE status = 'late';

CREATE TABLE credit_payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    credit_id UUID NOT NULL REFERENCES credits(id) ON DELETE RESTRICT,
    schedule_id UUID REFERENCES credit_payment_schedule(id) ON DELETE RESTRICT,
    wallet_transaction_id UUID REFERENCES wallet_transactions(id) ON DELETE RESTRICT,
    payment_method credit_payment_method NOT NULL,
    amount NUMERIC(18, 2) NOT NULL,
    external_reference TEXT,
    paid_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT credit_payments_amount_positive CHECK (amount > 0),
    CONSTRAINT credit_payments_external_reference_not_blank CHECK (
        external_reference IS NULL OR length(trim(external_reference)) > 0
    ),
    CONSTRAINT credit_payments_wallet_method_requires_transaction CHECK (
        payment_method <> 'wallet' OR wallet_transaction_id IS NOT NULL
    )
);

CREATE INDEX credit_payments_credit_paid_at_idx ON credit_payments (credit_id, paid_at DESC);
CREATE INDEX credit_payments_schedule_id_idx
    ON credit_payments (schedule_id)
    WHERE schedule_id IS NOT NULL;
CREATE UNIQUE INDEX credit_payments_wallet_transaction_unique_idx
    ON credit_payments (wallet_transaction_id)
    WHERE wallet_transaction_id IS NOT NULL;
CREATE UNIQUE INDEX credit_payments_external_reference_unique_idx
    ON credit_payments (external_reference)
    WHERE external_reference IS NOT NULL;

-- Schema section 4: API idempotency controls for financial operations.

CREATE TABLE idempotency_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    idempotency_key TEXT NOT NULL,
    request_method TEXT NOT NULL,
    request_path TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    status idempotency_status NOT NULL DEFAULT 'processing',
    response_status_code INTEGER,
    response_body JSONB,
    locked_until TIMESTAMPTZ NOT NULL DEFAULT now() + interval '5 minutes',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT idempotency_keys_key_not_blank CHECK (length(trim(idempotency_key)) > 0),
    CONSTRAINT idempotency_keys_method_not_blank CHECK (length(trim(request_method)) > 0),
    CONSTRAINT idempotency_keys_path_not_blank CHECK (length(trim(request_path)) > 0),
    CONSTRAINT idempotency_keys_request_hash_not_blank CHECK (length(trim(request_hash)) > 0),
    CONSTRAINT idempotency_keys_response_status_code_range CHECK (
        response_status_code IS NULL OR response_status_code BETWEEN 100 AND 599
    ),
    CONSTRAINT idempotency_keys_completed_has_response CHECK (
        status <> 'completed' OR response_status_code IS NOT NULL
    )
);

CREATE UNIQUE INDEX idempotency_keys_user_key_idx
    ON idempotency_keys (user_id, idempotency_key)
    WHERE user_id IS NOT NULL;
CREATE UNIQUE INDEX idempotency_keys_anonymous_key_idx
    ON idempotency_keys (idempotency_key)
    WHERE user_id IS NULL;
CREATE INDEX idempotency_keys_status_locked_until_idx
    ON idempotency_keys (status, locked_until);
CREATE INDEX idempotency_keys_created_at_idx ON idempotency_keys (created_at);
