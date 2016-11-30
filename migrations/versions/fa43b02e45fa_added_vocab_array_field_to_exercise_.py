"""added vocab array field to Exercise table

Revision ID: fa43b02e45fa
Revises: 50a9074e5d50
Create Date: 2016-11-30 11:43:03.401856

"""

# revision identifiers, used by Alembic.
revision = 'fa43b02e45fa'
down_revision = '50a9074e5d50'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column('exercises', sa.Column('vocab', postgresql.ARRAY(sa.String()), nullable=True))
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('exercises', 'vocab')
    ### end Alembic commands ###
