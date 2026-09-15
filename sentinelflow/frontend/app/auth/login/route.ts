import { NextRequest, NextResponse } from "next/server.js";

import {
    OIDC_NONCE_COOKIE_NAME,
    OIDC_RETURN_TO_COOKIE_NAME,
    OIDC_STATE_COOKIE_NAME,
    OIDC_VERIFIER_COOKIE_NAME,
    base64UrlRandom,
    cookieSecureFlag,
    createPkceChallenge,
    getOidcClientConfig,
    getOidcDiscoveryDocument,
    resolveCallbackUrl,
    sanitizeReturnPath,
} from "../../../lib/oidc.ts";

const transientCookieMaxAgeSeconds = 600;

export const GET = async (request: NextRequest): Promise<NextResponse> => {
    try {
        const discovery = await getOidcDiscoveryDocument();
        const clientConfig = getOidcClientConfig();

        const state = base64UrlRandom(24);
        const nonce = base64UrlRandom(24);
        const verifier = base64UrlRandom(32);
        const challenge = createPkceChallenge(verifier);
        const returnTo = sanitizeReturnPath(request.nextUrl.searchParams.get("returnTo"));

        const authorizeUrl = new URL(discovery.authorization_endpoint);
        authorizeUrl.searchParams.set("response_type", "code");
        authorizeUrl.searchParams.set("client_id", clientConfig.clientId);
        authorizeUrl.searchParams.set("redirect_uri", resolveCallbackUrl(request));
        authorizeUrl.searchParams.set("scope", clientConfig.scope);
        authorizeUrl.searchParams.set("state", state);
        authorizeUrl.searchParams.set("nonce", nonce);
        authorizeUrl.searchParams.set("code_challenge", challenge);
        authorizeUrl.searchParams.set("code_challenge_method", "S256");

        const prompt = request.nextUrl.searchParams.get("prompt");
        if (prompt) {
            authorizeUrl.searchParams.set("prompt", prompt);
        }

        const response = NextResponse.redirect(authorizeUrl);
        const secure = cookieSecureFlag(request);
        response.cookies.set(OIDC_STATE_COOKIE_NAME, state, {
            httpOnly: true,
            sameSite: "lax",
            secure,
            path: "/",
            maxAge: transientCookieMaxAgeSeconds,
        });
        response.cookies.set(OIDC_NONCE_COOKIE_NAME, nonce, {
            httpOnly: true,
            sameSite: "lax",
            secure,
            path: "/",
            maxAge: transientCookieMaxAgeSeconds,
        });
        response.cookies.set(OIDC_VERIFIER_COOKIE_NAME, verifier, {
            httpOnly: true,
            sameSite: "lax",
            secure,
            path: "/",
            maxAge: transientCookieMaxAgeSeconds,
        });
        response.cookies.set(OIDC_RETURN_TO_COOKIE_NAME, returnTo, {
            httpOnly: true,
            sameSite: "lax",
            secure,
            path: "/",
            maxAge: transientCookieMaxAgeSeconds,
        });
        return response;
    } catch (error) {
        return NextResponse.json(
            {
                error: {
                    code: "OIDC_LOGIN_INIT_FAILED",
                    message: error instanceof Error ? error.message : "OIDC login initialization failed.",
                },
            },
            { status: 500 },
        );
    }
};
