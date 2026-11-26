"""Four digit codes, reusable after closing a test."""

import sqlalchemy as sa
from alembic import op

revision = "b240_four_digit_codes"
down_revision = "a9f7f07f0ac3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Validate legacy data before changing constraints; never silently recode tests."""
    connection = op.get_bind()
    invalid = connection.scalar(
        sa.text("SELECT count(*) FROM tests WHERE code !~ '^[1-9][0-9]{3}$'")
    )
    if invalid:
        raise RuntimeError("Legacy test codes must be mapped to 1000-9999 before migration.")
    op.drop_constraint("tests_code_key", "tests", type_="unique")
    op.alter_column("tests", "code", type_=sa.String(4), existing_type=sa.String(32))
    op.create_check_constraint("ck_tests_code_digits", "tests", "code ~ '^[1-9][0-9]{3}$'")
    op.create_index(
        "uq_tests_open_code",
        "tests",
        ["code"],
        unique=True,
        postgresql_where=sa.text("status IN ('draft','active')"),
    )


def downgrade() -> None:
    """Restore global uniqueness only if reused codes do not conflict."""
    op.drop_index("uq_tests_open_code", table_name="tests")
    op.drop_constraint("ck_tests_code_digits", "tests", type_="check")
    op.alter_column("tests", "code", type_=sa.String(32), existing_type=sa.String(4))
    op.create_unique_constraint("tests_code_key", "tests", ["code"])
