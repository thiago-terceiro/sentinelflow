import { NextRequest, NextResponse } from "next/server.js";

import { sanitizeReturnPath } from "../../../lib/testAuth.ts";

export const GET = async (request: NextRequest): Promise<NextResponse> => {
    const fallback = request.nextUrl.searchParams.get("returnTo");
    const legacyRedirect = request.nextUrl.searchParams.get("redirect");
    const returnTo = sanitizeReturnPath(fallback ?? legacyRedirect);
    const destination = new URL("/login", request.nextUrl.origin);
    destination.searchParams.set("returnTo", returnTo);
    return NextResponse.redirect(destination);
};
