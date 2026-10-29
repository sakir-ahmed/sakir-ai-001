-- =============================================================================
-- dt-assistant schema. Applied on every start; every statement is idempotent.
-- All timestamps are timestamptz (UTC in the database, shown in Asia/Dhaka).
-- =============================================================================

-- People who wrote to the page (Messenger, comments, Instagram).
CREATE TABLE IF NOT EXISTS leads (
    id               SERIAL PRIMARY KEY,
    channel_user_id  TEXT NOT NULL UNIQUE,          -- PSID, IGSID or commenter id
    source           TEXT NOT NULL,                 -- messenger | comment | instagram
    name             TEXT,
    business         TEXT,
    phone            TEXT,
    product          TEXT NOT NULL DEFAULT 'restora',
    stage            TEXT NOT NULL DEFAULT 'new',   -- new, interested, demo, proposal, won, lost
    language         TEXT,                          -- bn | banglish | en
    last_inbound_at  TIMESTAMPTZ,
    last_outbound_at TIMESTAMPTZ,
    followup_sent_at TIMESTAMPTZ,
    holding_sent_at  TIMESTAMPTZ,
    notes            TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS leads_stage_idx ON leads (stage);

-- Every inbound and outbound message.
CREATE TABLE IF NOT EXISTS messages (
    id          SERIAL PRIMARY KEY,
    lead_id     INT REFERENCES leads(id) ON DELETE CASCADE,
    meta_id     TEXT UNIQUE,                        -- Meta message/comment id (dedupe)
    channel     TEXT NOT NULL,                      -- messenger | comment | instagram
    direction   TEXT NOT NULL,                      -- in | out
    text        TEXT,
    intent      TEXT,
    language    TEXT,
    confidence  REAL,
    how         TEXT,                               -- auto | template | approved | edited | holding
    target_id   TEXT,                               -- comment id or post id for comments
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS messages_lead_idx ON messages (lead_id, created_at);
CREATE INDEX IF NOT EXISTS messages_created_idx ON messages (created_at);

-- Drafts waiting for Sakir in @DTSalesDesk_bot.
CREATE TABLE IF NOT EXISTS approvals (
    id                  SERIAL PRIMARY KEY,
    lead_id             INT REFERENCES leads(id) ON DELETE CASCADE,
    inbound_message_id  INT REFERENCES messages(id) ON DELETE SET NULL,
    kind                TEXT NOT NULL DEFAULT 'reply',      -- reply | followup | escalation
    channel             TEXT NOT NULL,                      -- messenger | comment | instagram
    target_id           TEXT NOT NULL,                      -- PSID/IGSID or comment id
    intent              TEXT,
    draft               TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'waiting',    -- waiting, sent, rejected, expired, failed
    edited              BOOLEAN NOT NULL DEFAULT false,
    sent_text           TEXT,
    telegram_message_id BIGINT,
    stale_notified      BOOLEAN NOT NULL DEFAULT false,
    error               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    decided_at          TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS approvals_status_idx ON approvals (status, created_at);

-- Approved posts to publish (filled by Hermes after Sakir approves a content pack).
CREATE TABLE IF NOT EXISTS content_calendar (
    id          SERIAL PRIMARY KEY,
    product     TEXT NOT NULL,
    platform    TEXT NOT NULL,                      -- facebook, instagram, youtube, linkedin, tiktok, x
    publish_at  TIMESTAMPTZ NOT NULL,
    caption     TEXT NOT NULL,
    media_path  TEXT,                               -- file under /outbox
    status      TEXT NOT NULL DEFAULT 'approved',   -- approved, posted, reminded, failed, cancelled
    result      TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS calendar_due_idx ON content_calendar (status, publish_at);

-- Model spend per day and purpose (classify, reply, reply_premium, followup).
CREATE TABLE IF NOT EXISTS spend (
    day        DATE NOT NULL,
    purpose    TEXT NOT NULL,
    usd        NUMERIC(10, 5) NOT NULL DEFAULT 0,
    tokens_in  BIGINT NOT NULL DEFAULT 0,
    tokens_out BIGINT NOT NULL DEFAULT 0,
    calls      INT NOT NULL DEFAULT 0,
    PRIMARY KEY (day, purpose)
);

-- Small key/value store: pause flag, alert markers, edit state.
CREATE TABLE IF NOT EXISTS settings (
    key        TEXT PRIMARY KEY,
    value      JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Daily metrics snapshot (21:00), read by Hermes for the evening summary.
CREATE TABLE IF NOT EXISTS metrics (
    day  DATE PRIMARY KEY,
    data JSONB NOT NULL
);
