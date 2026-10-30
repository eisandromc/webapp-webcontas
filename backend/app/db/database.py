from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import DATABASE_PATH, DATABASE_URL


class Base(DeclarativeBase):
    pass


DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    future=True,
)


@event.listens_for(engine, "connect")
def _configure_sqlite(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.db import models  # noqa: F401

    Base.metadata.create_all(engine)
    _upgrade_existing_schema()


def _upgrade_existing_schema() -> None:
    inspector = inspect(engine)
    month_columns = {column["name"] for column in inspector.get_columns("months")}
    adjustment_columns = {column["name"] for column in inspector.get_columns("adjustments")}
    people_columns = {column["name"] for column in inspector.get_columns("people")}
    entry_columns = {column["name"] for column in inspector.get_columns("entries")}
    with engine.begin() as connection:
        if "start_date" not in month_columns:
            connection.execute(text("ALTER TABLE months ADD COLUMN start_date VARCHAR(10)"))
        if "end_date" not in month_columns:
            connection.execute(text("ALTER TABLE months ADD COLUMN end_date VARCHAR(10)"))
        if "closed" not in month_columns:
            connection.execute(text("ALTER TABLE months ADD COLUMN closed BOOLEAN NOT NULL DEFAULT 0"))
        if "registered" not in month_columns:
            connection.execute(text("ALTER TABLE months ADD COLUMN registered BOOLEAN NOT NULL DEFAULT 0"))
            # Meses que já têm registros passam a contar como cadastrados.
            connection.execute(text(
                "UPDATE months SET registered = 1 WHERE id IN "
                "(SELECT month_id FROM entries UNION SELECT month_id FROM adjustments UNION SELECT month_id FROM payments)"
            ))
        if "is_primary" not in people_columns:
            connection.execute(text("ALTER TABLE people ADD COLUMN is_primary BOOLEAN NOT NULL DEFAULT 0"))
        if "primary_person_id" not in month_columns:
            connection.execute(text("ALTER TABLE months ADD COLUMN primary_person_id INTEGER REFERENCES people(id)"))
            # Meses existentes herdam a fonte primária atual (era assim que eram calculados).
            connection.execute(text(
                "UPDATE months SET primary_person_id = "
                "(SELECT id FROM people WHERE is_primary = 1 AND active = 1 ORDER BY position LIMIT 1)"
            ))
        if "paid_by_person_id" not in entry_columns:
            connection.execute(text("ALTER TABLE entries ADD COLUMN paid_by_person_id INTEGER REFERENCES people(id)"))
        if "distribution" not in adjustment_columns:
            connection.execute(text("ALTER TABLE adjustments ADD COLUMN distribution VARCHAR(20) NOT NULL DEFAULT 'proportional'"))
        if "person_id" not in adjustment_columns:
            connection.execute(text("ALTER TABLE adjustments ADD COLUMN person_id INTEGER REFERENCES people(id)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_adjustments_person_id ON adjustments (person_id)"))
        connection.execute(text("UPDATE months SET start_date = date(period || '-01', '-1 month') WHERE start_date IS NULL"))
        connection.execute(text("UPDATE months SET end_date = date(period || '-01', '-1 day') WHERE end_date IS NULL"))
