import { NextRequest, NextResponse } from "next/server.js";

import {
    ACCESS_TOKEN_COOKIE_NAME,
    ID_TOKEN_COOKIE_NAME,
    OIDC_NONCE_COOKIE_NAME,
    OIDC_RETURN_TO_COOKIE_NAME,
    OIDC_STATE_COOKIE_NAME,
    OIDC_VERIFIER_COOKIE_NAME,
    cookieSecureFlag,
    getOidcClientConfig,
    getOidcDiscoveryDocument,
    resolveCallbackUrl,
    resolveOrigin,
    sanitizeReturnPath,
} from "../../../lib/oidc.ts";

type TokenResponse = {
    access_token?: string;
    id_token?: string;
    expires_in?: number;
    error?: string;
    error_description?: string;
};

const clearTransientCookies = (response: NextResponse): void => {
    response.cookies.set(OIDC_STATE_COOKIE_NAME, "", { path: "/", maxAge: 0 });
    response.cookies.set(OIDC_NONCE_COOKIE_NAME, "", { path: "/", maxAge: 0 });
    response.cookies.set(OIDC_VERIFIER_COOKIE_NAME, "", { path: "/", maxAge: 0 });
    response.cookies.set(OIDC_RETURN_TO_COOKIE_NAME, "", { path: "/", maxAge: 0 });
};

const errorRedirect = (request: NextRequest, message: string): NextResponse => {
    const destination = new URL("/", resolveOrigin(request));
    destination.searchParams.set("auth_error", message);
    const response = NextResponse.redirect(destination);
    clearTransientCookies(response);
    return response;
};

export const GET = async (request: NextRequest): Promise<NextResponse> => {
    const callbackError = request.nextUrl.searchParams.get("error");
    if (callbackError) {
        return errorRedirect(request, callbackError);
    }

    const code = request.nextUrl.searchParams.get("code");
    const state = request.nextUrl.searchParams.get("state");
    const expectedState = request.cookies.get(OIDC_STATE_COOKIE_NAME)?.value;
    const verifier = request.cookies.get(OIDC_VERIFIER_COOKIE_NAME)?.value;

    if (!code || !state || !expectedState || !verifier || state !== expectedState) {
        return errorRedirect(request, "invalid_oauth_state");
    }

    try {
        const discovery = await getOidcDiscoveryDocument();
        const callbackIssuer = request.nextUrl.searchParams.get("iss");
        if (callbackIssuer && callbackIssuer !== discovery.issuer) {
            return errorRedirect(request, "issuer_mismatch");
        }

        const clientConfig = getOidcClientConfig();
        const tokenBody = new URLSearchParams({
            grant_type: "authorization_code",
            code,
            client_id: clientConfig.clientId,
            code_verifier: verifier,
            redirect_uri: resolveCallbackUrl(request),
        });
        if (clientConfig.clientSecret) {
            tokenBody.set("client_secret", clientConfig.clientSecret);
        }

        const tokenResponse = await fetch(discovery.token_endpoint, {
            method: "POST",
            headers: {
                Accept: "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            body: tokenBody.toString(),
            cache: "no-store",
        });

        const tokenPayload = (await tokenResponse.json()) as TokenResponse;
        if (!tokenResponse.ok || tokenPayload.error || !tokenPayload.access_token) {
            const message = tokenPayload.error_description ?? tokenPayload.error ?? `token_exchange_${tokenResponse.status}`;
            return errorRedirect(request, message);
        }

        const returnTo = sanitizeReturnPath(request.cookies.get(OIDC_RETURN_TO_COOKIE_NAME)?.value ?? null);
        const destination = new URL(returnTo, resolveOrigin(request));
        const response = NextResponse.redirect(destination);
        const secure = cookieSecureFlag(request);
        const cookieMaxAge = typeof tokenPayload.expires_in === "number"
            ? Math.max(60, tokenPayload.expires_in)
            : 3600;

        response.cookies.set(ACCESS_TOKEN_COOKIE_NAME, tokenPayload.access_token, {
            httpOnly: true,
            sameSite: "lax",
            secure,
            path: "/",
            maxAge: cookieMaxAge,
        });

        if (tokenPayload.id_token) {
            response.cookies.set(ID_TOKEN_COOKIE_NAME, tokenPayload.id_token, {
                httpOnly: true,
                sameSite: "lax",
                secure,
                path: "/",
                maxAge: cookieMaxAge,
            });
        }

        clearTransientCookies(response);
        return response;
    } catch (error) {
        return errorRedirect(
            request,
            error instanceof Error ? error.message : "oidc_callback_failed",
        );
    }
};

export const POST = GET;