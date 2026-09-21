"""
AURA OS — SQLite Episodic Memory Engine
Stores user goals, task execution graphs, tool audit trails, and execution states.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from aura.core.logger import logger


class MemoryDB:
    """Episodic database manager for AURA OS."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path.resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._init_tables()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self) -> None:
        """Create database schema if not present."""
        with self._get_connection() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS goals (
                id TEXT PRIMARY KEY,
                user_prompt TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at REAL NOT NULL,
                completed_at REAL
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                goal_id TEXT NOT NULL,
                title TEXT NOT NULL,
                tool_name TEXT,
                status TEXT NOT NULL,
                result_json TEXT,
                error TEXT,
                created_at REAL NOT NULL,
                FOREIGN KEY(goal_id) REFERENCES goals(id)
            );

            CREATE TABLE IF NOT EXISTS tool_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool_name TEXT NOT NULL,
                params_json TEXT NOT NULL,
                success INTEGER NOT NULL,
                duration_ms REAL NOT NULL,
                timestamp REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS memory_items (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                category TEXT NOT NULL,
                updated_at REAL NOT NULL
            );
            """)
            logger.debug(f"Initialized MemoryDB schema at {self.db_path}")

    def record_goal(self, goal_id: str, prompt: str) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO goals (id, user_prompt, status, created_at) VALUES (?, ?, ?, ?)",
                (goal_id, prompt, "ACTIVE", time.time())
            )

    def update_goal_status(self, goal_id: str, status: str) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE goals SET status = ?, completed_at = ? WHERE id = ?",
                (status, time.time() if status in ("COMPLETED", "FAILED") else None, goal_id)
            )

    def record_task(self, task_id: str, goal_id: str, title: str, tool_name: Optional[str] = None) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO tasks (id, goal_id, title, tool_name, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (task_id, goal_id, title, tool_name, "PENDING", time.time())
            )

    def update_task(self, task_id: str, status: str, result: Optional[Any] = None, error: Optional[str] = None) -> None:
        result_json = json.dumps(result) if result is not None else None
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE tasks SET status = ?, result_json = ?, error = ? WHERE id = ?",
                (status, result_json, error, task_id)
            )

    def record_tool_audit(self, tool_name: str, params: Dict[str, Any], success: bool, duration_ms: float) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO tool_audit (tool_name, params_json, success, duration_ms, timestamp) VALUES (?, ?, ?, ?, ?)",
                (tool_name, json.dumps(params), 1 if success else 0, duration_ms, time.time())
            )

    def get_goal_tasks(self, goal_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM tasks WHERE goal_id = ? ORDER BY created_at ASC", (goal_id,))
            return [dict(row) for row in cursor.fetchall()]

    def set_memory_item(self, key: str, value: str, category: str = "general") -> None:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO memory_items (key, value, category, updated_at) VALUES (?, ?, ?, ?)",
                (key, value, category, time.time())
            )

    def get_memory_item(self, key: str) -> Optional[str]:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT value FROM memory_items WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row["value"] if row else None
