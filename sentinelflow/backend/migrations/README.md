# Migrations

Alembic migration environment for SentinelFlow backend schema changes.

Common commands:

```bash
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "describe_change"
uv run alembic downgrade -1
```

Recommended workflow:

1. Apply schema: `uv run alembic upgrade head`
2. Optionally seed demo data: `uv run python -m app.db.seed`
3. Validate app readiness and tests.

Fresh database validation should run with step 1 before any seeding to ensure schema boot does not depend on demo data.

Audit table permission hardening (production role example):

1. Grant runtime insert path only:
	GRANT SELECT, INSERT ON TABLE audit_records TO sentinelflow_app;
	REVOKE UPDATE, DELETE ON TABLE audit_records FROM sentinelflow_app;
2. Verify role policy:
	SELECT privilege_type
	FROM information_schema.role_table_grants
	WHERE table_name = 'audit_records' AND grantee = 'sentinelflow_app';
3. Rollback policy change when required:
	GRANT UPDATE, DELETE ON TABLE audit_records TO sentinelflow_app;
