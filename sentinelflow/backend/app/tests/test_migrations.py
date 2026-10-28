from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def _get_alembic_config() -> Config:
    repo_root = Path(__file__).resolve().parents[2]
    ini_path = repo_root / "alembic.ini"
    assert ini_path.is_file(), f"alembic.ini not found at {ini_path}"
    config = Config(str(ini_path))
    config.set_main_option("script_location", str(repo_root / "migrations"))
    return config


def test_alembic_migrations_have_single_head() -> None:
    config = _get_alembic_config()
    script = ScriptDirectory.from_config(config)
    heads = script.get_heads()
    assert len(heads) == 1, f"Expected exactly one Alembic head revision, found: {heads}"
    assert heads[0] == "20261022_000006"


def test_alembic_revisions_chain_is_contiguous_and_reversible() -> None:
    config = _get_alembic_config()
    script = ScriptDirectory.from_config(config)
    revisions = list(script.walk_revisions())
    assert len(revisions) >= 4, "Expected at least 4 migration revisions."

    base = script.get_base()
    assert base == "20260826_000001"

    for rev in revisions:
        assert rev.revision is not None
        # Verify both upgrade and downgrade entrypoints exist on each script
        module = rev.module
        assert hasattr(module, "upgrade") and callable(module.upgrade)
        assert hasattr(module, "downgrade") and callable(module.downgrade)
