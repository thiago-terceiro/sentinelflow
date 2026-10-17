import { NextRequest, NextResponse } from "next/server.js";

import {
  ACCESS_TOKEN_COOKIE_NAME,
  ID_TOKEN_COOKIE_NAME,
  TEST_USER_COOKIE_NAME,
} from "../../../lib/testAuth.ts";

const clearSessionCookies = (response: NextResponse): void => {
  response.cookies.set(ACCESS_TOKEN_COOKIE_NAME, "", {
    path: "/",
    maxAge: 0,
  });
  response.cookies.set(ID_TOKEN_COOKIE_NAME, "", {
    path: "/",
    maxAge: 0,
  });
  response.cookies.set(TEST_USER_COOKIE_NAME, "", {
    path: "/",
    maxAge: 0,
  });
};

export const GET = async (request: NextRequest): Promise<NextResponse> => {
  const destination = new URL("/", request.nextUrl.origin);
  const response = NextResponse.redirect(destination);
  clearSessionCookies(response);
  return response;
};
