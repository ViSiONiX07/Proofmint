from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from pydantic import SecretStr

from app.core.config import Settings
from app.core.database import DatabaseNotConfiguredError
from app.models import Base, CandidateRule, GuidelineDocument, ImportedFact, ImportedTerm


API_ROOT = Path(__file__).resolve().parents[1]


def test_database_is_optional_and_missing_configuration_is_clear(monkeypatch):
    import app.core.database as database

    unconfigured = Settings(_env_file=None)
    assert unconfigured.get_database_url() is None
    monkeypatch.setattr(database, "settings", unconfigured)
    database.dispose_database()
    with pytest.raises(DatabaseNotConfiguredError, match="Set DATABASE_URL or POSTGRES_SERVER"):
        database.get_engine()
    database.dispose_database()


def test_postgres_url_uses_psycopg_and_keeps_password_masked():
    settings = Settings(
        _env_file=None,
        POSTGRES_SERVER="localhost",
        POSTGRES_USER="proofmint-user",
        POSTGRES_PASSWORD=SecretStr("local-secret"),
        POSTGRES_DB="proofmint",
    )
    url = settings.get_database_url()
    assert url is not None
    assert url.drivername == "postgresql+psycopg"
    assert url.password == "local-secret"
    assert "local-secret" not in str(url)
    assert "local-secret" not in repr(settings)


def test_database_url_accepts_postgresql_scheme_and_rejects_other_databases():
    postgres = Settings(_env_file=None, DATABASE_URL=SecretStr("postgresql://user:pass@localhost/proofmint"))
    assert postgres.get_database_url().drivername == "postgresql+psycopg"
    other = Settings(_env_file=None, DATABASE_URL=SecretStr("sqlite:///not-allowed.db"))
    with pytest.raises(ValueError, match="must use PostgreSQL"):
        other.get_database_url()
    wrong_driver = Settings(
        _env_file=None,
        DATABASE_URL=SecretStr("postgresql+asyncpg://user:pass@localhost/proofmint"),
    )
    with pytest.raises(ValueError, match="Psycopg 3 driver"):
        wrong_driver.get_database_url()


def test_engine_creation_is_lazy_and_does_not_connect(monkeypatch):
    import app.core.database as database

    configured = Settings(
        _env_file=None,
        DATABASE_URL=SecretStr("postgresql+psycopg://proofmint:local-only@127.0.0.1:65432/proofmint"),
    )
    database.dispose_database()
    monkeypatch.setattr(database, "settings", configured)
    try:
        engine = database.get_engine()
        assert engine.url.drivername == "postgresql+psycopg"
        # Engine construction is local; a connection is attempted only on connect/session use.
        assert engine.pool is not None
    finally:
        database.dispose_database()


def test_initial_models_are_postgresql_workflow_tables_with_constraints():
    assert {"guideline_documents", "candidate_rules", "imported_facts", "imported_terms",
            "audit_runs", "audit_findings", "finding_decisions", "clearance_records"} <= set(Base.metadata.tables)
    assert GuidelineDocument.__table__.c.source_sha256.type.length == 64
    assert any("source_end_offset > source_start_offset" in str(item.sqltext) for item in CandidateRule.__table__.constraints if hasattr(item, "sqltext"))
    assert any("source_row_number > 0" in str(item.sqltext) for item in ImportedFact.__table__.constraints if hasattr(item, "sqltext"))
    assert any("source_row_number > 0" in str(item.sqltext) for item in ImportedTerm.__table__.constraints if hasattr(item, "sqltext"))


@pytest.mark.parametrize("model", [CandidateRule, ImportedFact, ImportedTerm])
def test_new_rules_and_imports_default_to_pending_review(model):
    column = model.__table__.c.review_status
    assert column.nullable is False
    assert column.default.arg == "pending_review"
    assert str(column.server_default.arg).strip("()'") == "pending_review"


@pytest.mark.parametrize("model", [ImportedFact, ImportedTerm])
def test_imported_records_require_source_provenance(model):
    columns = model.__table__.c
    assert columns.source_filename.nullable is False
    assert columns.source_row_number.nullable is False
    assert columns.source_sha256.nullable is False
    assert columns.imported_at.nullable is False


def test_alembic_config_discovers_baseline_without_database_credentials():
    config_path = API_ROOT / "alembic.ini"
    config = Config(str(config_path))
    script = ScriptDirectory.from_config(config)
    assert config.get_main_option("sqlalchemy.url") == ""
    assert script.get_heads() == ["0003_session_workspaces"]
    revision = script.get_revision("0001_postgresql_persistence")
    assert revision is not None
    assert revision.down_revision is None
    audit_revision = script.get_revision("0002_persisted_audits")
    assert audit_revision is not None
    assert audit_revision.down_revision == "0001_postgresql_persistence"
