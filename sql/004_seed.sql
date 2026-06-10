-- Dynamicore Wallet and Credit Platform
-- Demo data for local validation, API testing, and report previews.

DO $$
DECLARE
    user_rafa UUID;
    user_ana UUID;
    user_luis UUID;
    credit_officer UUID;
    rafa_wallet UUID;
    ana_wallet UUID;
    luis_wallet UUID;
    rafa_credit UUID;
    ana_credit UUID;
BEGIN
    IF EXISTS (SELECT 1 FROM users WHERE email = 'rafa@example.com') THEN
        RAISE NOTICE 'Seed data already exists, skipping.';
        RETURN;
    END IF;

    INSERT INTO users (
        email,
        password_hash,
        first_name,
        last_name,
        phone_number,
        date_of_birth,
        tax_id,
        status,
        credit_score,
        monthly_income,
        verified_at
    )
    VALUES
        (
            'rafa@example.com',
            'demo-hashed-password-value-rafa',
            'Rafael',
            'Canseco',
            '+525555000001',
            '1992-04-10',
            'RFCDEMO001',
            'active',
            780,
            65000.00,
            now()
        ),
        (
            'ana@example.com',
            'demo-hashed-password-value-ana',
            'Ana',
            'Lopez',
            '+525555000002',
            '1989-08-21',
            'RFCDEMO002',
            'active',
            720,
            52000.00,
            now()
        ),
        (
            'luis@example.com',
            'demo-hashed-password-value-luis',
            'Luis',
            'Martinez',
            '+525555000003',
            '1995-01-15',
            'RFCDEMO003',
            'active',
            640,
            31000.00,
            now()
        ),
        (
            'credit.officer@example.com',
            'demo-hashed-password-value-officer',
            'Credit',
            'Officer',
            '+525555000004',
            '1985-11-05',
            'RFCDEMO004',
            'active',
            810,
            85000.00,
            now()
        );

    SELECT id INTO user_rafa FROM users WHERE email = 'rafa@example.com';
    SELECT id INTO user_ana FROM users WHERE email = 'ana@example.com';
    SELECT id INTO user_luis FROM users WHERE email = 'luis@example.com';
    SELECT id INTO credit_officer FROM users WHERE email = 'credit.officer@example.com';

    INSERT INTO user_roles (user_id, role_id)
    SELECT user_rafa, id FROM roles WHERE name = 'user';

    INSERT INTO user_roles (user_id, role_id)
    SELECT user_ana, id FROM roles WHERE name = 'user';

    INSERT INTO user_roles (user_id, role_id)
    SELECT user_luis, id FROM roles WHERE name = 'user';

    INSERT INTO user_roles (user_id, role_id)
    SELECT credit_officer, id FROM roles WHERE name = 'credit_officer';

    INSERT INTO wallets (user_id, currency)
    VALUES (user_rafa, 'MXN')
    RETURNING id INTO rafa_wallet;

    INSERT INTO wallets (user_id, currency)
    VALUES (user_ana, 'MXN')
    RETURNING id INTO ana_wallet;

    INSERT INTO wallets (user_id, currency)
    VALUES (user_luis, 'MXN')
    RETURNING id INTO luis_wallet;

    PERFORM procesar_transaccion(NULL, rafa_wallet, 5000.00, 'deposit', user_rafa, 'seed-deposit-rafa', 'Initial wallet funding');
    PERFORM procesar_transaccion(NULL, ana_wallet, 3500.00, 'deposit', user_ana, 'seed-deposit-ana', 'Initial wallet funding');
    PERFORM procesar_transaccion(NULL, luis_wallet, 1200.00, 'deposit', user_luis, 'seed-deposit-luis', 'Initial wallet funding');
    PERFORM procesar_transaccion(rafa_wallet, ana_wallet, 750.00, 'transfer', user_rafa, 'seed-transfer-rafa-ana', 'Demo transfer');
    PERFORM procesar_transaccion(ana_wallet, NULL, 300.00, 'withdrawal', user_ana, 'seed-withdrawal-ana', 'Demo withdrawal');

    UPDATE wallet_transactions
    SET posted_at = now() - interval '2 months',
        created_at = now() - interval '2 months'
    WHERE external_reference = 'seed-deposit-rafa';

    UPDATE wallet_transactions
    SET posted_at = now() - interval '1 month',
        created_at = now() - interval '1 month'
    WHERE external_reference IN ('seed-deposit-ana', 'seed-transfer-rafa-ana');

    INSERT INTO credits (
        user_id,
        disbursement_wallet_id,
        status,
        principal_amount,
        annual_interest_rate,
        term_months,
        purpose,
        approved_by,
        approved_at,
        disbursed_at
    )
    VALUES (
        user_rafa,
        rafa_wallet,
        'active',
        12000.00,
        18.0000,
        12,
        'Working capital',
        credit_officer,
        now() - interval '40 days',
        now() - interval '39 days'
    )
    RETURNING id INTO rafa_credit;

    PERFORM generar_plan_pagos(rafa_credit);

    UPDATE credit_payment_schedule
    SET status = 'paid',
        remaining_amount = 0,
        paid_at = due_date::TIMESTAMPTZ - interval '1 day'
    WHERE credit_id = rafa_credit
      AND installment_number IN (1, 2);

    INSERT INTO credit_payments (credit_id, schedule_id, payment_method, amount, external_reference, paid_at)
    SELECT
        rafa_credit,
        id,
        'external_transfer',
        total_amount,
        'seed-credit-payment-rafa-' || installment_number,
        paid_at
    FROM credit_payment_schedule
    WHERE credit_id = rafa_credit
      AND installment_number IN (1, 2);

    INSERT INTO credits (
        user_id,
        disbursement_wallet_id,
        status,
        principal_amount,
        annual_interest_rate,
        term_months,
        purpose,
        approved_by,
        approved_at,
        disbursed_at
    )
    VALUES (
        user_ana,
        ana_wallet,
        'active',
        8000.00,
        22.0000,
        8,
        'Personal expenses',
        credit_officer,
        now() - interval '70 days',
        now() - interval '69 days'
    )
    RETURNING id INTO ana_credit;

    PERFORM generar_plan_pagos(ana_credit);

    UPDATE credit_payment_schedule
    SET status = 'late',
        due_date = CURRENT_DATE - interval '10 days'
    WHERE credit_id = ana_credit
      AND installment_number = 1;
END $$;
