"""
llm/cache.py — Disk-based LLM response cache backed by the llm_cache SQLite table.
The input_hash is: sha256(model + prompt).hexdigest()
"""
import aiosqlite
from pathlib import Path


class LLMCache:
    def __init__(self, db_path: str = "./browser_agent.db"):
        self.db_path = db_path

    def set_db_path(self, db_path: str):
        self.db_path = db_path

    async def get(self, input_hash: str) -> str | None:
        """Retrieve cached LLM response by input hash."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT response FROM llm_cache WHERE input_hash = ?",
                    (input_hash,)
                ) as cursor:
                    row = await cursor.fetchone()
            return row["response"] if row else None
        except Exception:
            return None

    async def set(self, input_hash: str, response: str, model: str) -> None:
        """Cache an LLM response."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """INSERT OR REPLACE INTO llm_cache
                       (input_hash, response, model)
                       VALUES (?, ?, ?)""",
                    (input_hash, response, model)
                )
                await db.commit()
        except Exception:
            pass  # Cache failures are non-fatal
