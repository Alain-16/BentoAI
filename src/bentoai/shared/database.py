from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase


NAMING_CONVENTION = {
    # An index — makes looking up rows by this column fast.
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    # A uniqueness rule — no two rows may share this value.
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    # A check rule — the value has to satisfy some condition.
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    # A link to a row in another table.
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    # The column that identifies each row uniquely.
    "pk": "pk_%(table_name)s",
}

class Base(DeclarativeBase):

    metadata = MetaData(naming_convention=NAMING_CONVENTION)