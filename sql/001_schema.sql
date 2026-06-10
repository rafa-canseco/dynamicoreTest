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
