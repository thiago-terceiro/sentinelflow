import { NextRequest, NextResponse } from "next/server.js";

import {
  ACCESS_TOKEN_COOKIE_NAME,
  ID_TOKEN_COOKIE_NAME,
  TEST_USER_COOKIE_NAME,
  cookieSecureFlag,
} from "../../../lib/testAuth.ts";

export const dynamic = "force-dynamic";

const clearSessionCookies = (request: NextRequest, response: NextResponse): void => {
  const secure = cookieSecureFlag(request.nextUrl.protocol);
  const clearOptions = {
    httpOnly: true,
    sameSite: "lax" as const,
    secure,
    path: "/",
    maxAge: 0,
    expires: new Date(0),
  };
  response.cookies.set(ACCESS_TOKEN_COOKIE_NAME, "", clearOptions);
  response.cookies.set(ID_TOKEN_COOKIE_NAME, "", clearOptions);
  response.cookies.set(TEST_USER_COOKIE_NAME, "", clearOptions);
  response.headers.set("Cache-Control", "no-store, no-cache, must-revalidate");
};

export const GET = async (request: NextRequest): Promise<NextResponse> => {
  const destination = new URL("/", request.nextUrl.origin);
  const response = NextResponse.redirect(destination);
  clearSessionCookies(request, response);
  return response;
};

export const POST = async (request: NextRequest): Promise<NextResponse> => {
  const response = NextResponse.json({ status: "signed_out" });
  clearSessionCookies(request, response);
  return response;
};
