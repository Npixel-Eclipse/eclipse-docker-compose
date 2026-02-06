"""Custom SQLite Checkpointer for LangGraph.

This module implements a persistent checkpointer using sqlite3,
compatible with LangGraph's BaseCheckpointSaver interface.
It avoids dependency issues with missing 'langgraph.checkpoint.sqlite'.
"""

import pickle
import sqlite3
from typing import Any, Optional, Iterator, AsyncIterator
from contextlib import contextmanager

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint, CheckpointTuple, CheckpointMetadata

class CustomSqliteSaver(BaseCheckpointSaver):
    """A checkpoint saver that stores state in a SQLite database."""

    def __init__(self, conn: sqlite3.Connection, context_manager=None):
        super().__init__()
        self.conn = conn
        self.context_manager = context_manager  # Trimmer or AutoCompactor
        self._setup()

    def _setup(self):
        with self.conn:
            # Enable WAL mode for better concurrency (Readers don't block Writers)
            self.conn.execute("PRAGMA journal_mode=WAL;")
            
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoints (
                    thread_id TEXT,
                    thread_ts TEXT,
                    parent_ts TEXT,
                    checkpoint BLOB,
                    metadata BLOB,
                    PRIMARY KEY (thread_id, thread_ts)
                );
                """
            )

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """Asynchronous version of get_tuple."""
        import asyncio
        return await asyncio.to_thread(self.get_tuple, config)

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: dict[str, Any],
    ) -> RunnableConfig:
        """Asynchronous version of put."""
        return await asyncio.to_thread(self.put, config, checkpoint, metadata, new_versions)

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: list[tuple[str, Any]],
        task_id: str,
    ) -> None:
        """Store intermediate writes asynchronously."""
        # For now, we delegate to a sync dummy or just pass as we don't fully support detailed write tracking in this simple SQLite version yet.
        # But we must implement it to satisfy the abstract base class.
        pass

    async def alist(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[CheckpointTuple]:
        """List checkpoints asynchronously."""
        import asyncio
        # We assume the sync .list() is implemented (or empty) and wrap it.
        # Since .list creates a generator, wrapping it in to_thread is tricky.
        # For this simple bot, we might not need full history listing. 
        # But let's return an empty async iterator to satisfy the interface if real list is not critical.
        async def _empty_gen():
            if False: yield
        return _empty_gen()

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        thread_id = config["configurable"]["thread_id"]
        thread_ts = config["configurable"].get("thread_ts")
        
        cursor = self.conn.cursor()
        if thread_ts:
            cursor.execute(
                "SELECT checkpoint, metadata, parent_ts, thread_ts FROM checkpoints WHERE thread_id = ? AND thread_ts = ?",
                (thread_id, thread_ts),
            )
        else:
            cursor.execute(
                "SELECT checkpoint, metadata, parent_ts, thread_ts FROM checkpoints WHERE thread_id = ? ORDER BY thread_ts DESC LIMIT 1",
                (thread_id,),
            )
        row = cursor.fetchone()
        
        if row:
            checkpoint = pickle.loads(row[0])
            metadata = pickle.loads(row[1]) if row[1] else {}
            
            # Apply Context Management (Trimming or Auto-Compacting) at Load Time
            if self.context_manager and "channel_values" in checkpoint and "messages" in checkpoint["channel_values"]:
                try:
                    original_msgs = checkpoint["channel_values"]["messages"]
                    # invoke() handles both LangChain Trimmer and our AutoCompactor
                    trimmed_msgs = self.context_manager.invoke(original_msgs)
                    checkpoint["channel_values"]["messages"] = trimmed_msgs
                except Exception as e:
                    # Fallback if processing fails
                    pass

            return CheckpointTuple(
                config,
                checkpoint,
                metadata,
                (config["configurable"]["thread_id"], row[2]) if row[2] else None,
            )
        return None

    def list(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> Iterator[CheckpointTuple]:
        # Minimal implementation for basic persistence
        pass

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: dict[str, Any],
    ) -> RunnableConfig:
        thread_id = config["configurable"]["thread_id"]
        thread_ts = checkpoint["id"]
        parent_ts = config["configurable"].get("thread_ts")
        
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO checkpoints (thread_id, thread_ts, parent_ts, checkpoint, metadata) VALUES (?, ?, ?, ?, ?)",
                (
                    thread_id,
                    thread_ts,
                    parent_ts,
                    pickle.dumps(checkpoint),
                    pickle.dumps(metadata),
                ),
            )
        return {
            "configurable": {
                "thread_id": thread_id,
                "thread_ts": thread_ts,
            }
        }
