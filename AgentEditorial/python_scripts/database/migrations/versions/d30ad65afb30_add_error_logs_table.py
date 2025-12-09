"""Add error_logs table for error tracking and monitoring.

Revision ID: d30ad65afb30
Revises: c3d4e5f6a7b8
Create Date: 2025-12-08 12:22:20.551283

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd30ad65afb30'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ===========================================================================
    # TABLE: error_logs
    # Table de suivi des erreurs pour diagnostic et monitoring
    # ===========================================================================
    op.create_table(
        'error_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        
        # Contexte
        sa.Column('execution_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('domain', sa.Text(), nullable=True),
        sa.Column('agent_name', sa.String(length=100), nullable=True),
        sa.Column('component', sa.String(length=100), nullable=False),  # 'qdrant', 'scraping', 'llm', etc.
        
        # Erreur
        sa.Column('error_type', sa.String(length=100), nullable=False),  # 'AttributeError', 'ValueError', etc.
        sa.Column('error_message', sa.Text(), nullable=False),
        sa.Column('error_traceback', sa.Text(), nullable=True),
        
        # Contexte additionnel
        sa.Column('context', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        
        # Statut
        sa.Column('severity', sa.String(length=20), nullable=False, server_default='error'),  # 'critical', 'error', 'warning'
        sa.Column('is_resolved', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('resolution_note', sa.Text(), nullable=True),
        
        # Métadonnées
        sa.Column('occurrence_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('first_occurrence', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_occurrence', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['execution_id'], ['workflow_executions.execution_id'], ondelete='SET NULL'),
    )
    
    # Indexes
    op.create_index('ix_error_logs_execution_id', 'error_logs', ['execution_id'], unique=False)
    op.create_index('ix_error_logs_domain', 'error_logs', ['domain'], unique=False)
    op.create_index('ix_error_logs_agent_name', 'error_logs', ['agent_name'], unique=False)
    op.create_index('ix_error_logs_component', 'error_logs', ['component'], unique=False)
    op.create_index('ix_error_logs_error_type', 'error_logs', ['error_type'], unique=False)
    op.create_index('ix_error_logs_severity', 'error_logs', ['severity'], unique=False)
    op.create_index('ix_error_logs_is_resolved', 'error_logs', ['is_resolved'], unique=False)
    
    # Composite indexes
    op.create_index('idx_error_component_severity', 'error_logs', ['component', 'severity'], unique=False)
    op.create_index('idx_error_execution', 'error_logs', ['execution_id', 'first_occurrence'], unique=False)
    op.create_index('idx_error_domain', 'error_logs', ['domain', 'first_occurrence'], unique=False)
    op.create_index('idx_error_unresolved', 'error_logs', ['is_resolved', 'severity', 'first_occurrence'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_error_unresolved', table_name='error_logs')
    op.drop_index('idx_error_domain', table_name='error_logs')
    op.drop_index('idx_error_execution', table_name='error_logs')
    op.drop_index('idx_error_component_severity', table_name='error_logs')
    op.drop_index('ix_error_logs_is_resolved', table_name='error_logs')
    op.drop_index('ix_error_logs_severity', table_name='error_logs')
    op.drop_index('ix_error_logs_error_type', table_name='error_logs')
    op.drop_index('ix_error_logs_component', table_name='error_logs')
    op.drop_index('ix_error_logs_agent_name', table_name='error_logs')
    op.drop_index('ix_error_logs_domain', table_name='error_logs')
    op.drop_index('ix_error_logs_execution_id', table_name='error_logs')
    
    # Drop table
    op.drop_table('error_logs')
