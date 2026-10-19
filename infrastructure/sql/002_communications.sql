SET XACT_ABORT ON;

IF OBJECT_ID(N'claims.Communication', N'U') IS NULL
    CREATE TABLE claims.Communication (
        communication_id nvarchar(100) NOT NULL PRIMARY KEY,
        claim_id nvarchar(100) NOT NULL REFERENCES claims.Claim(claim_id),
        assessment_id nvarchar(100) NOT NULL,
        citation_ids nvarchar(max) NOT NULL CHECK (ISJSON(citation_ids) = 1),
        artifact_ids nvarchar(max) NOT NULL CHECK (ISJSON(artifact_ids) = 1),
        body nvarchar(max) NOT NULL CHECK (LEN(LTRIM(RTRIM(body))) > 0),
        created_at datetime2(7) NOT NULL,
        reviewed_by nvarchar(200) NULL,
        reviewed_at datetime2(7) NULL,
        sent_at datetime2(7) NULL,
        payload nvarchar(max) NOT NULL CHECK (ISJSON(payload) = 1),
        human_review_required bit NOT NULL CHECK (human_review_required = 1),
        CHECK ((reviewed_by IS NULL AND reviewed_at IS NULL)
            OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)),
        CHECK (sent_at IS NULL OR reviewed_at IS NOT NULL)
    );

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID(N'claims.Communication')
      AND name = N'IX_Communication_Claim_Created'
)
    CREATE INDEX IX_Communication_Claim_Created
        ON claims.Communication(claim_id, created_at DESC);

GO

CREATE OR ALTER PROCEDURE claims.CreateCommunication
    @payload nvarchar(max)
AS
BEGIN
    SET NOCOUNT ON;
    IF ISJSON(@payload) <> 1
        THROW 50020, 'Communication payload must be valid JSON.', 1;

    DECLARE @communication_id nvarchar(100) = JSON_VALUE(@payload, '$.communicationId');
    DECLARE @claim_id nvarchar(100) = JSON_VALUE(@payload, '$.claimId');
    DECLARE @assessment_id nvarchar(100) = JSON_VALUE(@payload, '$.assessmentId');
    DECLARE @citation_ids nvarchar(max) = JSON_QUERY(@payload, '$.citationIds');
    DECLARE @artifact_ids nvarchar(max) = JSON_QUERY(@payload, '$.artifactIds');
    DECLARE @body nvarchar(max);
    SELECT @body = body FROM OPENJSON(@payload) WITH (body nvarchar(max) '$.body');
    DECLARE @created_at datetime2(7) = SYSUTCDATETIME();
    DECLARE @created_at_json nvarchar(40) = CONVERT(varchar(33), @created_at, 126) + 'Z';

    IF @communication_id IS NULL OR @claim_id IS NULL OR @assessment_id IS NULL
       OR @body IS NULL OR LEN(LTRIM(RTRIM(@body))) = 0
       OR @citation_ids IS NULL OR @artifact_ids IS NULL
       OR LEFT(LTRIM(@citation_ids), 1) <> '['
       OR LEFT(LTRIM(@artifact_ids), 1) <> '['
       OR COALESCE(JSON_VALUE(@payload, '$.humanReviewRequired'), 'false') <> 'true'
        THROW 50021, 'Communication record is incomplete.', 1;

    SET @payload = JSON_MODIFY(@payload, '$.createdAt', @created_at_json);

    INSERT claims.Communication (
        communication_id, claim_id, assessment_id, citation_ids, artifact_ids,
        body, created_at, payload, human_review_required
    )
    VALUES (
        @communication_id, @claim_id, @assessment_id, @citation_ids, @artifact_ids,
        @body, @created_at, @payload, 1
    );

    SELECT payload FROM claims.Communication WHERE communication_id = @communication_id;
END;

GO

CREATE OR ALTER PROCEDURE claims.MarkCommunicationReviewed
    @communication_id nvarchar(100),
    @reviewer nvarchar(200)
AS
BEGIN
    SET NOCOUNT ON;
    IF LEN(LTRIM(RTRIM(@reviewer))) = 0
        THROW 50022, 'Reviewer identity is required.', 1;

    DECLARE @reviewed_at datetime2(7) = SYSUTCDATETIME();
    DECLARE @reviewed_at_json nvarchar(40) =
        CONVERT(varchar(33), @reviewed_at, 126) + 'Z';
    DECLARE @updated TABLE(payload nvarchar(max));

    UPDATE claims.Communication
    SET reviewed_by = @reviewer,
        reviewed_at = @reviewed_at,
        payload = JSON_MODIFY(
            JSON_MODIFY(payload, '$.reviewedBy', @reviewer),
            '$.reviewedAt',
            @reviewed_at_json
        )
    OUTPUT inserted.payload INTO @updated
    WHERE communication_id = @communication_id AND reviewed_at IS NULL;

    IF EXISTS (SELECT 1 FROM @updated)
        SELECT N'updated' AS status, payload FROM @updated;
    ELSE IF NOT EXISTS (
        SELECT 1 FROM claims.Communication WHERE communication_id = @communication_id
    )
        SELECT N'missing' AS status, CAST(NULL AS nvarchar(max)) AS payload;
    ELSE
        SELECT N'conflict' AS status, payload
        FROM claims.Communication WHERE communication_id = @communication_id;
END;

GO

CREATE OR ALTER PROCEDURE claims.MarkCommunicationSent
    @communication_id nvarchar(100)
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @sent_at datetime2(7) = SYSUTCDATETIME();
    DECLARE @sent_at_json nvarchar(40) = CONVERT(varchar(33), @sent_at, 126) + 'Z';
    DECLARE @updated TABLE(payload nvarchar(max));

    UPDATE claims.Communication
    SET sent_at = @sent_at,
        payload = JSON_MODIFY(payload, '$.sentAt', @sent_at_json)
    OUTPUT inserted.payload INTO @updated
    WHERE communication_id = @communication_id
      AND reviewed_at IS NOT NULL
      AND sent_at IS NULL;

    IF EXISTS (SELECT 1 FROM @updated)
        SELECT N'updated' AS status, payload FROM @updated;
    ELSE IF NOT EXISTS (
        SELECT 1 FROM claims.Communication WHERE communication_id = @communication_id
    )
        SELECT N'missing' AS status, CAST(NULL AS nvarchar(max)) AS payload;
    ELSE
        SELECT N'conflict' AS status, payload
        FROM claims.Communication WHERE communication_id = @communication_id;
END;
