"""SQLite storage layer. Standard library only."""
import json
import os
import sqlite3
import threading
from datetime import datetime, timezone

DB_PATH = os.environ.get(
    "OUTREACH_DB",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "outreach.db"),
)

_local = threading.local()

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT DEFAULT '',
    last_name TEXT DEFAULT '',
    email TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    linkedin_url TEXT DEFAULT '',
    company TEXT DEFAULT '',
    title TEXT DEFAULT '',
    website TEXT DEFAULT '',
    custom TEXT DEFAULT '{}',
    status TEXT DEFAULT 'new',
    source TEXT DEFAULT '',
    created_at TEXT,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email);
CREATE INDEX IF NOT EXISTS idx_contacts_li ON contacts(linkedin_url);
CREATE INDEX IF NOT EXISTS idx_contacts_status ON contacts(status);

CREATE TABLE IF NOT EXISTS lists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS list_members (
    list_id INTEGER NOT NULL,
    contact_id INTEGER NOT NULL,
    PRIMARY KEY (list_id, contact_id)
);

CREATE TABLE IF NOT EXISTS sequences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sequence_id INTEGER NOT NULL,
    position INTEGER NOT NULL,
    channel TEXT NOT NULL,              -- email | linkedin | call
    action TEXT DEFAULT 'message',      -- email: message; linkedin: connect|message|view; call: call
    delay_days INTEGER DEFAULT 0,
    delay_hours INTEGER DEFAULT 0,
    subject TEXT DEFAULT '',
    body TEXT DEFAULT '',
    requires_field TEXT DEFAULT '',     -- waterfall gate: email|phone|linkedin_url|''
    on_missing TEXT DEFAULT 'skip',     -- skip (fall through to next step) | stop
    auto_send INTEGER DEFAULT 1,        -- email only; manual channels always queue
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_steps_seq ON steps(sequence_id, position);

CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    sequence_id INTEGER NOT NULL,
    status TEXT DEFAULT 'draft',        -- draft | running | paused | done
    daily_limit INTEGER DEFAULT 50,
    window_start INTEGER DEFAULT 8,
    window_end INTEGER DEFAULT 18,
    weekdays_only INTEGER DEFAULT 1,
    stop_on_reply INTEGER DEFAULT 1,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    contact_id INTEGER NOT NULL,
    status TEXT DEFAULT 'active',       -- active | waiting | finished | replied | stopped | bounced
    step_index INTEGER DEFAULT 0,
    next_action_at TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_enroll_unique ON enrollments(campaign_id, contact_id);
CREATE INDEX IF NOT EXISTS idx_enroll_due ON enrollments(status, next_action_at);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    enrollment_id INTEGER,
    campaign_id INTEGER,
    contact_id INTEGER NOT NULL,
    step_id INTEGER,
    step_index INTEGER DEFAULT 0,
    channel TEXT NOT NULL,
    action TEXT DEFAULT 'message',
    status TEXT DEFAULT 'pending',      -- pending | done | skipped | failed
    due_at TEXT,
    subject TEXT DEFAULT '',
    body TEXT DEFAULT '',
    outcome TEXT DEFAULT '',            -- call disposition / linkedin result
    notes TEXT DEFAULT '',
    created_at TEXT,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status, due_at);
CREATE INDEX IF NOT EXISTS idx_tasks_contact ON tasks(contact_id);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER NOT NULL,
    campaign_id INTEGER,
    task_id INTEGER,
    channel TEXT NOT NULL,              -- email | linkedin | call
    direction TEXT NOT NULL,            -- out | in | note
    subject TEXT DEFAULT '',
    body TEXT DEFAULT '',
    status TEXT DEFAULT 'sent',         -- sent | failed | dry_run | received
    error TEXT DEFAULT '',
    message_id TEXT DEFAULT '',
    open_count INTEGER DEFAULT 0,
    opened_at TEXT,
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_msg_contact ON messages(contact_id, created_at);
CREATE INDEX IF NOT EXISTS idx_msg_dir ON messages(direction, created_at);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER,
    campaign_id INTEGER,
    step_index INTEGER,
    channel TEXT DEFAULT '',
    type TEXT NOT NULL,                 -- sent | open | reply | bounce | unsubscribe | call | linkedin | skipped | failed
    meta TEXT DEFAULT '{}',
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(type, created_at);
CREATE INDEX IF NOT EXISTS idx_events_campaign ON events(campaign_id, created_at);

CREATE TABLE IF NOT EXISTS threads (
    contact_id INTEGER PRIMARY KEY,
    last_message_at TEXT,
    last_direction TEXT DEFAULT 'out',
    last_channel TEXT DEFAULT 'email',
    snippet TEXT DEFAULT '',
    unread INTEGER DEFAULT 0,
    state TEXT DEFAULT 'open'           -- open | closed | won | lost
);
CREATE INDEX IF NOT EXISTS idx_threads_time ON threads(last_message_at);

CREATE TABLE IF NOT EXISTS suppressions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    value TEXT NOT NULL,                -- lowercased email or domain
    kind TEXT DEFAULT 'email',          -- email | domain
    reason TEXT DEFAULT '',
    created_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_supp_value ON suppressions(value, kind);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS sendlog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day TEXT NOT NULL,
    campaign_id INTEGER NOT NULL,
    count INTEGER DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_sendlog ON sendlog(day, campaign_id);
"""

DEFAULT_SETTINGS = {
    "dry_run": "1",
    "smtp_host": "",
    "smtp_port": "587",
    "smtp_user": "",
    "smtp_pass": "",
    "smtp_security": "starttls",
    "from_name": "",
    "from_email": "",
    "reply_to": "",
    "imap_host": "",
    "imap_port": "993",
    "imap_user": "",
    "imap_pass": "",
    "imap_folder": "INBOX",
    "imap_poll_minutes": "10",
    "track_opens": "1",
    "base_url": "http://127.0.0.1:8000",
    "engine_enabled": "1",
    "signature": "",
}


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def conn():
    c = getattr(_local, "conn", None)
    if c is None:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        c = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("PRAGMA busy_timeout=10000")
        _local.conn = c
    return c


def init():
    c = conn()
    c.executescript(SCHEMA)
    for k, v in DEFAULT_SETTINGS.items():
        c.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (k, v))
    c.commit()


def query(sql, params=()):
    return [dict(r) for r in conn().execute(sql, params).fetchall()]


def query_one(sql, params=()):
    row = conn().execute(sql, params).fetchone()
    return dict(row) if row else None


def execute(sql, params=()):
    c = conn()
    cur = c.execute(sql, params)
    c.commit()
    return cur


def insert(table, data):
    keys = list(data.keys())
    sql = "INSERT INTO %s (%s) VALUES (%s)" % (
        table,
        ", ".join(keys),
        ", ".join("?" for _ in keys),
    )
    return execute(sql, tuple(data[k] for k in keys)).lastrowid


def update(table, row_id, data):
    if not data:
        return
    keys = list(data.keys())
    sql = "UPDATE %s SET %s WHERE id = ?" % (table, ", ".join(k + " = ?" for k in keys))
    execute(sql, tuple(data[k] for k in keys) + (row_id,))


def get_settings():
    return {r["key"]: r["value"] for r in query("SELECT key, value FROM settings")}


def set_settings(data):
    c = conn()
    for k, v in data.items():
        c.execute(
            "INSERT INTO settings(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (k, str(v)),
        )
    c.commit()


def log_event(contact_id, campaign_id, step_index, channel, etype, meta=None):
    insert(
        "events",
        {
            "contact_id": contact_id,
            "campaign_id": campaign_id,
            "step_index": step_index,
            "channel": channel or "",
            "type": etype,
            "meta": json.dumps(meta or {}),
            "created_at": now_iso(),
        },
    )


def touch_thread(contact_id, direction, channel, snippet, unread=None):
    existing = query_one("SELECT contact_id, unread FROM threads WHERE contact_id = ?", (contact_id,))
    snippet = (snippet or "").strip().replace("\n", " ")[:160]
    if existing:
        sql = (
            "UPDATE threads SET last_message_at = ?, last_direction = ?, last_channel = ?, snippet = ?"
            + (", unread = ?" if unread is not None else "")
            + " WHERE contact_id = ?"
        )
        params = [now_iso(), direction, channel, snippet]
        if unread is not None:
            params.append(1 if unread else 0)
        params.append(contact_id)
        execute(sql, tuple(params))
    else:
        insert(
            "threads",
            {
                "contact_id": contact_id,
                "last_message_at": now_iso(),
                "last_direction": direction,
                "last_channel": channel,
                "snippet": snippet,
                "unread": 1 if unread else 0,
                "state": "open",
            },
        )
