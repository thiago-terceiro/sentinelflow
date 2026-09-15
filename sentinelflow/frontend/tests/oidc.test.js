import assert from "node:assert/strict";
import test from "node:test";

import { createPkceChallenge, sanitizeReturnPath } from "../lib/oidc.ts";

test("createPkceChallenge returns deterministic base64url value", () => {
  const challenge = createPkceChallenge("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk");

  assert.equal(challenge, "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM");
});

test("sanitizeReturnPath rejects unsafe redirects", () => {
  assert.equal(sanitizeReturnPath("/disputes/123"), "/disputes/123");
  assert.equal(sanitizeReturnPath("https://evil.example"), "/");
  assert.equal(sanitizeReturnPath("//evil.example"), "/");
  assert.equal(sanitizeReturnPath(null), "/");
});
