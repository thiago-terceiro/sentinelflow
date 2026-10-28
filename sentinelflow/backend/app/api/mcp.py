from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any, cast
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DBSessionDep
from app.api.telecom import TelecomClassifyRequest, classify_telecom_message
from app.db.models import DisputeRecord, InvestigationRecord
from app.services.investigations import schedule_resume, to_run

router = APIRouter(tags=["mcp", "protocols"])

MCP_TOOLS_SPEC: list[dict[str, Any]] = [
    {
        "name": "list_disputes",
        "description": "List disputes with their status, code, title, amount, and timestamp.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of disputes to return",
                    "default": 10,
                }
            },
        },
    },
    {
        "name": "get_investigation",
        "description": "Get latest investigation run, hypotheses, evidence, and risk assessment.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dispute_id": {
                    "type": "string",
                    "description": "The dispute ID (e.g. SF-10001)",
                }
            },
            "required": ["dispute_id"],
        },
    },
    {
        "name": "submit_review",
        "description": "Submit a human review decision (approve, reject, or request_revision).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dispute_id": {"type": "string", "description": "The dispute ID"},
                "investigation_id": {
                    "type": "string",
                    "description": "The active investigation ID",
                },
                "decision": {
                    "type": "string",
                    "enum": ["approve", "reject", "request_revision"],
                    "description": "Review decision",
                },
                "guidance": {
                    "type": "string",
                    "description": "Optional steering instructions for revision",
                },
            },
            "required": ["dispute_id", "investigation_id", "decision"],
        },
    },
    {
        "name": "classify_telecom",
        "description": "Classify an incoming SMS for fraud and pumping attacks via ONNX model.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sender_phone": {
                    "type": "string",
                    "description": "Sender phone number in E.164 format",
                },
                "message_body": {"type": "string", "description": "SMS text content"},
                "client_ip": {"type": "string", "description": "Optional client IP address"},
            },
            "required": ["sender_phone", "message_body"],
        },
    },
]

MCP_WELL_KNOWN_MANIFEST: dict[str, Any] = {
    "name": "sentinelflow-mcp",
    "version": "1.0.0",
    "protocolVersion": "2024-11-05",
    "description": (
        "Remote MCP server for SentinelFlow dispute investigation "
        "and SentinelPulse telecom intelligence"
    ),
    "transports": [{"type": "sse", "url": "/api/v1/mcp/sse"}],
    "capabilities": {
        "tools": {
            t["name"]: {"description": t["description"], "parameters": t["inputSchema"]}
            for t in MCP_TOOLS_SPEC
        }
    },
}

_mcp_sessions: dict[str, asyncio.Queue[str]] = {}


@router.get("/.well-known/mcp.json")
def get_mcp_discovery_manifest() -> JSONResponse:
    """Return public MCP server discovery manifest (2024-11-05 standard)."""
    return JSONResponse(MCP_WELL_KNOWN_MANIFEST)


@router.get("/mcp/sse")
async def mcp_sse_transport(request: Request) -> StreamingResponse:
    """Server-Sent Events endpoint establishing an interactive MCP remote session."""
    session_id = uuid4().hex
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=100)
    _mcp_sessions[session_id] = queue

    async def event_generator() -> AsyncGenerator[str, None]:
        # Initial MCP endpoint event instructing the agent where to send JSON-RPC messages
        endpoint_url = f"/api/v1/mcp/messages?session_id={session_id}"
        yield f"event: endpoint\ndata: {endpoint_url}\n\n"
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"event: message\ndata: {data}\n\n"
                except TimeoutError:
                    # Keepalive SSE ping
                    yield ": ping\n\n"
        finally:
            _mcp_sessions.pop(session_id, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _execute_mcp_tool(
    name: str,
    args: dict[str, Any],
    session: AsyncSession,
) -> Any:
    """Execute local SentinelFlow & SentinelPulse capabilities for MCP tool call."""
    if name == "list_disputes":
        limit = int(args.get("limit", 10))
        result = await session.execute(
            select(DisputeRecord).order_by(DisputeRecord.created_at.desc()).limit(limit)
        )
        records = result.scalars().all()
        return [
            {
                "id": r.id,
                "case_code": r.case_code,
                "title": r.title,
                "amount": float(r.amount),
                "currency": r.currency,
                "status": r.status,
                "created_at": r.created_at.isoformat(),
            }
            for r in records
        ]

    if name == "get_investigation":
        dispute_id = str(args.get("dispute_id", "")).strip()
        result = await session.execute(
            select(InvestigationRecord)
            .where(InvestigationRecord.dispute_id == dispute_id)
            .order_by(InvestigationRecord.created_at.desc())
            .limit(1)
        )
        record = cast(InvestigationRecord | None, result.scalar_one_or_none())
        if not record:
            return {"error": f"No investigation found for dispute {dispute_id}"}
        run = to_run(record)
        return run.model_dump(mode="json")

    if name == "submit_review":
        investigation_id = str(args.get("investigation_id", "")).strip()
        decision = str(args.get("decision", "")).strip()
        guidance = args.get("guidance")
        decision_payload = {
            "decision": decision,
            "guidance": str(guidance) if guidance else None,
        }
        scheduled = await schedule_resume(investigation_id, decision_payload)
        return {"status": "review_submitted", "scheduled": scheduled, "decision": decision}

    if name == "classify_telecom":
        sender = str(args.get("sender", args.get("sender_phone", "+12025550199"))).strip()
        recipient = str(args.get("recipient", "+12025550100")).strip()
        message = str(args.get("message", args.get("message_body", ""))).strip()
        ip = args.get("ip", args.get("client_ip"))
        carrier = args.get("carrier")
        req = TelecomClassifyRequest(
            sender=sender,
            recipient=recipient,
            message=message,
            ip=str(ip) if ip else None,
            carrier=str(carrier) if carrier else None,
        )
        verdict = await classify_telecom_message(req, BackgroundTasks())
        return verdict.model_dump(mode="json")

    raise ValueError(f"Unknown MCP tool: {name}")


@router.post("/mcp/messages")
async def mcp_messages_transport(
    request: Request,
    session: DBSessionDep,
    session_id: str = Query(default=""),
) -> JSONResponse:
    """Handle incoming JSON-RPC 2.0 messages from agents over MCP protocol."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}},
            status_code=400,
        )

    msg_id = body.get("id")
    method = body.get("method")
    params = body.get("params") or {}

    if method == "initialize":
        response_payload = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "sentinelflow-mcp", "version": "1.0.0"},
            },
        }
        return JSONResponse(response_payload)

    if method == "tools/list":
        response_payload = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"tools": MCP_TOOLS_SPEC},
        }
        return JSONResponse(response_payload)

    if method == "tools/call":
        tool_name = str(params.get("name", ""))
        tool_args = params.get("arguments") or {}
        try:
            result_data = await _execute_mcp_tool(tool_name, tool_args, session)
            response_payload = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result_data, default=str),
                        }
                    ]
                },
            }
            return JSONResponse(response_payload)
        except Exception as exc:
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32000, "message": str(exc)},
                }
            )

    if method == "ping":
        return JSONResponse({"jsonrpc": "2.0", "id": msg_id, "result": {}})

    return JSONResponse(
        {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }
    )
