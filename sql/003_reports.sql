-- Dynamicore Wallet and Credit Platform
-- Advanced PostgreSQL reporting queries for the technical assessment.

-- 1. Balance report by user showing all wallets.
SELECT
    u.id AS user_id,
    u.email,
    u.first_name,
    u.last_name,
    w.id AS wallet_id,
    w.currency,
    w.status AS wallet_status,
    w.balance,
    w.available_balance,
    count(wte.id) AS ledger_entry_count,
    max(wte.created_at) AS last_wallet_activity_at
FROM users u
JOIN wallets w ON w.user_id = u.id
LEFT JOIN wallet_transaction_entries wte ON wte.wallet_id = w.id
GROUP BY
    u.id,
    u.email,
    u.first_name,
    u.last_name,
    w.id,
    w.currency,
    w.status,
    w.balance,
    w.available_balance
ORDER BY u.email, w.currency;

-- 2. Monthly transaction analysis by type with volume and month-over-month growth.
WITH monthly_transactions AS (
    SELECT
        date_trunc('month', posted_at)::DATE AS month,
        transaction_type,
        count(*) AS transaction_count,
        sum(amount) AS total_volume
    FROM wallet_transactions
    WHERE status = 'posted'
      AND posted_at IS NOT NULL
    GROUP BY date_trunc('month', posted_at)::DATE, transaction_type
),
monthly_with_previous AS (
    SELECT
        month,
        transaction_type,
        transaction_count,
        total_volume,
        lag(total_volume) OVER (
            PARTITION BY transaction_type
            ORDER BY month
        ) AS previous_month_volume
    FROM monthly_transactions
)
SELECT
    month,
    transaction_type,
    transaction_count,
    total_volume,
    previous_month_volume,
    CASE
        WHEN previous_month_volume IS NULL THEN NULL
        WHEN previous_month_volume = 0 THEN NULL
        ELSE round(((total_volume - previous_month_volume) / previous_month_volume) * 100, 2)
    END AS volume_growth_percentage
FROM monthly_with_previous
ORDER BY month DESC, transaction_type;

-- 3. Credit status dashboard with amounts by status and delinquency percentage.
WITH credit_amounts AS (
    SELECT
        status,
        count(*) AS credit_count,
        sum(principal_amount) AS total_principal,
        sum(coalesce(monthly_payment, 0)) AS total_monthly_payment
    FROM credits
    GROUP BY status
),
delinquency AS (
    SELECT
        c.status,
        count(DISTINCT c.id) FILTER (
            WHERE cps.status = 'late'
               OR (cps.status = 'pending' AND cps.due_date < CURRENT_DATE)
        ) AS delinquent_credits,
        count(DISTINCT c.id) AS credits_with_schedule
    FROM credits c
    LEFT JOIN credit_payment_schedule cps ON cps.credit_id = c.id
    GROUP BY c.status
)
SELECT
    ca.status,
    ca.credit_count,
    ca.total_principal,
    ca.total_monthly_payment,
    coalesce(d.delinquent_credits, 0) AS delinquent_credits,
    CASE
        WHEN coalesce(d.credits_with_schedule, 0) = 0 THEN 0
        ELSE round((d.delinquent_credits::NUMERIC / d.credits_with_schedule) * 100, 2)
    END AS delinquency_percentage
FROM credit_amounts ca
LEFT JOIN delinquency d ON d.status = ca.status
ORDER BY ca.status;

-- 4. Users with the best credit behavior: approved credits and on-time payments.
WITH credit_behavior AS (
    SELECT
        u.id AS user_id,
        u.email,
        u.first_name,
        u.last_name,
        u.credit_score,
        count(DISTINCT c.id) FILTER (
            WHERE c.status IN ('approved', 'active', 'paid')
        ) AS approved_credit_count,
        count(cps.id) FILTER (WHERE cps.status = 'paid') AS paid_installments,
        count(cps.id) FILTER (
            WHERE cps.status = 'paid'
              AND cps.paid_at::DATE <= cps.due_date
        ) AS on_time_installments,
        count(cps.id) FILTER (
            WHERE cps.status = 'late'
               OR (cps.status = 'pending' AND cps.due_date < CURRENT_DATE)
        ) AS late_or_overdue_installments,
        sum(cp.amount) AS total_paid_amount
    FROM users u
    LEFT JOIN credits c ON c.user_id = u.id
    LEFT JOIN credit_payment_schedule cps ON cps.credit_id = c.id
    LEFT JOIN credit_payments cp ON cp.credit_id = c.id
    GROUP BY
        u.id,
        u.email,
        u.first_name,
        u.last_name,
        u.credit_score
)
SELECT
    user_id,
    email,
    first_name,
    last_name,
    credit_score,
    approved_credit_count,
    paid_installments,
    on_time_installments,
    late_or_overdue_installments,
    coalesce(total_paid_amount, 0) AS total_paid_amount,
    CASE
        WHEN paid_installments = 0 THEN 0
        ELSE round((on_time_installments::NUMERIC / paid_installments) * 100, 2)
    END AS on_time_payment_percentage
FROM credit_behavior
WHERE approved_credit_count > 0
ORDER BY
    on_time_payment_percentage DESC,
    late_or_overdue_installments ASC,
    approved_credit_count DESC,
    credit_score DESC NULLS LAST;
