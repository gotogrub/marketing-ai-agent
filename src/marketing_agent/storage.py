from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3


class SessionStore:
    def __init__(self, path: Path | None):
        self.path = path

        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._init_db()

    def _connect(self) -> sqlite3.Connection:
        if not self.path:
            raise RuntimeError("SessionStore path is disabled")

        return sqlite3.connect(self.path)

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def add_message(self, user_id: str, role: str, content: str) -> None:
        if not self.path:
            return

        with self._connect() as connection:
            connection.execute(
                "INSERT INTO messages(user_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (user_id, role, content, datetime.now(timezone.utc).isoformat()),
            )

    def recent_messages(self, user_id: str, limit: int = 10) -> list[dict[str, str]]:
        if not self.path:
            return []

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT role, content, created_at
                FROM messages
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()

        return [
            {"role": role, "content": content, "created_at": created_at}
            for role, content, created_at in reversed(rows)
        ]
