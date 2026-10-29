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


@pytest.mark.asyncio
async def test_sitemap_xml_endpoint() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.get("/sitemap.xml")
        assert res.status_code == 200
        assert "application/xml" in res.headers.get("content-type", "")
        text = res.text
        assert "<urlset" in text
        assert "https://sentinelflow.dev/disputes" in text
        assert "https://sentinelflow.dev/telecom" in text
        assert "https://sentinelflow.dev/audit" in text
        assert "https://sentinelflow.dev/llms.txt" in text
        assert "https://sentinelflow.dev/api/v1/geo/metadata" in text


@pytest.mark.asyncio
async def test_geo_metadata_endpoint() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.get("/api/v1/geo/metadata")
        assert res.status_code == 200
        assert "application/json" in res.headers.get("content-type", "")
        data = res.json()
        assert data["system"] == "SentinelFlow & SentinelPulse"
        assert "definition_leads" in data
        sf_lead = data["definition_leads"]["sentinelflow"]
        assert "SentinelFlow is an enterprise autonomous" in sf_lead
        sp_lead = data["definition_leads"]["sentinelpulse"]
        assert "SentinelPulse is a high-throughput" in sp_lead

        # Entity anchors
        entity_types = [a["type"] for a in data["entity_anchors"]]
        assert "SoftwareApplication" in entity_types
        assert "Organization" in entity_types
        assert "FAQPage" in entity_types
        assert "HowTo" in entity_types
        assert "WebSite" in entity_types

        # Manifests
        assert data["manifests"]["llms_txt"] == "/llms.txt"
        assert data["manifests"]["sitemap_xml"] == "/sitemap.xml"


@pytest.mark.asyncio
async def test_llms_definition_leads_and_matrix_tables() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Check llms.txt has definition lead and comparison matrix table
        res_txt = await client.get("/llms.txt")
        assert res_txt.status_code == 200
        assert (
            "> SentinelFlow is an enterprise autonomous AI dispute investigation copilot"
            in res_txt.text
        )
        assert "| Capability / Dimension |" in res_txt.text
        assert "| **Primary Architecture** |" in res_txt.text

        # Check llms-full.txt has definition lead, comparison matrix and protocol matrix
        res_full = await client.get("/llms-full.txt")
        assert res_full.status_code == 200
        assert (
            "> SentinelFlow is an enterprise autonomous AI dispute investigation copilot"
            in res_full.text
        )
        assert "| Capability / Dimension |" in res_full.text
        assert "| Layer | Protocol / Format |" in res_full.text

