import sqlite3
import os
from config import DATABASE_PATH

os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

SCHEMA = """
CREATE TABLE IF NOT EXISTS creators (
    id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    url TEXT NOT NULL,
    channel_id TEXT,
    name TEXT,
    handle TEXT,
    subs INTEGER,
    country TEXT,
    content_lang TEXT,
    category TEXT,
    avatar_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS screen_results (
    id TEXT PRIMARY KEY,
    creator_id TEXT NOT NULL REFERENCES creators(id),
    status TEXT NOT NULL DEFAULT 'pending',
    composite_score REAL,
    verdict TEXT,
    veto_flags TEXT,
    batch_job_id TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (batch_job_id) REFERENCES batch_jobs(id)
);

CREATE TABLE IF NOT EXISTS layer_results (
    id TEXT PRIMARY KEY,
    screen_result_id TEXT NOT NULL REFERENCES screen_results(id),
    layer_number INTEGER NOT NULL,
    layer_name TEXT NOT NULL,
    score REAL,
    level TEXT,
    details TEXT,
    signals TEXT,
    risk_keywords TEXT,
    log_output TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS batch_jobs (
    id TEXT PRIMARY KEY,
    file_name TEXT,
    total_count INTEGER DEFAULT 0,
    completed_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'running',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_screen_creator ON screen_results(creator_id);
CREATE INDEX IF NOT EXISTS idx_screen_status ON screen_results(status);
CREATE INDEX IF NOT EXISTS idx_layer_screen ON layer_results(screen_result_id);
CREATE INDEX IF NOT EXISTS idx_batch_status ON batch_jobs(status);
"""


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
