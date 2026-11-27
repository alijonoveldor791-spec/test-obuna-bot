"""Store optional administrator-edited post captions."""

import sqlalchemy as sa
from alembic import op

revision = "d460_custom_caption"
down_revision = "c350_simple_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Preserve existing posts while adding optional custom text."""
    op.add_column("tests", sa.Column("custom_caption", sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove the optional post text."""
    op.drop_column("tests", "custom_caption")
