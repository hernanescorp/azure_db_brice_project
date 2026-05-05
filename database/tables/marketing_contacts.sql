CREATE TABLE brice.marketing_contacts (
    contact_id INT IDENTITY(1,1) PRIMARY KEY,
    first_name NVARCHAR(100),
    last_name NVARCHAR(100),
    email NVARCHAR(255) NOT NULL UNIQUE,
    phone NVARCHAR(50),
    company NVARCHAR(255),
    consent_marketing BIT NOT NULL DEFAULT 0,
    consent_date DATETIME2,
    consent_source NVARCHAR(255),
    unsubscribed BIT NOT NULL DEFAULT 0,
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO