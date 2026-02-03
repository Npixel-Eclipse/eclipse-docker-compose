"""Simple chat workflow example using LangGraph.

This example demonstrates:
1. Defining a custom state schema
2. Creating nodes that process state
3. Integrating with LLM for responses
4. Building and running a workflow
"""

from typing import TypedDict, Optional, Any
from langgraph.graph import END

from ..base import BaseWorkflow
from ...core.llm_client import LLMClient, Message


class ChatState(TypedDict, total=False):
    """State schema for simple chat workflow."""

    # Input
    user_message: str
    system_prompt: str

    # Processing
    messages: list[dict[str, str]]

    # Output
    assistant_response: str
    error: Optional[str]

    # Metadata
    model: str
    usage: dict[str, Any]


class SimpleChatWorkflow(BaseWorkflow):
    """A simple chat workflow that processes user messages with LLM.

    Usage:
        llm = LLMClient(api_key="...", default_model="google/gemini-3-flash-preview")
        workflow = SimpleChatWorkflow(llm)

        result = await workflow.run({
            "user_message": "안녕하세요!",
            "system_prompt": "You are a helpful assistant.",
        })

        print(result.final_state["assistant_response"])
    """

    name = "simple_chat"

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        super().__init__()

    def build(self):
        """Build the chat workflow graph."""

        @self.engine.node("prepare_messages")
        async def prepare_messages(state: ChatState) -> ChatState:
            """Prepare message list for LLM."""
            messages = []

            # Add system prompt if provided
            system = state.get("system_prompt", "You are a helpful assistant.")
            messages.append({"role": "system", "content": system})

            # Add user message
            messages.append({"role": "user", "content": state["user_message"]})

            return {"messages": messages}

        @self.engine.node("call_llm")
        async def call_llm(state: ChatState) -> ChatState:
            """Call LLM with prepared messages."""
            try:
                messages = [
                    Message(role=m["role"], content=m["content"])
                    for m in state["messages"]
                ]

                response = await self.llm.chat(messages)

                return {
                    "assistant_response": response.content,
                    "model": response.model,
                    "usage": response.usage,
                }
            except Exception as e:
                return {"error": str(e)}

        @self.engine.node("handle_error")
        async def handle_error(state: ChatState) -> ChatState:
            """Handle any errors that occurred."""
            return {"assistant_response": f"죄송합니다, 오류가 발생했습니다: {state.get('error')}"}

        # Define workflow structure
        self.engine.set_entry_point("prepare_messages")
        self.engine.add_edge("prepare_messages", "call_llm")

        # Conditional routing based on error
        def route_after_llm(state: ChatState) -> str:
            if state.get("error"):
                return "handle_error"
            return END

        self.engine.add_conditional_edge(
            "call_llm",
            route_after_llm,
            {"handle_error": "handle_error", END: END},
        )
        self.engine.add_edge("handle_error", END)

    def get_state_schema(self) -> type:
        """Return ChatState schema."""
        return ChatState
