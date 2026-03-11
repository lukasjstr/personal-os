"""Add iCal sync fields

Revision ID: 018
Revises: 017
Create Date: 2026-03-11
"""
from alembic import op
import sqlalchemy as sa

revision = '018'
down_revision = '017'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('ical_url', sa.Text(), nullable=True))
    op.add_column('calendar_events', sa.Column('external_id', sa.String(512), nullable=True))
    op.add_column('calendar_events', sa.Column('external_source', sa.String(64), nullable=True))
    try:
        op.create_index('ix_calendar_events_external_id', 'calendar_events', ['external_id'])
    except Exception:
        pass


def downgrade():
    try:
        op.drop_index('ix_calendar_events_external_id', 'calendar_events')
    except Exception:
        pass
    op.drop_column('calendar_events', 'external_source')
    op.drop_column('calendar_events', 'external_id')
    op.drop_column('users', 'ical_url')
