"""merge multiple heads

Revision ID: aa98bd461802
Revises: b1b3d373785a, g60ad65afb33
Create Date: 2025-12-15 15:04:24.118766

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aa98bd461802'
down_revision: Union[str, None] = ('b1b3d373785a', 'g60ad65afb33')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

