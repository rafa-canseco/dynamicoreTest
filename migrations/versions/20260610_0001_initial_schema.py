from pathlib import Path

from alembic import op

revision = "20260610_0001"
down_revision = None
branch_labels = None
depends_on = None


def _read_sql(filename: str) -> str:
    project_root = Path(__file__).resolve().parents[2]
    return (project_root / "sql" / filename).read_text(encoding="utf-8")


def upgrade() -> None:
    op.execute(_read_sql("001_schema.sql"))
    op.execute(_read_sql("002_functions_triggers.sql"))


def downgrade() -> None:
    op.execute("DROP SCHEMA public CASCADE")
    op.execute("CREATE SCHEMA public")
    op.execute("GRANT ALL ON SCHEMA public TO dynamicore")
    op.execute("GRANT ALL ON SCHEMA public TO public")
