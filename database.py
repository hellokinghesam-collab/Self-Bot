"""
database.py
-----------
لایه‌ی دیتابیس SQLite. تمام لیست‌ها (دوست/دشمن)، تنظیمات کلید-مقدار،
و پیام‌های زمان‌بندی‌شده اینجا نگهداری می‌شوند.

طراحی به گونه‌ای است که:
- Query ها همیشه parametrized هستند (جلوگیری از SQL Injection).
- دسترسی به فایل دیتابیس فقط از داخل پوشه‌ی پروژه است.
"""

import sqlite3
import os
import time
import threading
from contextlib import contextmanager
from typing import Optional, Iterable

from config import DB_PATH

_lock = threading.Lock()


def _ensure_dir():
    d = os.path.dirname(DB_PATH)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)


@contextmanager
def get_conn():
    _ensure_dir()
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row
    try:
        with _lock:
            yield conn
            conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS lists (
                list_name TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                note TEXT DEFAULT '',
                added_at INTEGER NOT NULL,
                PRIMARY KEY (list_name, user_id)
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS scheduled_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                send_at INTEGER NOT NULL,
                sent INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS plugins (
                name TEXT PRIMARY KEY,
                enabled INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS forward_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_chat_id INTEGER NOT NULL,
                dest_chat_id INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                UNIQUE(source_chat_id, dest_chat_id)
            );

            CREATE TABLE IF NOT EXISTS daily_stats (
                day TEXT PRIMARY KEY,
                messages_sent INTEGER DEFAULT 0,
                messages_received INTEGER DEFAULT 0,
                commands_run INTEGER DEFAULT 0,
                private_chats TEXT DEFAULT '[]',
                group_chats TEXT DEFAULT '[]'
            );
            """
        )


# ---------------------------------------------------------------------------
# لیست‌ها (دوست / دشمن / هر لیست دلخواه دیگر)
# ---------------------------------------------------------------------------

def list_add(list_name: str, user_id: int, note: str = "") -> bool:
    """افزودن یک کاربر به یک لیست. اگر قبلاً بود، False برمی‌گرداند."""
    with get_conn() as conn:
        try:
            conn.execute(
                "INSERT INTO lists (list_name, user_id, note, added_at) VALUES (?, ?, ?, ?)",
                (list_name, user_id, note, int(time.time())),
            )
            return True
        except sqlite3.IntegrityError:
            return False


def list_remove(list_name: str, user_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM lists WHERE list_name = ? AND user_id = ?",
            (list_name, user_id),
        )
        return cur.rowcount > 0


def list_contains(list_name: str, user_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM lists WHERE list_name = ? AND user_id = ?",
            (list_name, user_id),
        ).fetchone()
        return row is not None


def list_get_all(list_name: str) -> Iterable[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT user_id, note, added_at FROM lists WHERE list_name = ? ORDER BY added_at DESC",
            (list_name,),
        ).fetchall()


def list_clear(list_name: str) -> int:
    """پاکسازی کامل یک لیست. تعداد ردیف‌های حذف‌شده را برمی‌گرداند."""
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM lists WHERE list_name = ?", (list_name,))
        return cur.rowcount


def list_names() -> list:
    """نام تمام لیست‌هایی که حداقل یک عضو دارند."""
    with get_conn() as conn:
        rows = conn.execute("SELECT DISTINCT list_name FROM lists").fetchall()
        return [r["list_name"] for r in rows]


# ---------------------------------------------------------------------------
# تنظیمات کلید-مقدار (فعال/غیرفعال بودن قابلیت‌ها و ...)
# ---------------------------------------------------------------------------

def setting_set(key: str, value: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def setting_get(key: str, default: Optional[str] = None) -> Optional[str]:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default


def setting_get_bool(key: str, default: bool = False) -> bool:
    val = setting_get(key, "1" if default else "0")
    return val == "1"


def setting_set_bool(key: str, value: bool):
    setting_set(key, "1" if value else "0")


# ---------------------------------------------------------------------------
# پیام‌های زمان‌بندی‌شده
# ---------------------------------------------------------------------------

def schedule_add(chat_id: int, text: str, send_at: int) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO scheduled_messages (chat_id, text, send_at, sent) VALUES (?, ?, ?, 0)",
            (chat_id, text, send_at),
        )
        return cur.lastrowid


def schedule_due(now_ts: int) -> Iterable[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, chat_id, text FROM scheduled_messages WHERE sent = 0 AND send_at <= ?",
            (now_ts,),
        ).fetchall()


def schedule_mark_sent(msg_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE scheduled_messages SET sent = 1 WHERE id = ?", (msg_id,))


def schedule_list_pending() -> Iterable[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, chat_id, text, send_at FROM scheduled_messages WHERE sent = 0 ORDER BY send_at ASC"
        ).fetchall()


def schedule_cancel(msg_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM scheduled_messages WHERE id = ?", (msg_id,))
        return cur.rowcount > 0


# ---------------------------------------------------------------------------
# پلاگین‌ها (فعال/غیرفعال)
# ---------------------------------------------------------------------------

def plugin_set_enabled(name: str, enabled: bool):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO plugins (name, enabled) VALUES (?, ?) "
            "ON CONFLICT(name) DO UPDATE SET enabled=excluded.enabled",
            (name, 1 if enabled else 0),
        )


def plugin_is_enabled(name: str, default: bool = True) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT enabled FROM plugins WHERE name = ?", (name,)).fetchone()
        if row is None:
            return default
        return bool(row["enabled"])


# ---------------------------------------------------------------------------
# قوانین فوروارد خودکار (source_chat_id -> dest_chat_id)
# ---------------------------------------------------------------------------

def forward_rule_add(source_chat_id: int, dest_chat_id: int) -> bool:
    with get_conn() as conn:
        try:
            conn.execute(
                "INSERT INTO forward_rules (source_chat_id, dest_chat_id, created_at) VALUES (?, ?, ?)",
                (source_chat_id, dest_chat_id, int(time.time())),
            )
            return True
        except sqlite3.IntegrityError:
            return False


def forward_rule_remove(source_chat_id: int, dest_chat_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM forward_rules WHERE source_chat_id = ? AND dest_chat_id = ?",
            (source_chat_id, dest_chat_id),
        )
        return cur.rowcount > 0


def forward_rules_for_source(source_chat_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT dest_chat_id FROM forward_rules WHERE source_chat_id = ?",
            (source_chat_id,),
        ).fetchall()


def forward_rules_all():
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, source_chat_id, dest_chat_id FROM forward_rules ORDER BY created_at DESC"
        ).fetchall()


# ---------------------------------------------------------------------------
# آمار روزانه
# ---------------------------------------------------------------------------

def _today_str() -> str:
    return time.strftime("%Y-%m-%d", time.localtime())


def _ensure_today_row(conn, day: str):
    conn.execute(
        "INSERT OR IGNORE INTO daily_stats (day) VALUES (?)",
        (day,),
    )


def stats_bump(field: str, chat_id: Optional[int] = None, is_group: bool = False):
    """
    یک شمارنده‌ی روزانه را یک واحد افزایش می‌دهد.
    field باید یکی از 'messages_sent', 'messages_received', 'commands_run' باشد.
    اگر chat_id داده شود، آن چت به مجموعه‌ی چت‌های امروز (خصوصی یا گروه) اضافه می‌شود.
    """
    if field not in ("messages_sent", "messages_received", "commands_run"):
        return
    day = _today_str()
    with get_conn() as conn:
        _ensure_today_row(conn, day)
        conn.execute(
            f"UPDATE daily_stats SET {field} = {field} + 1 WHERE day = ?",
            (day,),
        )
        if chat_id is not None:
            import json
            col = "group_chats" if is_group else "private_chats"
            row = conn.execute(f"SELECT {col} FROM daily_stats WHERE day = ?", (day,)).fetchone()
            try:
                chat_set = set(json.loads(row[col])) if row else set()
            except Exception:
                chat_set = set()
            chat_set.add(chat_id)
            conn.execute(
                f"UPDATE daily_stats SET {col} = ? WHERE day = ?",
                (json.dumps(list(chat_set)), day),
            )


def stats_get(day: Optional[str] = None) -> Optional[sqlite3.Row]:
    day = day or _today_str()
    with get_conn() as conn:
        return conn.execute("SELECT * FROM daily_stats WHERE day = ?", (day,)).fetchone()


def stats_get_range(days: int = 7) -> Iterable[sqlite3.Row]:
    """آمار N روز اخیر را برمی‌گرداند (بر اساس رشته‌ی تاریخ، مرتب‌شده صعودی)."""
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM daily_stats ORDER BY day DESC LIMIT ?",
            (days,),
        ).fetchall()
