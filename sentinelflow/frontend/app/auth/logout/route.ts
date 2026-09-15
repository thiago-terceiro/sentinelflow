import { NextRequest, NextResponse } from "next/server.js";

import {
    ACCESS_TOKEN_COOKIE_NAME,
    ID_TOKEN_COOKIE_NAME,
    getDefaultPostLogoutPath,
    getOidcDiscoveryDocument,
    resolveOrigin,
} from "../../../lib/oidc.ts";

const clearSessionCookies = (response: NextResponse): void => {
    response.cookies.set(ACCESS_TOKEN_COOKIE_NAME, "", {
        path: "/",
        maxAge: 0,
    });
    response.cookies.set(ID_TOKEN_COOKIE_NAME, "", {
        path: "/",
        maxAge: 0,
    });
};

export const GET = async (request: NextRequest): Promise<NextResponse> => {
    const fallbackTarget = new URL(getDefaultPostLogoutPath(), resolveOrigin(request));
    const fallbackResponse = NextResponse.redirect(fallbackTarget);
    clearSessionCookies(fallbackResponse);

    const idToken = request.cookies.get(ID_TOKEN_COOKIE_NAME)?.value;

    try {
        const discovery = await getOidcDiscoveryDocument();
        if (!discovery.end_session_endpoint) {
            return fallbackResponse;
        }

        const logoutUrl = new URL(discovery.end_session_endpoint);
        logoutUrl.searchParams.set("post_logout_redirect_uri", fallbackTarget.toString());
        if (idToken) {
            logoutUrl.searchParams.set("id_token_hint", idToken);
        }

        const response = NextResponse.redirect(logoutUrl);
        clearSessionCookies(response);
        return response;
    } catch {
        return fallbackResponse;
    }
};
