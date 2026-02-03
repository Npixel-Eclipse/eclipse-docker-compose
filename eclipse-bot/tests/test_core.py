"""Unit tests for core modules."""

import pytest
from typing import TypedDict
from langgraph.graph import END

from src.core.workflow_engine import WorkflowEngine


class TestState(TypedDict, total=False):
    input: str
    output: str


def test_workflow_engine_sync():
    """Test synchronous workflow execution."""
    engine = WorkflowEngine()

    @engine.node("process")
    def process(state: TestState) -> TestState:
        return {"output": state["input"].upper()}

    engine.set_entry_point("process")
    engine.add_edge("process", END)
    engine.compile(TestState)

    result = engine.run_sync({"input": "hello"})

    assert result.success
    assert result.final_state["output"] == "HELLO"


@pytest.mark.asyncio
async def test_workflow_engine_async():
    """Test asynchronous workflow execution."""
    engine = WorkflowEngine()

    @engine.node("process")
    async def process(state: TestState) -> TestState:
        return {"output": state["input"].lower()}

    engine.set_entry_point("process")
    engine.add_edge("process", END)
    engine.compile(TestState)

    result = await engine.run({"input": "HELLO"})

    assert result.success
    assert result.final_state["output"] == "hello"
