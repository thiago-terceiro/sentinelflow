import assert from "node:assert/strict";
import test from "node:test";

import { NextRequest } from "next/server.js";

test("/auth/login redirects to /login and preserves returnTo", async () => {
    const { GET } = await import("../app/auth/login/route.ts");
    const request = new NextRequest("https://console.example.com/auth/login?returnTo=/disputes/disp_123");

    const response = await GET(request);

    assert.equal(response.status, 307);
    assert.equal(
        response.headers.get("location"),
        "https://console.example.com/login?returnTo=%2Fdisputes%2Fdisp_123",
    );
});

test("/api/auth/login accepts hardcoded credentials and sets session cookies", async () => {
    const { POST } = await import("../app/api/auth/login/route.ts");
    const body = new URLSearchParams({
        username: "reviewer",
        password: "reviewer123",
        role: "reviewer",
        returnTo: "/",
    });
    const request = new NextRequest("https://console.example.com/api/auth/login", {
        method: "POST",
        body,
        headers: {
            "Content-Type": "application/x-www-form-urlencoded",
        },
    });

    const response = await POST(request);

    assert.equal(response.status, 307);
    assert.equal(response.headers.get("location"), "https://console.example.com/");
    assert.equal(response.cookies.get("sentinelflow_access_token")?.value, "dev-reviewer");
    assert.equal(response.cookies.get("sentinelflow_test_user")?.value, "reviewer:reviewer");
});

test("/api/auth/login rejects invalid credentials", async () => {
    const { POST } = await import("../app/api/auth/login/route.ts");
    const body = new URLSearchParams({
        username: "reviewer",
        password: "wrong-password",
        role: "reviewer",
        returnTo: "/disputes",
    });
    const request = new NextRequest("https://console.example.com/api/auth/login", {
        method: "POST",
        body,
        headers: {
            "Content-Type": "application/x-www-form-urlencoded",
        },
    });

    const response = await POST(request);

    assert.equal(response.status, 307);
    assert.equal(
        response.headers.get("location"),
        "https://console.example.com/login?error=invalid_credentials&returnTo=%2Fdisputes",
    );
});

test("/auth/callback redirects to /login with oidc_disabled", async () => {
    const { GET } = await import("../app/auth/callback/route.ts");
    const request = new NextRequest("https://console.example.com/auth/callback?code=test");

    const response = await GET(request);

    assert.equal(response.status, 307);
    assert.equal(response.headers.get("location"), "https://console.example.com/login?error=oidc_disabled");
});

test("/auth/logout clears session cookies and redirects home", async () => {
    const { GET } = await import("../app/auth/logout/route.ts");
    const request = new NextRequest("https://console.example.com/auth/logout", {
        headers: {
            cookie: [
                "sentinelflow_access_token=dev-reviewer",
                "sentinelflow_id_token=id-token-123",
                "sentinelflow_test_user=reviewer:reviewer",
            ].join("; "),
        },
    });

    const response = await GET(request);

    assert.equal(response.status, 307);
    assert.equal(response.headers.get("location"), "https://console.example.com/");
    assert.equal(response.cookies.get("sentinelflow_access_token")?.value, "");
    assert.equal(response.cookies.get("sentinelflow_id_token")?.value, "");
    assert.equal(response.cookies.get("sentinelflow_test_user")?.value, "");
});
