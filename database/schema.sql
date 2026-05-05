IF NOT EXISTS (
    SELECT 1 FROM sys.schemas WHERE name = 'brice'
)
BEGIN
    EXEC('CREATE SCHEMA brice');
END;
GO

