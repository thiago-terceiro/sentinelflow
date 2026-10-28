---
name: sentinelflow-security-audit
description: "Audits, validates, and remediates security controls in SentinelFlow. Use when testing OWASP Top 10, LLM Top 10 prompt injection defense, PCI-DSS/GDPR PII redacting, Fernet encryption, cryptographic SHA-256 audit ledger integrity, RBAC dev-token lockout, or scanning for Bandit/Ruff/CVE vulnerabilities."
argument-hint: "compliance, pii, ledger, or rbac"
---

# SentinelFlow Security Audit Skill

## When To Use
- Verifying the 11-control OWASP Top 10 & LLM Top 10 compliance score
- Testing pre-inference PII redacting for PAN, SSN, IBAN, JWT, and API keys
- Validating cryptographic SHA-256 ledger integrity from genesis (0) to head
- Auditing RBAC and verifying dev-token lockouts in production mode

## Procedure

### Step 1: Automated Compliance Scan
```bash
cd sentinelflow/backend
uv run python ../ops/security_compliance_scan.py
```
Assert that 11/11 controls report `[PASS]`.

### Step 2: Pre-Inference PII Scrubbing
Inspect `app/services/trace_safety.py` and verify `redact_text()` masks all credit card PANs, SSNs, IBANs, and API credentials before LLM dispatch.

### Step 3: SHA-256 Hash Chain Integrity
Verify that each audit row links $\text{prev\_hash}$ to the prior $\text{row\_hash}$ and writes serialize under `asyncio.Lock`.

### Step 4: Prompt Injection Evals
```bash
cd sentinelflow/backend
uv run python -m app.evals.run
```
Confirm `EVAL-005` and `EVAL-006` pass with 100% safety guardrail enforcement.
