from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from typing import Any, cast

import pytest
from app.graph import graph as graph_module
from sqlalchemy.ext.asyncio import AsyncSession


def _settings(**overrides: object) -> SimpleNamespace:
    base: dict[str, object] = {
        "APP_ENV": "production",
        "LANGGRAPH_CHECKPOINT_URL": "postgresql://postgres:postgres@localhost:5432/sentinelflow",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _install_fake_postgres_saver(
    monkeypatch: pytest.MonkeyPatch,
    *,
    raise_error: Exception | None = None,
    return_value: object | None = None,
) -> None:
    module = ModuleType("langgraph.checkpoint.postgres.aio")

    class _FakeAsyncPostgresSaver:
        @classmethod
        def from_conn_string(cls, conn_string: str) -> object:
            _ = conn_string
            if raise_error is not None:
                raise raise_error
            return return_value if return_value is not None else object()

    module_any = cast(Any, module)
    module_any.AsyncPostgresSaver = _FakeAsyncPostgresSaver
    postgres_module = ModuleType("langgraph.checkpoint.postgres")
    postgres_module_any = cast(Any, postgres_module)
    postgres_module_any.aio = module

    monkeypatch.setitem(sys.modules, "langgraph.checkpoint.postgres", postgres_module)
    monkeypatch.setitem(sys.modules, "langgraph.checkpoint.postgres.aio", module)


def test_validate_production_checkpointer_rejects_missing_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        graph_module,
        "get_settings",
        lambda: _settings(LANGGRAPH_CHECKPOINT_URL=""),
    )

    with pytest.raises(RuntimeError, match="LANGGRAPH_CHECKPOINT_URL is required"):
        graph_module.validate_production_checkpointer()


def test_validate_production_checkpointer_rejects_invalid_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(graph_module, "get_settings", lambda: _settings())
    _install_fake_postgres_saver(monkeypatch, raise_error=ValueError("invalid"))

    with pytest.raises(RuntimeError, match="Invalid LANGGRAPH_CHECKPOINT_URL"):
        graph_module.validate_production_checkpointer()


def test_build_checkpointer_uses_postgres_saver_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = object()
    monkeypatch.setattr(graph_module, "get_settings", lambda: _settings())
    _install_fake_postgres_saver(monkeypatch, return_value=sentinel)

    checkpointer = graph_module._build_checkpointer()  # pyright: ignore[reportPrivateUsage]

    assert checkpointer is sentinel


def test_build_graph_passes_checkpointer_to_workflow_compile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = object()

    async def _node(state: dict[str, object]) -> dict[str, object]:
        return state

    class _FakeNodes:
        def __init__(self, **_kwargs: object) -> None:
            self.intake = _node
            self.investigate = _node
            self.collect = _node
            self.synthesize = _node
            self.approval = _node
            self.finalize = _node

    class _FakeStateGraph:
        def __init__(self, _state_type: object) -> None:
            self._state_type = _state_type

        def add_node(self, *_args: object, **_kwargs: object) -> None:
            return None

        def add_edge(self, *_args: object, **_kwargs: object) -> None:
            return None

        def add_conditional_edges(self, *_args: object, **_kwargs: object) -> None:
            return None

        def compile(self, *, checkpointer: object) -> dict[str, object]:
            return {"checkpointer": checkpointer}

    def _fake_settings() -> object:
        return SimpleNamespace()

    def _fake_model_gateway(_settings: object) -> object:
        return object()

    def _fake_investigator_agent(_gateway: object) -> object:
        return object()

    def _fake_synthesizer_agent(_gateway: object) -> object:
        return object()

    monkeypatch.setattr(graph_module, "_build_checkpointer", lambda: sentinel)
    monkeypatch.setattr(graph_module, "get_settings", _fake_settings)
    monkeypatch.setattr(graph_module, "ModelGateway", _fake_model_gateway)
    monkeypatch.setattr(graph_module, "InvestigatorAgent", _fake_investigator_agent)
    monkeypatch.setattr(graph_module, "SynthesizerAgent", _fake_synthesizer_agent)
    monkeypatch.setattr(graph_module, "InvestigationNodes", _FakeNodes)
    monkeypatch.setattr(graph_module, "StateGraph", _FakeStateGraph)

    compiled = graph_module.build_graph(cast(AsyncSession, SimpleNamespace()))

    assert compiled == {"checkpointer": sentinel}
