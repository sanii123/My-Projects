"""Declarative base shared by every ORM model.

Every model module must be imported by app/db/models/__init__.py so that
(a) Base.metadata has a complete picture for Alembic autogenerate, and
(b) string-based relationship() targets (e.g. Mapped["Message"]) can resolve
across modules when mappers configure.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
