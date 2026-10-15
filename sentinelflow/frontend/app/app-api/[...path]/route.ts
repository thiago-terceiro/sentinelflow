import { NextRequest } from "next/server.js";

const INTERNAL_API_BASE_URL =
    process.env.INTERNAL_API_BASE_URL ??
    process.env.NEXT_PUBLIC_API_BASE_URL ??
    "http://localhost:8000/api/v1";
const ACCESS_TOKEN_COOKIE_NAME =
    process.env.INTERNAL_ACCESS_TOKEN_COOKIE_NAME ?? "sentinelflow_access_token";

const passthroughHeaders = (headers: Headers): Headers => {
    const nextHeaders = new Headers();
    const allowList = [
        "content-type",
        "cache-control",
        "etag",
        "last-modified",
        "x-request-id",
    ];
    for (const headerName of allowList) {
        const value = headers.get(headerName);
        if (value) {
            nextHeaders.set(headerName, value);
        }
    }
    return nextHeaders;
};

const targetPath = (parts: string[], query: string): string => {
    const base = INTERNAL_API_BASE_URL.replace(/\/$/, "");
    const path = `${base}/${parts.join("/")}`;
    return query ? `${path}?${query}` : path;
};

const tokenFromAuthorizationHeader = (value: string | null): string | null => {
    if (!value) {
        return null;
    }
    const [scheme, token] = value.split(/\s+/, 2);
    if (scheme?.toLowerCase() !== "bearer" || !token) {
        return null;
    }
    return token;
};

const resolveCallerToken = (request: NextRequest): string | null => {
    const headerToken = tokenFromAuthorizationHeader(request.headers.get("authorization"));
    if (headerToken) {
        return headerToken;
    }
    const cookieToken = request.cookies.get(ACCESS_TOKEN_COOKIE_NAME)?.value;
    if (cookieToken) {
        return cookieToken;
    }
    return null;
};

const proxy = async (request: NextRequest, parts: string[]): Promise<Response> => {
    if (parts.length === 0) {
        return Response.json({ error: { code: "BAD_PROXY_PATH", message: "Path is required." } }, { status: 400 });
    }

    const token = resolveCallerToken(request);
    if (!token) {
        return Response.json(
            {
                error: {
                    code: "UNAUTHENTICATED",
                    message: "Authentication is required.",
                },
            },
            { status: 401 },
        );
    }

    const requestHeaders = new Headers();
    requestHeaders.set("Accept", request.headers.get("accept") ?? "application/json");
    requestHeaders.set("Authorization", `Bearer ${token}`);
    const contentType = request.headers.get("content-type");
    if (contentType) {
        requestHeaders.set("Content-Type", contentType);
    }
    const requestId = request.headers.get("x-request-id");
    if (requestId) {
        requestHeaders.set("X-Request-Id", requestId);
    }

    try {
        const body = request.method === "GET" ? undefined : await request.text();
        const upstreamResponse = await fetch(targetPath(parts, request.nextUrl.searchParams.toString()), {
            method: request.method,
            headers: requestHeaders,
            body,
            cache: "no-store",
        });

        return new Response(upstreamResponse.body, {
            status: upstreamResponse.status,
            headers: passthroughHeaders(upstreamResponse.headers),
        });
    } catch (error) {
        const message = error instanceof Error ? error.message : "Upstream connection error";
        return Response.json(
            {
                error: {
                    code: "UPSTREAM_UNAVAILABLE",
                    message: `Failed to communicate with backend service: ${message}`,
                },
            },
            { status: 502 },
        );
    }
};

type RouteContext = {
    params: Promise<{ path: string[] }>;
};

export const GET = async (request: NextRequest, context: RouteContext): Promise<Response> => {
    const params = await context.params;
    return proxy(request, params.path ?? []);
};

export const POST = async (request: NextRequest, context: RouteContext): Promise<Response> => {
    const params = await context.params;
    return proxy(request, params.path ?? []);
};
