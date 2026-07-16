"""Persistencia SQLite para tareas, listas de la compra y recordatorios."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "bot.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Crea las tablas si no existen."""
    with _conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                title       TEXT    NOT NULL,
                done        INTEGER DEFAULT 0,
                priority    TEXT    DEFAULT 'normal',
                due_date    TEXT,
                created_at  TEXT
            );

            CREATE TABLE IF NOT EXISTS shopping_lists (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                name        TEXT    NOT NULL,
                created_at  TEXT
            );

            CREATE TABLE IF NOT EXISTS shopping_items (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                list_id     INTEGER NOT NULL,
                text        TEXT    NOT NULL,
                checked     INTEGER DEFAULT 0,
                created_at  TEXT,
                FOREIGN KEY (list_id) REFERENCES shopping_lists(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS reminders (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                chat_id     INTEGER NOT NULL,
                message     TEXT    NOT NULL,
                remind_at   TEXT    NOT NULL,
                recurring   TEXT,
                active      INTEGER DEFAULT 1,
                created_at  TEXT
            );
        """)


# ════════════════════════════════════════════════════════════
#  TAREAS
# ════════════════════════════════════════════════════════════
def add_task(user_id: int, title: str, priority: str = "normal", due_date: str | None = None) -> int:
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO tasks (user_id, title, priority, due_date, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, title, priority, due_date, _now()),
        )
        return cur.lastrowid  # type: ignore


def list_tasks(user_id: int, only_pending: bool = True) -> list[dict[str, Any]]:
    with _conn() as conn:
        if only_pending:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE user_id = ? AND done = 0 ORDER BY due_date ASC, id DESC",
                (user_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE user_id = ? ORDER BY done ASC, due_date ASC, id DESC",
                (user_id,),
            ).fetchall()
        return [dict(r) for r in rows]


def complete_task(user_id: int, task_id: int) -> bool:
    with _conn() as conn:
        cur = conn.execute(
            "UPDATE tasks SET done = 1 WHERE id = ? AND user_id = ? AND done = 0",
            (task_id, user_id),
        )
        return cur.rowcount > 0


def delete_task(user_id: int, task_id: int) -> bool:
    with _conn() as conn:
        cur = conn.execute(
            "DELETE FROM tasks WHERE id = ? AND user_id = ?",
            (task_id, user_id),
        )
        return cur.rowcount > 0


def get_task(user_id: int, task_id: int) -> dict[str, Any] | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND user_id = ?",
            (task_id, user_id),
        ).fetchone()
        return dict(row) if row else None


# ════════════════════════════════════════════════════════════
#  LISTAS DE LA COMPRA
# ════════════════════════════════════════════════════════════
def create_list(user_id: int, name: str) -> int:
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO shopping_lists (user_id, name, created_at) VALUES (?, ?, ?)",
            (user_id, name, _now()),
        )
        return cur.lastrowid  # type: ignore


def get_lists(user_id: int) -> list[dict[str, Any]]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM shopping_lists WHERE user_id = ? ORDER BY id DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_list(user_id: int, list_id: int) -> dict[str, Any] | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM shopping_lists WHERE id = ? AND user_id = ?",
            (list_id, user_id),
        ).fetchone()
        return dict(row) if row else None


def delete_list(user_id: int, list_id: int) -> bool:
    with _conn() as conn:
        cur = conn.execute(
            "DELETE FROM shopping_lists WHERE id = ? AND user_id = ?",
            (list_id, user_id),
        )
        return cur.rowcount > 0


def add_item(list_id: int, text: str) -> int:
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO shopping_items (list_id, text, created_at) VALUES (?, ?, ?)",
            (list_id, text, _now()),
        )
        return cur.lastrowid  # type: ignore


def list_items(list_id: int) -> list[dict[str, Any]]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM shopping_items WHERE list_id = ? ORDER BY checked ASC, id ASC",
            (list_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def check_item(list_id: int, item_id: int) -> bool:
    with _conn() as conn:
        cur = conn.execute(
            "UPDATE shopping_items SET checked = 1 WHERE id = ? AND list_id = ? AND checked = 0",
            (item_id, list_id),
        )
        return cur.rowcount > 0


def uncheck_item(list_id: int, item_id: int) -> bool:
    with _conn() as conn:
        cur = conn.execute(
            "UPDATE shopping_items SET checked = 0 WHERE id = ? AND list_id = ? AND checked = 1",
            (item_id, list_id),
        )
        return cur.rowcount > 0


def delete_item(list_id: int, item_id: int) -> bool:
    with _conn() as conn:
        cur = conn.execute(
            "DELETE FROM shopping_items WHERE id = ? AND list_id = ?",
            (item_id, list_id),
        )
        return cur.rowcount > 0


def clear_checked_items(list_id: int) -> int:
    with _conn() as conn:
        cur = conn.execute(
            "DELETE FROM shopping_items WHERE list_id = ? AND checked = 1",
            (list_id,),
        )
        return cur.rowcount


# ════════════════════════════════════════════════════════════
#  RECORDATORIOS
# ════════════════════════════════════════════════════════════
def add_reminder(
    user_id: int,
    chat_id: int,
    message: str,
    remind_at: str,
    recurring: str | None = None,
) -> int:
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO reminders (user_id, chat_id, message, remind_at, recurring, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, chat_id, message, remind_at, recurring, _now()),
        )
        return cur.lastrowid  # type: ignore


def get_pending_reminders() -> list[dict[str, Any]]:
    """Devuelve recordatorios activos cuya fecha ya pasó."""
    now = _now()
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM reminders WHERE active = 1 AND remind_at <= ? ORDER BY remind_at",
            (now,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_user_reminders(user_id: int) -> list[dict[str, Any]]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM reminders WHERE user_id = ? AND active = 1 ORDER BY remind_at",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def delete_reminder(user_id: int, reminder_id: int) -> bool:
    with _conn() as conn:
        cur = conn.execute(
            "DELETE FROM reminders WHERE id = ? AND user_id = ?",
            (reminder_id, user_id),
        )
        return cur.rowcount > 0


def disable_reminder(reminder_id: int) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE reminders SET active = 0 WHERE id = ?",
            (reminder_id,),
        )


def update_reminder_time(reminder_id: int, new_time: str) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE reminders SET remind_at = ?, active = 1 WHERE id = ?",
            (new_time, reminder_id),
        )
