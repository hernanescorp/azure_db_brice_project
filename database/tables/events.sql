CREATE TABLE brice.events (
    event_id INT IDENTITY(1,1) PRIMARY KEY,
    event_name NVARCHAR(255),
    event_date DATE,
    location NVARCHAR(255),
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO