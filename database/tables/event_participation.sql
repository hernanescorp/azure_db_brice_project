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