from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Request, Response
from fastapi.responses import PlainTextResponse

router = APIRouter(tags=["discovery", "ai-first"])

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@lru_cache
def _load_static_file(name: str) -> str:
    path = _STATIC_DIR / name
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    return ""


@router.get("/robots.txt", response_class=PlainTextResponse)
def get_robots_txt() -> PlainTextResponse:
    """Return decoupled robots.txt separating training scrapers from search/citation crawlers."""
    content = _load_static_file("robots.txt")
    return PlainTextResponse(content, media_type="text/plain; charset=utf-8")


@router.get("/llms.txt", response_class=PlainTextResponse)
def get_llms_txt() -> PlainTextResponse:
    """Return standard llms.txt curated manifest for AI agents and LLMs."""
    content = _load_static_file("llms.txt")
    return PlainTextResponse(content, media_type="text/markdown; charset=utf-8")


@router.get("/llms-full.txt", response_class=PlainTextResponse)
def get_llms_full_txt() -> PlainTextResponse:
    """Return full concatenated markdown technical reference for 1-turn context loading."""
    content = _load_static_file("llms-full.txt")
    return PlainTextResponse(content, media_type="text/markdown; charset=utf-8")


@router.get("/", response_class=Response)
def root_content_negotiation(request: Request) -> Response:
    """Root endpoint supporting HTTP Content Negotiation (Accept: text/markdown vs json)."""
    accept = request.headers.get("accept", "")
    if "text/markdown" in accept:
        content = _load_static_file("llms.txt")
        return Response(
            content=content,
            media_type="text/markdown; charset=utf-8",
            headers={"Vary": "Accept"},
        )
    fallback_json = (
        '{"name":"SentinelFlow & SentinelPulse API","version":"0.1.0",'
        '"docs":"/docs","llms":"/llms.txt"}'
    )
    return Response(
        content=fallback_json,
        media_type="application/json",
        headers={"Vary": "Accept"},
    )
