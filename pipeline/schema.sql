-- SQLite schema of the dashboard index. Shared by pipeline/index_db.py (writes it)
-- and the Bun server tests (web/tests). The JSON stays the source of truth.
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE emails (
    source_file       TEXT PRIMARY KEY,
    folder_name       TEXT NOT NULL,
    bank              TEXT NOT NULL,
    date              TEXT,
    market_wrap       TEXT NOT NULL CHECK (market_wrap IN ('YES', 'NO')),
    primary_asset_tag TEXT NOT NULL,
    has_pdf           INTEGER NOT NULL,
    record_json       TEXT NOT NULL
);
CREATE TABLE email_asset_tags (
    source_file TEXT NOT NULL REFERENCES emails(source_file),
    tag         TEXT NOT NULL,
    parent      TEXT,            -- NULL for a primary class
    is_primary  INTEGER NOT NULL,
    PRIMARY KEY (source_file, tag)
);
CREATE TABLE email_companies (
    source_file TEXT NOT NULL REFERENCES emails(source_file),
    company     TEXT NOT NULL,
    PRIMARY KEY (source_file, company)
);
CREATE TABLE email_industries (
    source_file TEXT NOT NULL REFERENCES emails(source_file),
    industry    TEXT NOT NULL,   -- "SECTOR > Subindustry" or "Unknown"
    sector      TEXT,
    PRIMARY KEY (source_file, industry)
);
CREATE TABLE email_pdfs (
    source_file TEXT NOT NULL REFERENCES emails(source_file),
    filename    TEXT NOT NULL,
    position    INTEGER NOT NULL,
    PRIMARY KEY (source_file, filename)
);
CREATE INDEX idx_emails_date ON emails(date);
CREATE INDEX idx_emails_bank ON emails(bank);
CREATE INDEX idx_tags_tag ON email_asset_tags(tag);
CREATE INDEX idx_companies_company ON email_companies(company);
CREATE INDEX idx_industries_industry ON email_industries(industry);
CREATE VIRTUAL TABLE email_fts USING fts5(
    source_file UNINDEXED, title, bank, companies, industries, body, pdf_text,
    tokenize = 'unicode61 remove_diacritics 2'
);
