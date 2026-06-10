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
