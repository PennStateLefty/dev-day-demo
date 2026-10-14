SET XACT_ABORT ON;

IF SCHEMA_ID(N'claims') IS NULL
    EXEC(N'CREATE SCHEMA claims AUTHORIZATION dbo');

IF OBJECT_ID(N'claims.Policy', N'U') IS NULL
    CREATE TABLE claims.Policy (
        policy_id nvarchar(100) NOT NULL PRIMARY KEY,
        payload nvarchar(max) NOT NULL CHECK (ISJSON(payload) = 1)
    );

IF OBJECT_ID(N'claims.Claim', N'U') IS NULL
    CREATE TABLE claims.Claim (
        claim_id nvarchar(100) NOT NULL PRIMARY KEY,
        policy_id nvarchar(100) NULL REFERENCES claims.Policy(policy_id),
        customer_id nvarchar(100) NULL,
        loss_date date NULL,
        payload nvarchar(max) NOT NULL CHECK (ISJSON(payload) = 1)
    );

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID(N'claims.Claim') AND name = N'IX_Claim_Customer'
)
    CREATE INDEX IX_Claim_Customer ON claims.Claim(customer_id, loss_date);

IF OBJECT_ID(N'claims.Artifact', N'U') IS NULL
    CREATE TABLE claims.Artifact (
        artifact_id nvarchar(100) NOT NULL PRIMARY KEY,
        claim_id nvarchar(100) NOT NULL REFERENCES claims.Claim(claim_id),
        payload nvarchar(max) NOT NULL CHECK (ISJSON(payload) = 1)
    );

IF OBJECT_ID(N'claims.ReviewNote', N'U') IS NULL
    CREATE TABLE claims.ReviewNote (
        note_id uniqueidentifier NOT NULL DEFAULT NEWID() PRIMARY KEY,
        claim_id nvarchar(100) NOT NULL REFERENCES claims.Claim(claim_id),
        note nvarchar(2000) NOT NULL CHECK (LEN(LTRIM(RTRIM(note))) > 0),
        created_at datetime2 NOT NULL DEFAULT SYSUTCDATETIME(),
        human_review_required bit NOT NULL DEFAULT 1 CHECK (human_review_required = 1)
    );
