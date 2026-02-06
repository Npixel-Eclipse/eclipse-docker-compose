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

    def __init__(self, conn: sqlite3.Connection):
        super().__init__()
        self.conn = conn
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
            return CheckpointTuple(
                config,
                pickle.loads(row[0]),
                pickle.loads(row[1]) if row[1] else {},
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
