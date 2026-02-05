"""Global context singleton for shared client instances.

Decouples tools from the main application lifecycle to prevent circular dependencies.
"""

from typing import Optional
from .slack_client import SlackIntegration
from .perforce_client import PerforceClient


import contextvars
from dataclasses import dataclass

@dataclass
class RequestContext:
    channel: str
    thread_ts: str
    user_id: Optional[str] = None
    team_id: Optional[str] = None

# ContextVar for request-scoped data
_request_context = contextvars.ContextVar("request_context", default=None)

class AppContext:
    """Singleton context holding global state/clients."""
    _instance: Optional['AppContext'] = None
    
    def __init__(self):
        self.slack: Optional[SlackIntegration] = None
        self.p4: Optional[PerforceClient] = None

    @classmethod
    def get_instance(cls) -> 'AppContext':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @property
    def current_request(self) -> Optional[RequestContext]:
        return _request_context.get()

    def set_request_context(self, channel: str, thread_ts: str, user_id: str = None, team_id: str = None):
        _request_context.set(RequestContext(channel, thread_ts, user_id, team_id))


def get_context() -> AppContext:
    """Helper to get the global app context."""
    return AppContext.get_instance()
