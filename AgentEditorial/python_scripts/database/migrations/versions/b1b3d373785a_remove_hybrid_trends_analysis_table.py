"""remove_hybrid_trends_analysis_table

Revision ID: b1b3d373785a
Revises: e40ad65afb31
Create Date: 2025-12-10 15:26:34.050643

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1b3d373785a'
down_revision: Union[str, None] = 'e40ad65afb31'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop hybrid_trends_analysis table (not used anywhere, no model defined)
    # First, drop any indexes if they exist
    op.execute("DROP INDEX IF EXISTS ix_hybrid_trends_analysis_created_at")
    op.execute("DROP INDEX IF EXISTS ix_hybrid_trends_analysis_analysis_date")
    op.execute("DROP INDEX IF EXISTS ix_hybrid_trends_analysis_client_domain")
    op.execute("DROP INDEX IF EXISTS ix_hybrid_trends_client_date")
    
    # Drop the table (CASCADE will handle any foreign key constraints)
    op.drop_table('hybrid_trends_analysis', if_exists=True)


def downgrade() -> None:
    # Recreate hybrid_trends_analysis table (if needed for rollback)
    # Note: This is a placeholder - the original structure is unknown
    # If rollback is needed, the original table structure should be restored from backup
    op.create_table(
        'hybrid_trends_analysis',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_hybrid_trends_analysis_created_at', 'hybrid_trends_analysis', ['created_at'], unique=False)

