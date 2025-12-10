"""Remove unused tables: bertopic_analysis and editorial_trends

Revision ID: e40ad65afb31
Revises: d30ad65afb30
Create Date: 2025-01-09 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e40ad65afb31'
down_revision: Union[str, None] = 'd30ad65afb30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop bertopic_analysis table (used only by removed trends router)
    op.drop_index(op.f('ix_bertopic_analysis_created_at'), table_name='bertopic_analysis')
    op.drop_index(op.f('ix_bertopic_analysis_analysis_date'), table_name='bertopic_analysis')
    op.drop_table('bertopic_analysis')
    
    # Drop editorial_trends table (not used anywhere)
    op.drop_index('ix_editorial_trends_domain_date_type', table_name='editorial_trends')
    op.drop_index(op.f('ix_editorial_trends_domain'), table_name='editorial_trends')
    op.drop_index(op.f('ix_editorial_trends_analysis_date'), table_name='editorial_trends')
    op.drop_table('editorial_trends')


def downgrade() -> None:
    # Recreate editorial_trends table
    op.create_table('editorial_trends',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('domain', sa.String(length=255), nullable=False),
    sa.Column('analysis_date', sa.Date(), nullable=False),
    sa.Column('trend_type', sa.String(length=50), nullable=False),
    sa.Column('trend_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('time_window_days', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('is_valid', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_editorial_trends_analysis_date'), 'editorial_trends', ['analysis_date'], unique=False)
    op.create_index(op.f('ix_editorial_trends_domain'), 'editorial_trends', ['domain'], unique=False)
    op.create_index('ix_editorial_trends_domain_date_type', 'editorial_trends', ['domain', 'analysis_date', 'trend_type'], unique=False)
    
    # Recreate bertopic_analysis table
    op.create_table('bertopic_analysis',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('analysis_date', sa.Date(), nullable=False),
    sa.Column('time_window_days', sa.Integer(), nullable=False),
    sa.Column('domains_included', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('topics', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('topic_hierarchy', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('topics_over_time', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('visualizations', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('model_parameters', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('is_valid', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_bertopic_analysis_analysis_date'), 'bertopic_analysis', ['analysis_date'], unique=False)
    op.create_index(op.f('ix_bertopic_analysis_created_at'), 'bertopic_analysis', ['created_at'], unique=False)

