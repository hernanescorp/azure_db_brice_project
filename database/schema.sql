IF NOT EXISTS (
    SELECT 1 FROM sys.schemas WHERE name = 'brice'
)
BEGIN
    EXEC('CREATE SCHEMA brice');
END;
GO
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

CREATE TABLE brice.events (
    event_id INT IDENTITY(1,1) PRIMARY KEY,
    event_name NVARCHAR(255),
    event_date DATE,
    location NVARCHAR(255),
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO

CREATE TABLE brice.event_participation (
    participation_id INT IDENTITY(1,1) PRIMARY KEY,
    event_id INT NOT NULL,
    contact_id INT NOT NULL,
    status NVARCHAR(50),
    source NVARCHAR(255),
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),

    CONSTRAINT FK_event_participation_events
        FOREIGN KEY (event_id) REFERENCES brice.events(event_id),

    CONSTRAINT FK_event_participation_contacts
        FOREIGN KEY (contact_id) REFERENCES brice.marketing_contacts(contact_id)
);
GO