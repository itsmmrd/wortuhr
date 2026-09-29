from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from bot import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER PRIMARY KEY,
    display_name TEXT NOT NULL DEFAULT '',
    timezone TEXT NOT NULL DEFAULT 'Europe/Berlin',
    translation_language TEXT NOT NULL DEFAULT 'English',
    ready INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    language TEXT NOT NULL,
    level TEXT NOT NULL,
    content_type TEXT NOT NULL,
    topic TEXT NOT NULL,
    schedule_mode TEXT NOT NULL,
    time_1 TEXT,
    time_2 TEXT,
    window_start TEXT,
    window_end TEXT,
    next_random_at TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    plan_id INTEGER,
    content_type TEXT NOT NULL,
    language TEXT NOT NULL,
    level TEXT NOT NULL,
    topic TEXT NOT NULL,
    term TEXT NOT NULL,
    translation TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    sent_at TEXT NOT NULL,
    local_day TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS deliveries (
    plan_id INTEGER NOT NULL,
    slot TEXT NOT NULL,
    sent_on TEXT NOT NULL,
    status TEXT NOT NULL,
    item_id INTEGER,
    attempts INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (plan_id, slot, sent_on)
);

CREATE INDEX IF NOT EXISTS idx_items_user_status ON items (user_id, status, content_type);
CREATE INDEX IF NOT EXISTS idx_items_user_day ON items (user_id, local_day);
CREATE INDEX IF NOT EXISTS idx_plans_user ON plans (user_id, active);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class User:
    telegram_id: int
    display_name: str
    timezone: str
    translation_language: str
    ready: int
    created_at: str


@dataclass
class Plan:
    id: int
    user_id: int
    language: str
    level: str
    content_type: str
    topic: str
    schedule_mode: str
    time_1: str | None
    time_2: str | None
    window_start: str | None
    window_end: str | None
    next_random_at: str | None
    active: int
    created_at: str


@dataclass
class Item:
    id: int
    user_id: int
    plan_id: int | None
    content_type: str
    language: str
    level: str
    topic: str
    term: str
    translation: str
    payload_json: str
    status: str
    sent_at: str
    local_day: str
    updated_at: str


def _row_to(cls, row: sqlite3.Row):
    return cls(**{field: row[field] for field in cls.__dataclass_fields__})


class Database:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else config.DB_PATH
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.Lock()

    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("PRAGMA foreign_keys=ON")
            self._conn = conn
        return self._conn

    def init(self) -> None:
        with self._lock:
            conn = self.connect()
            conn.executescript(SCHEMA)
            conn.commit()

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def get_setting(self, key: str) -> str | None:
        with self._lock:
            row = self.connect().execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
        return None if row is None else str(row["value"])

    def set_setting(self, key: str, value: str) -> None:
        with self._lock:
            self.connect().execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
            self.connect().commit()

    def upsert_user(self, telegram_id: int, display_name: str) -> User:
        now = utcnow()
        name = display_name.strip()[:64]
        with self._lock:
            conn = self.connect()
            conn.execute(
                "INSERT INTO users (telegram_id, display_name, created_at) VALUES (?, ?, ?) "
                "ON CONFLICT(telegram_id) DO UPDATE SET display_name = excluded.display_name",
                (telegram_id, name, now),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
            ).fetchone()
        return _row_to(User, row)

    def get_user(self, telegram_id: int) -> User | None:
        with self._lock:
            row = self.connect().execute(
                "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
            ).fetchone()
        return None if row is None else _row_to(User, row)

    def set_timezone(self, telegram_id: int, timezone_name: str) -> None:
        with self._lock:
            self.connect().execute(
                "UPDATE users SET timezone = ? WHERE telegram_id = ?",
                (timezone_name, telegram_id),
            )
            self.connect().commit()

    def set_translation_language(self, telegram_id: int, language: str) -> None:
        with self._lock:
            self.connect().execute(
                "UPDATE users SET translation_language = ? WHERE telegram_id = ?",
                (language, telegram_id),
            )
            self.connect().commit()

    def set_ready(self, telegram_id: int) -> None:
        with self._lock:
            self.connect().execute(
                "UPDATE users SET ready = 1 WHERE telegram_id = ?",
                (telegram_id,),
            )
            self.connect().commit()

    def create_plan(self, **fields) -> Plan:
        now = utcnow()
        columns = [
            "user_id",
            "language",
            "level",
            "content_type",
            "topic",
            "schedule_mode",
            "time_1",
            "time_2",
            "window_start",
            "window_end",
            "next_random_at",
            "active",
            "created_at",
        ]
        values = [fields.get(column) for column in columns[:-2]]
        values.append(1)
        values.append(now)
        placeholders = ", ".join("?" for _ in columns)
        with self._lock:
            conn = self.connect()
            cursor = conn.execute(
                f"INSERT INTO plans ({', '.join(columns)}) VALUES ({placeholders})",
                values,
            )
            conn.commit()
            plan_id = int(cursor.lastrowid)
            row = conn.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
        return _row_to(Plan, row)

    def update_plan(self, plan_id: int, user_id: int | None = None, **fields) -> None:
        allowed = {
            "language",
            "level",
            "content_type",
            "topic",
            "schedule_mode",
            "time_1",
            "time_2",
            "window_start",
            "window_end",
            "next_random_at",
            "active",
        }
        pairs = [(key, value) for key, value in fields.items() if key in allowed]
        if not pairs:
            return
        assignments = ", ".join(f"{key} = ?" for key, _value in pairs)
        params: list = [value for _key, value in pairs]
        where = "id = ?"
        params.append(plan_id)
        if user_id is not None:
            where += " AND user_id = ?"
            params.append(user_id)
        with self._lock:
            self.connect().execute(f"UPDATE plans SET {assignments} WHERE {where}", params)
            self.connect().commit()

    def delete_plan(self, plan_id: int, user_id: int) -> bool:
        with self._lock:
            cursor = self.connect().execute(
                "DELETE FROM plans WHERE id = ? AND user_id = ?",
                (plan_id, user_id),
            )
            self.connect().commit()
        return cursor.rowcount > 0

    def get_plan(self, plan_id: int, user_id: int | None = None) -> Plan | None:
        sql = "SELECT * FROM plans WHERE id = ?"
        params: list = [plan_id]
        if user_id is not None:
            sql += " AND user_id = ?"
            params.append(user_id)
        with self._lock:
            row = self.connect().execute(sql, params).fetchone()
        return None if row is None else _row_to(Plan, row)

    def list_plans(self, user_id: int) -> list[Plan]:
        with self._lock:
            rows = self.connect().execute(
                "SELECT * FROM plans WHERE user_id = ? ORDER BY id",
                (user_id,),
            ).fetchall()
        return [_row_to(Plan, row) for row in rows]

    def list_active_plans(self) -> list[Plan]:
        with self._lock:
            rows = self.connect().execute(
                "SELECT plans.* FROM plans "
                "JOIN users ON users.telegram_id = plans.user_id "
                "WHERE plans.active = 1 AND users.ready = 1 "
                "ORDER BY plans.id"
            ).fetchall()
        return [_row_to(Plan, row) for row in rows]

    def set_plan_active(self, plan_id: int, user_id: int, active: bool) -> None:
        self.update_plan(plan_id, user_id, active=1 if active else 0)

    def pause_user_plans(self, user_id: int) -> None:
        with self._lock:
            self.connect().execute(
                "UPDATE plans SET active = 0 WHERE user_id = ?",
                (user_id,),
            )
            self.connect().commit()

    def add_item(self, **fields) -> Item:
        now = utcnow()
        columns = [
            "user_id",
            "plan_id",
            "content_type",
            "language",
            "level",
            "topic",
            "term",
            "translation",
            "payload_json",
            "status",
            "sent_at",
            "local_day",
            "updated_at",
        ]
        taken = columns[:9]
        values = [fields[column] for column in taken]
        values.extend(["new", now, fields["local_day"], now])
        placeholders = ", ".join("?" for _ in columns)
        with self._lock:
            conn = self.connect()
            cursor = conn.execute(
                f"INSERT INTO items ({', '.join(columns)}) VALUES ({placeholders})",
                values,
            )
            conn.commit()
            item_id = int(cursor.lastrowid)
            row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        return _row_to(Item, row)

    def delete_item(self, item_id: int) -> None:
        with self._lock:
            self.connect().execute("DELETE FROM items WHERE id = ?", (item_id,))
            self.connect().commit()

    def get_item(self, item_id: int, user_id: int | None = None) -> Item | None:
        sql = "SELECT * FROM items WHERE id = ?"
        params: list = [item_id]
        if user_id is not None:
            sql += " AND user_id = ?"
            params.append(user_id)
        with self._lock:
            row = self.connect().execute(sql, params).fetchone()
        return None if row is None else _row_to(Item, row)

    def set_item_status(self, item_id: int, user_id: int, status: str) -> bool:
        with self._lock:
            cursor = self.connect().execute(
                "UPDATE items SET status = ?, updated_at = ? WHERE id = ? AND user_id = ?",
                (status, utcnow(), item_id, user_id),
            )
            self.connect().commit()
        return cursor.rowcount > 0

    def recent_terms(self, user_id: int, language: str, content_type: str, limit: int = 40) -> list[str]:
        with self._lock:
            rows = self.connect().execute(
                "SELECT term FROM items WHERE user_id = ? AND language = ? AND content_type = ? "
                "ORDER BY id DESC LIMIT ?",
                (user_id, language, content_type, limit),
            ).fetchall()
        return [str(row["term"]) for row in rows]

    def counts(self, user_id: int) -> dict[str, int]:
        with self._lock:
            rows = self.connect().execute(
                "SELECT content_type, status, COUNT(*) AS n FROM items "
                "WHERE user_id = ? GROUP BY content_type, status",
                (user_id,),
            ).fetchall()
        stats = {
            "sent": 0,
            "learned": 0,
            "repeat": 0,
            "words_sent": 0,
            "words_learned": 0,
            "idioms_sent": 0,
            "idioms_learned": 0,
        }
        for row in rows:
            amount = int(row["n"])
            stats["sent"] += amount
            if row["status"] == "learned":
                stats["learned"] += amount
            elif row["status"] == "repeat":
                stats["repeat"] += amount
            if row["content_type"] == "word":
                stats["words_sent"] += amount
                if row["status"] == "learned":
                    stats["words_learned"] += amount
            elif row["content_type"] == "idiom":
                stats["idioms_sent"] += amount
                if row["status"] == "learned":
                    stats["idioms_learned"] += amount
        return stats

    def list_items(
        self,
        user_id: int,
        *,
        content_type: str | None = None,
        status: str | None = None,
        limit: int = 5,
        offset: int = 0,
    ) -> list[Item]:
        clauses = ["user_id = ?"]
        params: list = [user_id]
        if content_type is not None:
            clauses.append("content_type = ?")
            params.append(content_type)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        params.extend([limit, offset])
        sql = (
            f"SELECT * FROM items WHERE {' AND '.join(clauses)} "
            "ORDER BY id DESC LIMIT ? OFFSET ?"
        )
        with self._lock:
            rows = self.connect().execute(sql, params).fetchall()
        return [_row_to(Item, row) for row in rows]

    def count_items(
        self,
        user_id: int,
        *,
        content_type: str | None = None,
        status: str | None = None,
    ) -> int:
        clauses = ["user_id = ?"]
        params: list = [user_id]
        if content_type is not None:
            clauses.append("content_type = ?")
            params.append(content_type)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        sql = f"SELECT COUNT(*) AS n FROM items WHERE {' AND '.join(clauses)}"
        with self._lock:
            row = self.connect().execute(sql, params).fetchone()
        return int(row["n"])

    def activity_counts(self, user_id: int, since_day: str) -> dict[str, int]:
        with self._lock:
            rows = self.connect().execute(
                "SELECT local_day, COUNT(*) AS n FROM items "
                "WHERE user_id = ? AND local_day >= ? GROUP BY local_day",
                (user_id, since_day),
            ).fetchall()
        return {str(row["local_day"]): int(row["n"]) for row in rows}

    def learned_for_summary(self, user_id: int, limit: int = 30) -> list[Item]:
        with self._lock:
            rows = self.connect().execute(
                "SELECT * FROM items WHERE user_id = ? AND status = 'learned' "
                "ORDER BY updated_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [_row_to(Item, row) for row in rows]

    def delivery_info(self, plan_id: int, slot: str, sent_on: str) -> tuple[str | None, int]:
        with self._lock:
            row = self.connect().execute(
                "SELECT status, attempts FROM deliveries WHERE plan_id = ? AND slot = ? AND sent_on = ?",
                (plan_id, slot, sent_on),
            ).fetchone()
        if row is None:
            return None, 0
        return str(row["status"]), int(row["attempts"])

    def claim_delivery(self, plan_id: int, slot: str, sent_on: str) -> int | None:
        now = utcnow()
        with self._lock:
            conn = self.connect()
            row = conn.execute(
                "SELECT status, attempts, updated_at FROM deliveries "
                "WHERE plan_id = ? AND slot = ? AND sent_on = ?",
                (plan_id, slot, sent_on),
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO deliveries (plan_id, slot, sent_on, status, attempts, updated_at) "
                    "VALUES (?, ?, ?, 'sending', 1, ?)",
                    (plan_id, slot, sent_on, now),
                )
                conn.commit()
                return 1
            status = str(row["status"])
            attempts = int(row["attempts"])
            if status == "sent" or attempts >= 3:
                return None
            if status == "sending":
                updated = datetime.fromisoformat(str(row["updated_at"]))
                age = datetime.now(timezone.utc) - updated
                if age.total_seconds() < 120:
                    return None
            attempts += 1
            conn.execute(
                "UPDATE deliveries SET status = 'sending', attempts = ?, updated_at = ? "
                "WHERE plan_id = ? AND slot = ? AND sent_on = ?",
                (attempts, now, plan_id, slot, sent_on),
            )
            conn.commit()
            return attempts

    def finish_delivery(self, plan_id: int, slot: str, sent_on: str, item_id: int | None) -> None:
        with self._lock:
            self.connect().execute(
                "UPDATE deliveries SET status = 'sent', item_id = ?, updated_at = ? "
                "WHERE plan_id = ? AND slot = ? AND sent_on = ?",
                (item_id, utcnow(), plan_id, slot, sent_on),
            )
            self.connect().commit()

    def release_delivery(self, plan_id: int, slot: str, sent_on: str) -> None:
        with self._lock:
            self.connect().execute(
                "UPDATE deliveries SET status = 'failed', updated_at = ? "
                "WHERE plan_id = ? AND slot = ? AND sent_on = ?",
                (utcnow(), plan_id, slot, sent_on),
            )
            self.connect().commit()


db = Database()
