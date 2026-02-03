"""LangGraph-based workflow engine."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar, Generic, Optional
from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)

StateType = TypeVar("StateType")


@dataclass
class WorkflowResult:
    """Result of a workflow execution."""

    success: bool
    final_state: dict
    error: Optional[str] = None


class WorkflowEngine(Generic[StateType]):
    """LangGraph-based workflow engine for building AI workflows.

    Example usage:
        from typing import TypedDict

        class MyState(TypedDict):
            input: str
            output: str

        engine = WorkflowEngine[MyState]()

        @engine.node("process")
        async def process(state: MyState) -> MyState:
            return {"output": state["input"].upper()}

        engine.set_entry_point("process")
        engine.add_edge("process", END)

        result = await engine.run({"input": "hello"})
    """

    def __init__(self):
        self._nodes: dict[str, Callable] = {}
        self._edges: list[tuple[str, str]] = []
        self._conditional_edges: list[tuple[str, Callable, dict]] = []
        self._entry_point: Optional[str] = None
        self._graph: Optional[StateGraph] = None
        self._compiled = None

    def node(self, name: str):
        """Decorator to register a workflow node.

        Args:
            name: Unique node identifier

        Example:
            @engine.node("my_node")
            async def my_node(state):
                return {"result": "done"}
        """

        def decorator(func: Callable):
            self._nodes[name] = func
            return func

        return decorator

    def add_node(self, name: str, func: Callable):
        """Programmatically add a node.

        Args:
            name: Unique node identifier
            func: Node function
        """
        self._nodes[name] = func

    def add_edge(self, from_node: str, to_node: str):
        """Add an edge between nodes.

        Args:
            from_node: Source node name
            to_node: Target node name (use END for terminal)
        """
        self._edges.append((from_node, to_node))

    def add_conditional_edge(
        self,
        from_node: str,
        condition: Callable,
        mapping: dict[str, str],
    ):
        """Add a conditional edge.

        Args:
            from_node: Source node name
            condition: Function that returns a key from mapping
            mapping: Dict mapping condition results to node names
        """
        self._conditional_edges.append((from_node, condition, mapping))

    def set_entry_point(self, node_name: str):
        """Set the workflow entry point.

        Args:
            node_name: Name of the first node to execute
        """
        self._entry_point = node_name

    def compile(self, state_schema: type):
        """Compile the workflow graph.

        Args:
            state_schema: TypedDict or dataclass defining state schema
        """
        self._graph = StateGraph(state_schema)

        # Add all nodes
        for name, func in self._nodes.items():
            self._graph.add_node(name, func)

        # Set entry point
        if self._entry_point:
            self._graph.set_entry_point(self._entry_point)

        # Add edges
        for from_node, to_node in self._edges:
            if to_node == END:
                self._graph.add_edge(from_node, END)
            else:
                self._graph.add_edge(from_node, to_node)

        # Add conditional edges
        for from_node, condition, mapping in self._conditional_edges:
            self._graph.add_conditional_edges(from_node, condition, mapping)

        self._compiled = self._graph.compile()
        logger.info(f"Workflow compiled with {len(self._nodes)} nodes")

    async def run(self, initial_state: dict) -> WorkflowResult:
        """Execute the workflow.

        Args:
            initial_state: Initial state dictionary

        Returns:
            WorkflowResult with final state
        """
        if not self._compiled:
            raise RuntimeError("Workflow not compiled. Call compile() first.")

        try:
            result = await self._compiled.ainvoke(initial_state)
            return WorkflowResult(success=True, final_state=result)
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            return WorkflowResult(
                success=False,
                final_state=initial_state,
                error=str(e),
            )

    def run_sync(self, initial_state: dict) -> WorkflowResult:
        """Execute the workflow synchronously.

        Args:
            initial_state: Initial state dictionary

        Returns:
            WorkflowResult with final state
        """
        if not self._compiled:
            raise RuntimeError("Workflow not compiled. Call compile() first.")

        try:
            result = self._compiled.invoke(initial_state)
            return WorkflowResult(success=True, final_state=result)
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            return WorkflowResult(
                success=False,
                final_state=initial_state,
                error=str(e),
            )
