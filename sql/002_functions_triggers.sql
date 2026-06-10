-- Dynamicore Wallet and Credit Platform
-- PostgreSQL functions and triggers for financial consistency.

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER users_set_updated_at
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER wallets_set_updated_at
BEFORE UPDATE ON wallets
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER wallet_transactions_set_updated_at
BEFORE UPDATE ON wallet_transactions
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER credits_set_updated_at
BEFORE UPDATE ON credits
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER credit_payment_schedule_set_updated_at
BEFORE UPDATE ON credit_payment_schedule
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER idempotency_keys_set_updated_at
BEFORE UPDATE ON idempotency_keys
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE FUNCTION verificar_fondos_suficientes()
RETURNS TRIGGER AS $$
DECLARE
    source_available_balance NUMERIC(18, 2);
    source_status wallet_status;
BEGIN
    IF NEW.transaction_type IN ('withdrawal', 'transfer')
        AND NEW.status IN ('pending', 'posted') THEN
        IF NEW.source_wallet_id IS NULL THEN
            RAISE EXCEPTION 'source wallet is required for % transactions', NEW.transaction_type
                USING ERRCODE = '23514';
        END IF;

        SELECT available_balance, status
        INTO source_available_balance, source_status
        FROM wallets
        WHERE id = NEW.source_wallet_id;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'source wallet % does not exist', NEW.source_wallet_id
                USING ERRCODE = '23503';
        END IF;

        IF source_status <> 'active' THEN
            RAISE EXCEPTION 'source wallet % is not active', NEW.source_wallet_id
                USING ERRCODE = '23514';
        END IF;

        IF source_available_balance < NEW.amount THEN
            RAISE EXCEPTION 'insufficient funds in wallet %', NEW.source_wallet_id
                USING ERRCODE = '23514';
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER wallet_transactions_verify_sufficient_funds
BEFORE INSERT OR UPDATE OF transaction_type, status, amount, source_wallet_id
ON wallet_transactions
FOR EACH ROW
EXECUTE FUNCTION verificar_fondos_suficientes();

CREATE OR REPLACE FUNCTION procesar_transaccion(
    wallet_origen UUID,
    wallet_destino UUID,
    monto NUMERIC,
    tipo VARCHAR,
    actor_id UUID DEFAULT NULL,
    referencia_externa TEXT DEFAULT NULL,
    descripcion TEXT DEFAULT NULL
)
RETURNS BOOLEAN AS $$
DECLARE
    transaction_id UUID;
    transaction_type_value wallet_transaction_type;
    source_wallet wallets%ROWTYPE;
    destination_wallet wallets%ROWTYPE;
    source_balance_after NUMERIC(18, 2);
    destination_balance_after NUMERIC(18, 2);
    transaction_currency CHAR(3);
BEGIN
    transaction_type_value = tipo::wallet_transaction_type;

    IF monto IS NULL OR monto <= 0 THEN
        RAISE EXCEPTION 'transaction amount must be greater than zero'
            USING ERRCODE = '23514';
    END IF;

    IF transaction_type_value = 'deposit'
        AND (wallet_origen IS NOT NULL OR wallet_destino IS NULL) THEN
        RAISE EXCEPTION 'deposit requires only destination wallet'
            USING ERRCODE = '23514';
    ELSIF transaction_type_value = 'withdrawal'
        AND (wallet_origen IS NULL OR wallet_destino IS NOT NULL) THEN
        RAISE EXCEPTION 'withdrawal requires only source wallet'
            USING ERRCODE = '23514';
    ELSIF transaction_type_value = 'transfer'
        AND (wallet_origen IS NULL OR wallet_destino IS NULL OR wallet_origen = wallet_destino) THEN
        RAISE EXCEPTION 'transfer requires different source and destination wallets'
            USING ERRCODE = '23514';
    END IF;

    PERFORM 1
    FROM wallets
    WHERE id = ANY (ARRAY[wallet_origen, wallet_destino]::UUID[])
    ORDER BY id
    FOR UPDATE;

    IF wallet_origen IS NOT NULL THEN
        SELECT *
        INTO source_wallet
        FROM wallets
        WHERE id = wallet_origen;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'source wallet % does not exist', wallet_origen
                USING ERRCODE = '23503';
        END IF;

        IF source_wallet.status <> 'active' THEN
            RAISE EXCEPTION 'source wallet % is not active', wallet_origen
                USING ERRCODE = '23514';
        END IF;

        IF source_wallet.available_balance < monto THEN
            RAISE EXCEPTION 'insufficient funds in wallet %', wallet_origen
                USING ERRCODE = '23514';
        END IF;
    END IF;

    IF wallet_destino IS NOT NULL THEN
        SELECT *
        INTO destination_wallet
        FROM wallets
        WHERE id = wallet_destino;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'destination wallet % does not exist', wallet_destino
                USING ERRCODE = '23503';
        END IF;

        IF destination_wallet.status <> 'active' THEN
            RAISE EXCEPTION 'destination wallet % is not active', wallet_destino
                USING ERRCODE = '23514';
        END IF;
    END IF;

    IF transaction_type_value = 'transfer'
        AND source_wallet.currency <> destination_wallet.currency THEN
        RAISE EXCEPTION 'wallet currencies must match for transfers'
            USING ERRCODE = '23514';
    END IF;

    transaction_currency = COALESCE(source_wallet.currency, destination_wallet.currency);

    INSERT INTO wallet_transactions (
        transaction_type,
        status,
        amount,
        currency,
        source_wallet_id,
        destination_wallet_id,
        external_reference,
        description,
        requested_by,
        posted_at
    )
    VALUES (
        transaction_type_value,
        'posted',
        monto,
        transaction_currency,
        wallet_origen,
        wallet_destino,
        referencia_externa,
        descripcion,
        actor_id,
        now()
    )
    RETURNING id INTO transaction_id;

    IF wallet_origen IS NOT NULL THEN
        UPDATE wallets
        SET
            balance = balance - monto,
            available_balance = available_balance - monto
        WHERE id = wallet_origen
        RETURNING balance INTO source_balance_after;

        INSERT INTO wallet_transaction_entries (
            transaction_id,
            wallet_id,
            direction,
            amount,
            balance_after
        )
        VALUES (
            transaction_id,
            wallet_origen,
            'debit',
            monto,
            source_balance_after
        );
    END IF;

    IF wallet_destino IS NOT NULL THEN
        UPDATE wallets
        SET
            balance = balance + monto,
            available_balance = available_balance + monto
        WHERE id = wallet_destino
        RETURNING balance INTO destination_balance_after;

        INSERT INTO wallet_transaction_entries (
            transaction_id,
            wallet_id,
            direction,
            amount,
            balance_after
        )
        VALUES (
            transaction_id,
            wallet_destino,
            'credit',
            monto,
            destination_balance_after
        );
    END IF;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION generar_plan_pagos(credito_id UUID)
RETURNS VOID AS $$
DECLARE
    credit_record credits%ROWTYPE;
    monthly_rate NUMERIC;
    calculated_payment NUMERIC(18, 2);
    remaining_principal NUMERIC(18, 2);
    installment_principal NUMERIC(18, 2);
    installment_interest NUMERIC(18, 2);
    installment_total NUMERIC(18, 2);
    installment_number INTEGER;
BEGIN
    SELECT *
    INTO credit_record
    FROM credits
    WHERE id = credito_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'credit % does not exist', credito_id
            USING ERRCODE = '23503';
    END IF;

    IF credit_record.status NOT IN ('approved', 'active') THEN
        RAISE EXCEPTION 'payment schedule can only be generated for approved or active credits'
            USING ERRCODE = '23514';
    END IF;

    IF EXISTS (SELECT 1 FROM credit_payment_schedule WHERE credit_id = credito_id) THEN
        RAISE EXCEPTION 'payment schedule already exists for credit %', credito_id
            USING ERRCODE = '23505';
    END IF;

    monthly_rate = credit_record.annual_interest_rate / 100 / 12;

    IF monthly_rate = 0 THEN
        calculated_payment = round(credit_record.principal_amount / credit_record.term_months, 2);
    ELSE
        calculated_payment = round(
            (
                credit_record.principal_amount
                * monthly_rate
                * power(1 + monthly_rate, credit_record.term_months)
            )
            / (power(1 + monthly_rate, credit_record.term_months) - 1),
            2
        );
    END IF;

    remaining_principal = credit_record.principal_amount;

    FOR installment_number IN 1..credit_record.term_months LOOP
        installment_interest = round(remaining_principal * monthly_rate, 2);

        IF installment_number = credit_record.term_months THEN
            installment_principal = remaining_principal;
        ELSE
            installment_principal = calculated_payment - installment_interest;
        END IF;

        IF installment_principal < 0 THEN
            RAISE EXCEPTION 'calculated installment principal cannot be negative'
                USING ERRCODE = '22003';
        END IF;

        installment_total = installment_principal + installment_interest;
        remaining_principal = remaining_principal - installment_principal;

        INSERT INTO credit_payment_schedule (
            credit_id,
            installment_number,
            due_date,
            principal_amount,
            interest_amount,
            total_amount,
            remaining_amount
        )
        VALUES (
            credito_id,
            installment_number,
            (date_trunc('month', now())::DATE + (installment_number || ' months')::INTERVAL)::DATE,
            installment_principal,
            installment_interest,
            installment_total,
            installment_total
        );
    END LOOP;

    UPDATE credits
    SET monthly_payment = calculated_payment
    WHERE id = credito_id;
END;
$$ LANGUAGE plpgsql;
