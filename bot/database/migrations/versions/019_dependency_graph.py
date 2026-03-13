"""Add node_relations table for dependency graph foundation

Revision ID: 019
Revises: 018
Create Date: 2026-03-13

Epic 1.1 — Dependency Graph Foundation
Creates a generic directed-edge table connecting any two nodes
(task, objective, key_result) with explicit relation semantics:
  blocks | depends_on | contributes_to | unlocks
"""
from alembic import op
import sqlalchemy as sa

revision = '019'
down_revision = '018'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'node_relations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('from_type', sa.String(32), nullable=False),
        sa.Column('from_id', sa.Integer(), nullable=False),
        sa.Column('to_type', sa.String(32), nullable=False),
        sa.Column('to_id', sa.Integer(), nullable=False),
        sa.Column('relation_type', sa.String(32), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'user_id', 'from_type', 'from_id', 'to_type', 'to_id', 'relation_type',
            name='uq_node_relation',
        ),
    )
    op.create_index('ix_node_relations_user_id', 'node_relations', ['user_id'])
    op.create_index(
        'ix_node_relations_from', 'node_relations',
        ['user_id', 'from_type', 'from_id'],
    )
    op.create_index(
        'ix_node_relations_to', 'node_relations',
        ['user_id', 'to_type', 'to_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_node_relations_to', table_name='node_relations')
    op.drop_index('ix_node_relations_from', table_name='node_relations')
    op.drop_index('ix_node_relations_user_id', table_name='node_relations')
    op.drop_table('node_relations')
