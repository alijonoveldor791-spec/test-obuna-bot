"""Retire paused/scheduled tests and enforce one attempt."""

from alembic import op

revision = "c350_simple_lifecycle"
down_revision = "b240_four_digit_codes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Close legacy paused tests without publishing them or deleting results."""
    op.execute("UPDATE tests SET status = 'closed' WHERE status = 'paused'")
    op.execute("UPDATE tests SET max_attempts = 1, scheduled_at = NULL")
    op.create_check_constraint("ck_tests_single_attempt", "tests", "max_attempts = 1")
    op.create_check_constraint(
        "ck_tests_lifecycle", "tests", "status IN ('draft','active','closed')"
    )


def downgrade() -> None:
    """Remove constraints; historical paused/schedule values cannot be restored."""
    op.drop_constraint("ck_tests_lifecycle", "tests", type_="check")
    op.drop_constraint("ck_tests_single_attempt", "tests", type_="check")
