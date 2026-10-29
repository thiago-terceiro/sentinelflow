from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

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


@router.get("/sitemap.xml", response_class=Response)
def get_sitemap_xml() -> Response:
    """Return XML sitemap for search crawlers and AI search engine indexing."""
    content = _load_static_file("sitemap.xml")
    return Response(content=content, media_type="application/xml; charset=utf-8")


@router.get("/api/v1/geo/metadata")
def get_geo_metadata() -> dict[str, Any]:
    """Return Generative Engine Optimization (GEO) structured metadata and entity anchors."""
    return {
        "system": "SentinelFlow & SentinelPulse",
        "version": "0.1.0",
        "definition_leads": {
            "sentinelflow": (
                "SentinelFlow is an enterprise autonomous AI dispute investigation copilot built "
                "on LangGraph that orchestrates multi-agent evidence collection, deterministic "
                "risk evaluation, and human-in-the-loop steering."
            ),
            "sentinelpulse": (
                "SentinelPulse is a high-throughput, synchronous telecom trust-and-safety gateway "
                "delivering sub-15ms SMS and voice fraud classification using quantized ONNX "
                "Runtime CPU models and Redis sliding-window velocity aggregators."
            ),
            "cryptographic_audit": (
                "SentinelFlow's audit ledger is an append-only sequence of immutable records "
                "linked by SHA-256 cryptographic hashes ensuring tamper-evident non-repudiation."
            ),
        },
        "entity_anchors": [
            {
                "id": "https://sentinelflow.dev/#software",
                "type": "SoftwareApplication",
                "name": "SentinelFlow & SentinelPulse",
                "applicationCategory": "SecurityApplication",
            },
            {
                "id": "https://sentinelflow.dev/#organization",
                "type": "Organization",
                "name": "SentinelFlow Open Source Initiative",
                "url": "https://sentinelflow.dev",
            },
            {
                "id": "https://sentinelflow.dev/#faq",
                "type": "FAQPage",
                "name": "SentinelFlow Core FAQ",
            },
            {
                "id": "https://sentinelflow.dev/#howto-investigation",
                "type": "HowTo",
                "name": "How to Investigate a Transaction Dispute with SentinelFlow",
            },
            {
                "id": "https://sentinelflow.dev/#website",
                "type": "WebSite",
                "name": "SentinelFlow",
                "url": "https://sentinelflow.dev",
            },
        ],
        "comparison_matrices": [
            {
                "name": "System Capability Comparison",
                "dimensions": 8,
                "entities": [
                    "Legacy Rules Engine (2020)",
                    "SentinelFlow Dispute Copilot",
                    "SentinelPulse Telecom Gateway",
                ],
            },
            {
                "name": "AI-First Protocols & Ingestion",
                "dimensions": 7,
                "protocols": [
                    "mcp.json",
                    "llms.txt",
                    "llms-full.txt",
                    "content_negotiation",
                    "robots.txt",
                    "schema_json_ld",
                    "mcp_sse",
                ],
            },
        ],
        "manifests": {
            "llms_txt": "/llms.txt",
            "llms_full_txt": "/llms-full.txt",
            "mcp_discovery": "/.well-known/mcp.json",
            "robots_txt": "/robots.txt",
            "sitemap_xml": "/sitemap.xml",
        },
        "observability": {
            "primary_reference_tracking": (
                "Measure brand and feature citation frequency across synthetic search responses "
                "(ChatGPT Search, Perplexity, Gemini)."
            ),
            "high_citation_pillars": [
                "Definition Lead Pattern",
                "Comparison Matrix Tables",
                "Stacked Schema.org JSON-LD",
                "Primary Reference Rate Tracking",
            ],
        },
    }


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
