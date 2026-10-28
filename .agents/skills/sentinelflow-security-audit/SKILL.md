---
name: sentinelflow-security-audit
description: >-
  Audits, validates, and remediates security controls in SentinelFlow. Use when testing OWASP Top 10, LLM Top 10 prompt injection defense, PCI-DSS/GDPR PII redacting, Fernet encryption, cryptographic SHA-256 audit ledger integrity, RBAC dev-token lockout, or scanning for Bandit/Ruff/CVE vulnerabilities.
---

# SentinelFlow Security Audit Skill

This skill guides the rigorous security auditing and verification of the SentinelFlow & SentinelPulse platform across compliance, cryptography, privacy, and application security.

## Core Security Controls Overview

SentinelFlow implements 11 automated security controls mapped to OWASP Top 10 (2021), OWASP LLM Top 10 (2025), and CWE Top 25:

| Control ID | Standard | Target Subsystem | Mandate |
| :--- | :--- | :--- | :--- |
| **SAST-PY-RUFF-S** | OWASP A03 / A05 | `backend/app/` | 0 Bandit S-rule violations (flake8-bandit AST scan) |
| **SAST-PY-BANDIT** | CWE Top 25 | `backend/app/` | 0 high/medium AST security vulnerabilities |
| **SCA-PY-PIP-AUDIT**| OWASP A06 | `backend/pyproject.toml` | 0 known CVEs / OSV advisories |
| **SAST-TS-SONARJS** | OWASP A03 / A04 | `frontend/` | 0 ReDoS, prototype pollution, or security hotspots |
| **SCA-TS-PNPM-AUDIT**| OWASP A06 | `frontend/package.json` | 0 high/critical dependencies vulnerabilities |
| **OWASP-A01-RBAC** | OWASP A01 / CWE-284 | `backend/app/security.py` | Strict RBAC; dev tokens disabled when `AUTH_ALLOW_DEV_TOKENS=False` |
| **OWASP-A02-CRYPTO** | OWASP A02 / LLM02 | `app/services/trace_safety.py` | Pre-LLM redaction of PAN, SSN, IBAN, JWT, API keys; Fernet vault |
| **OWASP-A04-AGENCY** | OWASP A04 / LLM06 | `app/graph/nodes.py` | Native LangGraph `interrupt()` + `MAX_REVISION_CYCLES = 3` |
| **OWASP-A05-HTTP** | OWASP A05 / CWE-16 | `app/http.py` | Strict CSP, nosniff, frame-options DENY, TrustedHost |
| **OWASP-A07-PKCE** | OWASP A07 / RFC 7636 | `frontend/lib/oidc.ts` | S256 PKCE challenges, state nonces, HTTP-only cookies |
| **OWASP-A08-AUDIT** | OWASP A08 / CWE-353 | `app/services/audit.py` | Append-only SHA-256 cryptographic hash-chain ledger |

---

## Step-by-Step Security Audit Procedure

### Step 1: Run the Automated Compliance Suite
Run the 11-control automated scanner from `sentinelflow/backend`:
```bash
uv run python ../ops/security_compliance_scan.py
```
**Verification Checkpoint**:
- Verify that all 11 controls display `[PASS]`.
- Confirm report is persisted to `sentinelflow/backend/app/evals/security_compliance_latest.json`.

### Step 2: Validate PII Redaction & Pre-Inference Scrubbing
Inspect `sentinelflow/backend/app/services/trace_safety.py`:
1. Ensure all sensitive pattern regexes in `REDACTION_PATTERNS` are compiled at module load time.
2. Test sample strings through `redact_text()`:
   - Credit Card: `4111-2222-3333-4444` $\to$ `[REDACTED_CARDLIKE]`
   - SSN: `123-45-6789` $\to$ `[REDACTED_SSN]`
   - IBAN: `GB82 WEST 1234 5698 7654 32` $\to$ `[REDACTED_IBAN]`
   - JWT: `eyJhbGciOi...` $\to$ `[REDACTED_JWT]`
   - API Key: `sk-proj-abc123...` $\to$ `[REDACTED_KEY]`
3. Ensure `redact_text()` or `sanitize_for_prompt()` is invoked in `sentinelflow/backend/app/agents/` and `sentinelflow/backend/app/graph/nodes.py` *before* payloads reach LLM endpoints.

### Step 3: Verify Cryptographic SHA-256 Ledger Integrity
Inspect `sentinelflow/backend/app/services/audit.py`:
1. Verify the hash chaining logic:
   ```python
   def compute_row_hash(seq: int, prev_hash: str, event_name: str, actor_role: str, payload_json: str) -> str:
       content = f"{seq}:{prev_hash}:{event_name}:{actor_role}:{payload_json}"
       return hashlib.sha256(content.encode("utf-8")).hexdigest()
   ```
2. Verify that sequence 0 has `prev_hash = "0" * 64`.
3. Verify that writes acquire the per-investigation `asyncio.Lock` (`_session_locks[investigation_id]`) to prevent concurrent race conditions from branching the chain.
4. Verify the integrity verification logic (`verify_ledger_integrity`): it must traverse all records from `seq=0` to head and assert that every `prev_hash` equals the preceding `row_hash`.

### Step 4: Verify Prompt Injection Defense in AI Evals
Execute the benchmark evaluation suite:
```bash
uv run python -m app.evals.run
```
**Verification Checkpoint**:
- Cases `EVAL-005` and `EVAL-006` (adversarial injection) must detect the injection, reject instruction overrides, and achieve `100.0%` for Safety Guardrails and Zero-PII Leakage.

### Step 5: Verify Production RBAC and Dev-Token Lockout
Check `sentinelflow/backend/app/config.py` and `sentinelflow/backend/app/security.py`:
- In development (`ENVIRONMENT != "production"`), `AUTH_ALLOW_DEV_TOKENS=True` permits mock headers (`Authorization: Bearer dev-investigator`).
- In production (`ENVIRONMENT == "production"`), `AUTH_ALLOW_DEV_TOKENS` must default to `False`. When `False`, any request attempting to use a dev token must immediately return `401 Unauthorized` or `403 Forbidden`.
