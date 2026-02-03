"""PostgreSQL-based conversation memory store.

Provides persistent storage for conversation history that survives restarts
and can store conversations indefinitely.
"""

import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import Column, String, Text, DateTime, Integer, select, text, JSON
from sqlalchemy.orm import declarative_base

from ..models import Message

logger = logging.getLogger(__name__)

Base = declarative_base()


class ConversationMessage(Base):
    """SQLAlchemy model for conversation messages."""
    
    __tablename__ = "conversation_messages"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    # Slack 식별자
    channel_id = Column(String(50), nullable=False, index=True)
    thread_ts = Column(String(50), nullable=True, index=True)  # None for main channel
    user_id = Column(String(50), nullable=False)
    
    # 메시지 내용
    role = Column(String(20), nullable=False)  # user, assistant, system, tool
    content = Column(Text, nullable=True)
    tool_calls = Column(JSON, nullable=True)
    tool_call_id = Column(String(100), nullable=True)
    
    # 메타데이터
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class ConversationStore:
    """PostgreSQL-based persistent conversation storage.
    
    Usage:
        store = ConversationStore(database_url)
        await store.initialize()
        
        # Add message
        await store.add_message(
            channel_id="C123",
            thread_ts="1234567890.123456",
            user_id="U123",
            role="user",
            content="Hello!"
        )
        
        # Get conversation history
        messages = await store.get_conversation(
            channel_id="C123",
            thread_ts="1234567890.123456",
            limit=20
        )
    """
    
    def __init__(self, database_url: str):
        """Initialize the conversation store.
        
        Args:
            database_url: PostgreSQL connection URL
                Example: postgresql+asyncpg://user:pass@host:5432/dbname
        """
        self.database_url = database_url
        self.engine = create_async_engine(database_url, echo=False)
        self.async_session = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
    
    async def initialize(self):
        """Create tables if they don't exist."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Conversation store initialized")
    
    async def add_message(
        self,
        channel_id: str,
        role: str,
        content: Optional[str] = None,
        user_id: str = "system",
        thread_ts: Optional[str] = None,
        tool_calls: Optional[list] = None,
        tool_call_id: Optional[str] = None,
    ) -> int:
        """Add a message to the conversation.
        
        Args:
            channel_id: Slack channel ID
            role: Message role (user, assistant, system, tool)
            content: Message text
            user_id: Slack user ID
            thread_ts: Thread timestamp (None for main channel)
            tool_calls: Tool calls from assistant
            tool_call_id: Tool call ID for tool role
            
        Returns:
            Message ID
        """
        async with self.async_session() as session:
            message = ConversationMessage(
                channel_id=channel_id,
                thread_ts=thread_ts,
                user_id=user_id,
                role=role,
                content=content,
                tool_calls=tool_calls,
                tool_call_id=tool_call_id,
            )
            session.add(message)
            await session.commit()
            return message.id
    
    async def get_conversation(
        self,
        channel_id: str,
        thread_ts: Optional[str] = None,
        limit: int = 20,
    ) -> list[Message]:
        """Get conversation history.
        
        Args:
            channel_id: Slack channel ID
            thread_ts: Thread timestamp (None for main channel)
            limit: Maximum number of messages to return
            
        Returns:
            List of Message objects, oldest first
        """
        async with self.async_session() as session:
            # Build query
            if thread_ts:
                query = select(ConversationMessage).where(
                    ConversationMessage.channel_id == channel_id,
                    ConversationMessage.thread_ts == thread_ts,
                )
            else:
                query = select(ConversationMessage).where(
                    ConversationMessage.channel_id == channel_id,
                    ConversationMessage.thread_ts.is_(None),
                )
            
            # Order by created_at desc, then take last N
            query = query.order_by(ConversationMessage.created_at.desc()).limit(limit)
            
            result = await session.execute(query)
            rows = result.scalars().all()
            
            # Reverse to get oldest first
            messages = [
                Message(
                    role=row.role,
                    content=row.content,
                    user_id=row.user_id,
                    created_at=row.created_at,
                    tool_calls=row.tool_calls,
                    tool_call_id=row.tool_call_id,
                )
                for row in reversed(rows)
            ]
            
            return messages
    
    async def clear_conversation(
        self,
        channel_id: str,
        thread_ts: Optional[str] = None,
    ):
        """Clear conversation history.
        
        Args:
            channel_id: Slack channel ID
            thread_ts: Thread timestamp (None for main channel)
        """
        async with self.async_session() as session:
            if thread_ts:
                await session.execute(
                    text(
                        "DELETE FROM conversation_messages "
                        "WHERE channel_id = :channel_id AND thread_ts = :thread_ts"
                    ),
                    {"channel_id": channel_id, "thread_ts": thread_ts},
                )
            else:
                await session.execute(
                    text(
                        "DELETE FROM conversation_messages "
                        "WHERE channel_id = :channel_id AND thread_ts IS NULL"
                    ),
                    {"channel_id": channel_id},
                )
            await session.commit()
    
    async def close(self):
        """Close database connection."""
        await self.engine.dispose()
