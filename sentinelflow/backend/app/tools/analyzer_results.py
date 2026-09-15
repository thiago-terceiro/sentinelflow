from __future__ import annotations

from app.agents.analyzers import summarize_analyzer
from app.schemas.investigation import AnalyzerSummary, Evidence


async def run_analyzer(name: str, evidence: list[Evidence]) -> AnalyzerSummary:
    return summarize_analyzer(name, evidence)
