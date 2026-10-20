SET XACT_ABORT ON;

IF OBJECT_ID(N'claims.ClaimHistory', N'U') IS NULL
    CREATE TABLE claims.ClaimHistory (
        history_claim_id nvarchar(100) NOT NULL PRIMARY KEY,
        customer_id nvarchar(100) NOT NULL,
        claimed_at datetime2(0) NOT NULL,
        claimed_amount decimal(12,2) NOT NULL CHECK (claimed_amount >= 0),
        currency char(3) NOT NULL DEFAULT 'USD' CHECK (currency = 'USD'),
        synthetic bit NOT NULL DEFAULT 1 CHECK (synthetic = 1)
    );

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID(N'claims.ClaimHistory') AND name = N'IX_ClaimHistory_Customer'
)
    CREATE INDEX IX_ClaimHistory_Customer
    ON claims.ClaimHistory(customer_id, claimed_at DESC, history_claim_id)
    INCLUDE (claimed_amount, currency);

INSERT claims.ClaimHistory(history_claim_id, customer_id, claimed_at, claimed_amount)
SELECT seed.history_claim_id, seed.customer_id, seed.claimed_at, seed.claimed_amount
FROM (VALUES
    (N'hist-one-001', N'cust-demo-one', '2023-08-01T10:00:00', 500.00),
    (N'hist-one-002', N'cust-demo-one', '2024-11-04T10:00:00', 800.00),
    (N'hist-one-003', N'cust-demo-one', '2025-02-18T11:00:00', 1250.00),
    (N'hist-one-004', N'cust-demo-one', '2025-06-05T12:00:00', 1650.00),
    (N'hist-one-005', N'cust-demo-one', '2025-10-03T13:00:00', 950.00),
    (N'hist-one-006', N'cust-demo-one', '2026-01-22T14:00:00', 1850.00),
    (N'hist-one-007', N'cust-demo-one', '2026-05-14T15:00:00', 1200.00),
    (N'hist-one-008', N'cust-demo-one', '2026-08-02T16:00:00', 32000.00),
    (N'hist-one-009', N'cust-demo-one', '2026-10-01T17:00:00', 750.00),
    (N'hist-four-001', N'cust-demo-four', '2024-12-08T10:00:00', 600.00),
    (N'hist-four-002', N'cust-demo-four', '2025-04-11T11:00:00', 1100.00),
    (N'hist-four-003', N'cust-demo-four', '2025-11-17T12:00:00', 1450.00),
    (N'hist-four-004', N'cust-demo-four', '2026-06-09T13:00:00', 900.00)
) seed(history_claim_id, customer_id, claimed_at, claimed_amount)
WHERE NOT EXISTS (
    SELECT 1 FROM claims.ClaimHistory existing
    WHERE existing.history_claim_id = seed.history_claim_id
);
GO

CREATE OR ALTER PROCEDURE claims.GetClaimRiskFacts
    @claim_id nvarchar(max),
    @as_of nvarchar(max)
AS
BEGIN
    SET NOCOUNT ON;
    IF @claim_id IS NULL OR DATALENGTH(@claim_id) NOT BETWEEN 2 AND 200
       OR @claim_id COLLATE Latin1_General_100_BIN2 LIKE N'%[^a-z0-9-]%'
       OR @claim_id NOT LIKE N'clm-%'
        THROW 50010, 'A lowercase synthetic claim ID of at most 100 characters is required.', 1;
    DECLARE @review_at datetime2(0) = TRY_CONVERT(datetime2(0), LEFT(@as_of, 19), 126);
    IF @as_of IS NULL OR DATALENGTH(@as_of) <> 40
       OR RIGHT(@as_of, 1) COLLATE Latin1_General_100_BIN2 <> N'Z'
       OR @review_at IS NULL OR @review_at < '1902-01-01'
       OR CONVERT(varchar(19), @review_at, 126) COLLATE Latin1_General_100_BIN2
          <> LEFT(@as_of, 19) COLLATE Latin1_General_100_BIN2
        THROW 50011, 'as_of must be UTC YYYY-MM-DDTHH:MM:SSZ on or after 1902-01-01.', 1;

    DECLARE @customer_id nvarchar(100);
    SELECT @customer_id = customer_id FROM claims.Claim WHERE claim_id = @claim_id;
    IF NOT EXISTS (SELECT 1 FROM claims.Claim WHERE claim_id = @claim_id)
        THROW 50012, 'Synthetic claim not found.', 1;
    IF @customer_id IS NULL OR LEN(LTRIM(RTRIM(@customer_id))) = 0
        THROW 50013, 'The claim has no customer ID; history is unavailable, not zero.', 1;

    ;WITH prior AS (
        SELECT history_claim_id, claimed_at, claimed_amount, currency
        FROM claims.ClaimHistory
        WHERE customer_id = @customer_id
          AND history_claim_id <> @claim_id
          AND claimed_at <= @review_at
    ), windowed AS (
        SELECT history_claim_id, claimed_at, claimed_amount, currency
        FROM prior
        WHERE claimed_at > DATEADD(month, -24, @review_at)
    )
    SELECT
        @claim_id AS claim_id,
        @customer_id AS customer_id,
        CONVERT(varchar(19), @review_at, 126) + 'Z' AS as_of_utc,
        CONVERT(varchar(19), DATEADD(month, -24, @review_at), 126) + 'Z' AS window_start_utc,
        COUNT_BIG(*) AS claim_count_24_months,
        COALESCE(SUM(CASE WHEN claimed_at > DATEADD(month, -12, @review_at)
                          THEN CAST(1 AS bigint) ELSE CAST(0 AS bigint) END), 0)
            AS claim_count_12_months,
        COALESCE(SUM(claimed_amount), 0) AS total_claimed_amount_24_months,
        AVG(claimed_amount) AS average_claimed_amount_24_months,
        MAX(claimed_amount) AS largest_claimed_amount_24_months,
        'USD' AS currency,
        (SELECT CONVERT(varchar(19), MAX(claimed_at), 126) + 'Z' FROM prior)
            AS last_prior_claim_at_utc,
        (SELECT TOP (20) history_claim_id, CONVERT(varchar(19), claimed_at, 126) + 'Z'
                AS claimed_at_utc, claimed_amount, currency
         FROM windowed ORDER BY claimed_at DESC, history_claim_id FOR JSON PATH)
            AS recent_claim_amounts_json,
        CAST(CASE WHEN COUNT_BIG(*) > 20 THEN 1 ELSE 0 END AS bit) AS history_truncated,
        CAST(1 AS bit) AS synthetic,
        CAST(1 AS bit) AS human_review_required
    FROM windowed;
END;
