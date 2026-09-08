CREATE TABLE IF NOT EXISTS inquiries (
    
    id SERIAL PRIMARY KEY,
    title VARCHAR(160) NOT NULL,
    description TEXT NOT NULL,
    requester_name VARCHAR(120) NOT NULL,
    requester_email VARCHAR(254) NOT NULL,
    assignee VARCHAR(120),
    status VARCHAR(30) NOT NULL DEFAULT 'Open',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT inquiries_status_check CHECK (status IN ('Open', 'In Progress', 'Resolved', 'Closed'))
);

CREATE INDEX IF NOT EXISTS inquiries_search_idx
ON inquiries USING GIN (to_tsvector('english', title || ' ' || description || ' ' || requester_name || ' ' || requester_email));

INSERT INTO inquiries (title, description, requester_name, requester_email, assignee, status)
VALUES
  ('Unable to access monthly report', 'The export button returns a blank CSV for the finance workspace.', 'Maya Chen', 'maya.chen@example.com', 'Jordan Lee', 'In Progress'),
  ('Request for onboarding access', 'Please provision access to the customer success workspace for the new team members.', 'Elliot Brooks', 'elliot.brooks@example.com', NULL, 'Open'),
  ('Update billing contact', 'The billing contact on our account needs to be changed before the next invoice.', 'Priya Nair', 'priya.nair@example.com', 'Jordan Lee', 'Resolved')
ON CONFLICT DO NOTHING;