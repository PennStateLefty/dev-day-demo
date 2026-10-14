CREATE OR ALTER PROCEDURE claims.AddReviewNote
    @claim_id nvarchar(100),
    @note nvarchar(2000)
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    IF NOT EXISTS (SELECT 1 FROM claims.Claim WHERE claim_id = @claim_id)
        THROW 50001, 'Synthetic claim does not exist.', 1;
    IF @note IS NULL OR LEN(LTRIM(RTRIM(@note))) = 0
        THROW 50002, 'Review note must not be empty.', 1;
    DECLARE @note_id uniqueidentifier = NEWID();
    INSERT claims.ReviewNote(note_id, claim_id, note)
        VALUES (@note_id, @claim_id, @note);
    SELECT CONVERT(nvarchar(36), @note_id) AS note_id;
END;
