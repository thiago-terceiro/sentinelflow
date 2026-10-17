import { NextRequest, NextResponse } from "next/server.js";

export const GET = async (request: NextRequest): Promise<NextResponse> => {
  const destination = new URL("/login", request.nextUrl.origin);
  destination.searchParams.set("error", "oidc_disabled");
  return NextResponse.redirect(destination);
};

export const POST = GET;
