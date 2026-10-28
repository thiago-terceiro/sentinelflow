from __future__ import annotations

import pytest
from app.main import app
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_llms_txt_and_full_txt_endpoints() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Test /llms.txt
        res = await client.get("/llms.txt")
        assert res.status_code == 200
        assert "text/markdown" in res.headers.get("content-type", "")
        assert "# SentinelFlow & SentinelPulse" in res.text
        assert "/docs/architecture.md" in res.text

        # 2. Test /llms-full.txt
        res_full = await client.get("/llms-full.txt")
        assert res_full.status_code == 200
        assert "text/markdown" in res_full.headers.get("content-type", "")
        assert "Full Technical Knowledge Base" in res_full.text
        assert "Dispute Investigation Lifecycle" in res_full.text


@pytest.mark.asyncio
async def test_decoupled_robots_txt() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.get("/robots.txt")
        assert res.status_code == 200
        assert "text/plain" in res.headers.get("content-type", "")
        text = res.text
        # Training bots are blocked
        assert "User-agent: GPTBot\nDisallow: /" in text
        assert "User-agent: ClaudeBot\nDisallow: /" in text
        assert "User-agent: Google-Extended\nDisallow: /" in text
        # Search & citation bots are allowed
        assert "User-agent: OAI-SearchBot\nAllow: /" in text
        assert "User-agent: Claude-SearchBot\nAllow: /" in text
        assert "User-agent: PerplexityBot\nAllow: /" in text
        # Manifest pointers
        assert "LLM: /llms.txt" in text


@pytest.mark.asyncio
async def test_content_negotiation_markdown() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Root endpoint without markdown accept -> JSON
        res_json = await client.get("/")
        assert res_json.status_code == 200
        assert "application/json" in res_json.headers.get("content-type", "")

        # Root endpoint with Accept: text/markdown -> Markdown
        res_md = await client.get("/", headers={"Accept": "text/markdown"})
        assert res_md.status_code == 200
        assert "text/markdown" in res_md.headers.get("content-type", "")
        assert "Accept" in res_md.headers.get("vary", "")
        assert "# SentinelFlow & SentinelPulse" in res_md.text


@pytest.mark.asyncio
async def test_mcp_discovery_manifest() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.get("/.well-known/mcp.json")
        assert res.status_code == 200
        data = res.json()
        assert data["name"] == "sentinelflow-mcp"
        assert data["protocolVersion"] == "2024-11-05"
        assert "tools" in data["capabilities"]
        assert "list_disputes" in data["capabilities"]["tools"]
        assert "classify_telecom" in data["capabilities"]["tools"]


@pytest.mark.asyncio
async def test_mcp_json_rpc_messages() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Initialize
        res_init = await client.post(
            "/api/v1/mcp/messages",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        )
        assert res_init.status_code == 200
        init_data = res_init.json()
        assert init_data["result"]["protocolVersion"] == "2024-11-05"
        assert init_data["result"]["serverInfo"]["name"] == "sentinelflow-mcp"

        # 2. Tools list
        res_tools = await client.post(
            "/api/v1/mcp/messages",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        )
        assert res_tools.status_code == 200
        tools_data = res_tools.json()
        tool_names = [t["name"] for t in tools_data["result"]["tools"]]
        assert "list_disputes" in tool_names
        assert "classify_telecom" in tool_names
        assert "submit_review" in tool_names

        # 3. Ping
        res_ping = await client.post(
            "/api/v1/mcp/messages",
            json={"jsonrpc": "2.0", "id": 3, "method": "ping", "params": {}},
        )
        assert res_ping.status_code == 200
        assert res_ping.json()["result"] == {}

        # 4. Tool call: classify_telecom
        res_call = await client.post(
            "/api/v1/mcp/messages",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "classify_telecom",
                    "arguments": {
                        "sender": "+12025550199",
                        "recipient": "+12025550100",
                        "message": "Your one-time security code is 849201",
                    },
                },
            },
        )
        assert res_call.status_code == 200
        call_data = res_call.json()
        assert "content" in call_data["result"]
        content_text = call_data["result"]["content"][0]["text"]
        assert "verdict" in content_text
