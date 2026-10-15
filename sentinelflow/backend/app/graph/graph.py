from __future__ import annotations

from functools import lru_cache
from importlib import import_module
from typing import Any, cast

from app.agents.investigator import InvestigatorAgent
from app.agents.synthesizer import SynthesizerAgent
from app.config import get_settings
from app.graph.nodes import InvestigationNodes
from app.graph.routing import (
    route_after_approval,
    route_after_investigator,
    route_after_recommendation,
)
from app.graph.state import DisputeState
from app.services.model_gateway import ModelGateway
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy.ext.asyncio import AsyncSession

# LangGraph currently ships without complete type stubs for graph primitives.
_langgraph_graph: Any = import_module("langgraph.graph")
END: str = cast(str, _langgraph_graph.END)
START: str = cast(str, _langgraph_graph.START)
StateGraph: Any = _langgraph_graph.StateGraph


@lru_cache(maxsize=1)
def _memory_checkpointer() -> MemorySaver:
    return MemorySaver()


def validate_production_checkpointer() -> None:
    settings = get_settings()
    if settings.APP_ENV != "production":
        return
    if not settings.LANGGRAPH_CHECKPOINT_URL:
        raise RuntimeError("LANGGRAPH_CHECKPOINT_URL is required in production.")
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Install langgraph-checkpoint-postgres and psycopg[binary] "
            "for production checkpointer support."
        ) from exc
    try:
        AsyncPostgresSaver.from_conn_string(settings.LANGGRAPH_CHECKPOINT_URL)
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("Invalid LANGGRAPH_CHECKPOINT_URL for production checkpointer.") from exc


def _build_checkpointer() -> Any:
    settings = get_settings()
    if settings.APP_ENV == "production":
        validate_production_checkpointer()
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Install langgraph-checkpoint-postgres and psycopg[binary] "
                "for production checkpointer support."
            ) from exc
        return AsyncPostgresSaver.from_conn_string(settings.LANGGRAPH_CHECKPOINT_URL)
    return _memory_checkpointer()


def build_graph(session: AsyncSession) -> Any:
    gateway = ModelGateway(get_settings())
    nodes = InvestigationNodes(
        session=session,
        investigator=InvestigatorAgent(gateway),
        synthesizer=SynthesizerAgent(gateway),
    )
    workflow: Any = StateGraph(DisputeState)
    workflow.add_node("intake", nodes.intake)
    workflow.add_node("investigate", nodes.investigate)
    workflow.add_node("collect", nodes.collect)
    workflow.add_node("synthesize", nodes.synthesize)
    workflow.add_node("approval", nodes.approval)
    workflow.add_node("finalize", nodes.finalize)
    workflow.add_edge(START, "intake")
    workflow.add_edge("intake", "investigate")
    workflow.add_conditional_edges(
        "investigate",
        route_after_investigator,
        {
            "collect": "collect",
            "synthesize": "synthesize",
        },
    )
    workflow.add_edge("collect", "investigate")
    workflow.add_conditional_edges(
        "synthesize",
        route_after_recommendation,
        {
            "approval": "approval",
            "finalize": "finalize",
        },
    )
    workflow.add_conditional_edges(
        "approval",
        route_after_approval,
        {
            "investigate": "investigate",
            "finalize": "finalize",
        },
    )
    workflow.add_edge("finalize", END)
    return workflow.compile(checkpointer=_build_checkpointer())
