import assert from "node:assert/strict";
import test from "node:test";

import { NextRequest } from "next/server.js";

process.env.APP_ENV = "test";
process.env.AUTH_OIDC_ISSUER = "https://idp.example.com";
process.env.AUTH_OIDC_CLIENT_ID = "sentinelflow-web";
process.env.AUTH_OIDC_CLIENT_SECRET = "secret-for-tests";
process.env.AUTH_OIDC_CALLBACK_PATH = "/auth/callback";
process.env.AUTH_POST_LOGIN_PATH = "/";
process.env.AUTH_POST_LOGOUT_PATH = "/";
process.env.INTERNAL_ACCESS_TOKEN_COOKIE_NAME = "sentinelflow_access_token";
process.env.INTERNAL_ID_TOKEN_COOKIE_NAME = "sentinelflow_id_token";

const discoveryPayload = {
    issuer: "https://idp.example.com",
    authorization_endpoint: "https://idp.example.com/oauth2/v2/auth",
    token_endpoint: "https://idp.example.com/oauth2/v2/token",
    end_session_endpoint: "https://idp.example.com/oauth2/v2/logout",
};

const jsonResponse = (payload, status = 200) => {
    return new Response(JSON.stringify(payload), {
        status,
        headers: {
            "Content-Type": "application/json",
        },
    });
};

test("/auth/login redirects to authorization endpoint and sets transient cookies", async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async () => jsonResponse(discoveryPayload);

    try {
        const { GET } = await import("../app/auth/login/route.ts");
        const request = new NextRequest(
            "https://console.example.com/auth/login?returnTo=/disputes/disp_123&prompt=login",
        );

        const response = await GET(request);

        assert.equal(response.status, 307);
        const location = response.headers.get("location");
        assert.ok(location);
        const redirectUrl = new URL(location);
        assert.equal(redirectUrl.origin, "https://idp.example.com");
        assert.equal(redirectUrl.searchParams.get("client_id"), "sentinelflow-web");
        assert.equal(
            redirectUrl.searchParams.get("redirect_uri"),
            "https://console.example.com/auth/callback",
        );
        assert.equal(redirectUrl.searchParams.get("code_challenge_method"), "S256");
        assert.equal(redirectUrl.searchParams.get("prompt"), "login");
        assert.ok(response.cookies.get("sentinelflow_oidc_state")?.value);
        assert.ok(response.cookies.get("sentinelflow_oidc_nonce")?.value);
        assert.ok(response.cookies.get("sentinelflow_oidc_verifier")?.value);
        assert.equal(
            response.cookies.get("sentinelflow_oidc_return_to")?.value,
            "/disputes/disp_123",
        );
    } finally {
        globalThis.fetch = originalFetch;
    }
});

test("/auth/callback exchanges code, stores tokens, and clears transient cookies", async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async (url) => {
        const asString = String(url);
        if (asString.includes("openid-configuration")) {
            return jsonResponse(discoveryPayload);
        }
        if (asString.includes("/oauth2/v2/token")) {
            return jsonResponse({
                access_token: "access-token-123",
                id_token: "id-token-456",
                expires_in: 1800,
            });
        }
        throw new Error(`Unexpected fetch URL in test: ${asString}`);
    };

    try {
        const { GET } = await import("../app/auth/callback/route.ts");
        const request = new NextRequest(
            "https://console.example.com/auth/callback?code=auth-code&state=state-123&iss=https://idp.example.com",
            {
                headers: {
                    cookie: [
                        "sentinelflow_oidc_state=state-123",
                        "sentinelflow_oidc_verifier=verifier-abc",
                        "sentinelflow_oidc_return_to=/disputes/disp_123",
                    ].join("; "),
                },
            },
        );

        const response = await GET(request);

        assert.equal(response.status, 307);
        assert.equal(response.headers.get("location"), "https://console.example.com/disputes/disp_123");
        assert.equal(response.cookies.get("sentinelflow_access_token")?.value, "access-token-123");
        assert.equal(response.cookies.get("sentinelflow_id_token")?.value, "id-token-456");
        assert.equal(response.cookies.get("sentinelflow_oidc_state")?.value, "");
        assert.equal(response.cookies.get("sentinelflow_oidc_nonce")?.value, "");
        assert.equal(response.cookies.get("sentinelflow_oidc_verifier")?.value, "");
        assert.equal(response.cookies.get("sentinelflow_oidc_return_to")?.value, "");
    } finally {
        globalThis.fetch = originalFetch;
    }
});

test("/auth/logout clears session cookies and redirects to IdP logout endpoint", async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async () => jsonResponse(discoveryPayload);

    try {
        const { GET } = await import("../app/auth/logout/route.ts");
        const request = new NextRequest("https://console.example.com/auth/logout", {
            headers: {
                cookie: "sentinelflow_id_token=id-token-456",
            },
        });

        const response = await GET(request);

        assert.equal(response.status, 307);
        const location = response.headers.get("location");
        assert.ok(location);
        const redirectUrl = new URL(location);
        assert.equal(redirectUrl.origin, "https://idp.example.com");
        assert.equal(redirectUrl.pathname, "/oauth2/v2/logout");
        assert.equal(
            redirectUrl.searchParams.get("post_logout_redirect_uri"),
            "https://console.example.com/",
        );
        assert.equal(redirectUrl.searchParams.get("id_token_hint"), "id-token-456");
        assert.equal(response.cookies.get("sentinelflow_access_token")?.value, "");
        assert.equal(response.cookies.get("sentinelflow_id_token")?.value, "");
    } finally {
        globalThis.fetch = originalFetch;
    }
});
