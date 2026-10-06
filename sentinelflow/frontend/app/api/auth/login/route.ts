import { NextRequest, NextResponse } from "next/server.js";

import {
    ACCESS_TOKEN_COOKIE_NAME,
    ID_TOKEN_COOKIE_NAME,
    TEST_AUTH_SESSION_MAX_AGE_SECONDS,
    TEST_USER_COOKIE_NAME,
    cookieSecureFlag,
    findTestAuthUser,
    sanitizeReturnPath,
} from "../../../../lib/testAuth.ts";

const redirectToLogin = (request: NextRequest, errorCode: string, returnTo: string): NextResponse => {
    const destination = new URL("/login", request.nextUrl.origin);
    destination.searchParams.set("error", errorCode);
    destination.searchParams.set("returnTo", returnTo);
    return NextResponse.redirect(destination);
};

export const GET = async (request: NextRequest): Promise<NextResponse> => {
    const returnTo = sanitizeReturnPath(request.nextUrl.searchParams.get("returnTo"));
    const destination = new URL("/login", request.nextUrl.origin);
    destination.searchParams.set("returnTo", returnTo);
    return NextResponse.redirect(destination);
};

export const POST = async (request: NextRequest): Promise<NextResponse> => {
    const formData = await request.formData();
    const username = String(formData.get("username") ?? "");
    const password = String(formData.get("password") ?? "");
    const role = String(formData.get("role") ?? "");
    const returnTo = sanitizeReturnPath(String(formData.get("returnTo") ?? "/"));

    if (!username || !password || !role) {
        return redirectToLogin(request, "missing_credentials", returnTo);
    }

    const user = findTestAuthUser(username, password, role);
    if (!user) {
        return redirectToLogin(request, "invalid_credentials", returnTo);
    }

    const destination = new URL(returnTo, request.nextUrl.origin);
    const response = NextResponse.redirect(destination);
    const secure = cookieSecureFlag(request.nextUrl.protocol);

    response.cookies.set(ACCESS_TOKEN_COOKIE_NAME, user.token, {
        httpOnly: true,
        sameSite: "lax",
        secure,
        path: "/",
        maxAge: TEST_AUTH_SESSION_MAX_AGE_SECONDS,
    });
    response.cookies.set(TEST_USER_COOKIE_NAME, `${user.username}:${user.role}`, {
        httpOnly: true,
        sameSite: "lax",
        secure,
        path: "/",
        maxAge: TEST_AUTH_SESSION_MAX_AGE_SECONDS,
    });
    response.cookies.set(ID_TOKEN_COOKIE_NAME, "", {
        path: "/",
        maxAge: 0,
    });

    return response;
};