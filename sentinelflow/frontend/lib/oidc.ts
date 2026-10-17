import { createHash, randomBytes } from "node:crypto";

import type { NextRequest } from "next/server.js";

export type OidcDiscoveryDocument = {
  issuer: string;
  authorization_endpoint: string;
  token_endpoint: string;
  end_session_endpoint?: string;
};

type OidcClientConfig = {
  clientId: string;
  clientSecret: string | null;
  scope: string;
};

export const ACCESS_TOKEN_COOKIE_NAME =
  process.env.INTERNAL_ACCESS_TOKEN_COOKIE_NAME ?? "sentinelflow_access_token";
export const ID_TOKEN_COOKIE_NAME =
  process.env.INTERNAL_ID_TOKEN_COOKIE_NAME ?? "sentinelflow_id_token";

export const OIDC_STATE_COOKIE_NAME = "sentinelflow_oidc_state";
export const OIDC_VERIFIER_COOKIE_NAME = "sentinelflow_oidc_verifier";
export const OIDC_NONCE_COOKIE_NAME = "sentinelflow_oidc_nonce";
export const OIDC_RETURN_TO_COOKIE_NAME = "sentinelflow_oidc_return_to";

const APP_ENV = process.env.APP_ENV ?? process.env.NODE_ENV ?? "development";
const OIDC_SCOPE = process.env.AUTH_OIDC_SCOPE ?? "openid profile email";
const OIDC_DISCOVERY_URL = process.env.AUTH_OIDC_DISCOVERY_URL ?? "";
const OIDC_ISSUER = process.env.AUTH_OIDC_ISSUER ?? "";
const OIDC_CLIENT_ID = process.env.AUTH_OIDC_CLIENT_ID ?? "";
const OIDC_CLIENT_SECRET = process.env.AUTH_OIDC_CLIENT_SECRET ?? "";
const OIDC_CALLBACK_PATH = process.env.AUTH_OIDC_CALLBACK_PATH ?? "/auth/callback";
const DEFAULT_POST_LOGIN_PATH = process.env.AUTH_POST_LOGIN_PATH ?? "/";
const DEFAULT_POST_LOGOUT_PATH = process.env.AUTH_POST_LOGOUT_PATH ?? "/";

const assertConfigured = (): void => {
  if (!OIDC_CLIENT_ID) {
    throw new Error("AUTH_OIDC_CLIENT_ID is required for OIDC login.");
  }
  if (!OIDC_DISCOVERY_URL && !OIDC_ISSUER) {
    throw new Error("AUTH_OIDC_DISCOVERY_URL or AUTH_OIDC_ISSUER is required for OIDC login.");
  }
};

const resolveDiscoveryUrl = (): string => {
  if (OIDC_DISCOVERY_URL) {
    return OIDC_DISCOVERY_URL;
  }
  return `${OIDC_ISSUER.replace(/\/$/, "")}/.well-known/openid-configuration`;
};

export const getOidcClientConfig = (): OidcClientConfig => {
  assertConfigured();
  return {
    clientId: OIDC_CLIENT_ID,
    clientSecret: OIDC_CLIENT_SECRET || null,
    scope: OIDC_SCOPE,
  };
};

export const getOidcDiscoveryDocument = async (): Promise<OidcDiscoveryDocument> => {
  assertConfigured();
  const response = await fetch(resolveDiscoveryUrl(), {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`OIDC discovery failed with status ${response.status}.`);
  }
  const payload = (await response.json()) as Partial<OidcDiscoveryDocument>;
  if (!payload.issuer || !payload.authorization_endpoint || !payload.token_endpoint) {
    throw new Error("OIDC discovery response is missing required endpoints.");
  }
  return {
    issuer: payload.issuer,
    authorization_endpoint: payload.authorization_endpoint,
    token_endpoint: payload.token_endpoint,
    end_session_endpoint: payload.end_session_endpoint,
  };
};

export const base64UrlRandom = (bytes: number): string => {
  return randomBytes(bytes).toString("base64url");
};

export const createPkceChallenge = (verifier: string): string => {
  return createHash("sha256").update(verifier).digest("base64url");
};

export const resolveOrigin = (request: NextRequest): string => {
  const forwardedHost = request.headers.get("x-forwarded-host");
  const forwardedProto = request.headers.get("x-forwarded-proto");
  const host = forwardedHost ?? request.headers.get("host") ?? request.nextUrl.host;
  const protocol = forwardedProto ?? request.nextUrl.protocol.replace(":", "");
  return `${protocol}://${host}`;
};

export const resolveCallbackUrl = (request: NextRequest): string => {
  return `${resolveOrigin(request)}${OIDC_CALLBACK_PATH}`;
};

export const cookieSecureFlag = (request: NextRequest): boolean => {
  if (APP_ENV === "production") {
    return true;
  }
  const forwardedProto = request.headers.get("x-forwarded-proto");
  const protocol = (forwardedProto ?? request.nextUrl.protocol.replace(":", "")).toLowerCase();
  return protocol === "https";
};

export const sanitizeReturnPath = (value: string | null): string => {
  if (!value) {
    return DEFAULT_POST_LOGIN_PATH;
  }
  if (!value.startsWith("/") || value.startsWith("//")) {
    return DEFAULT_POST_LOGIN_PATH;
  }
  return value;
};

export const getDefaultPostLogoutPath = (): string => {
  return DEFAULT_POST_LOGOUT_PATH;
};
