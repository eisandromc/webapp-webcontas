from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session


@pytest.fixture()
def db(tmp_path, monkeypatch):
    from app.api.routers import months as month_routes
    from app.db.models import Base, Category, Person

    # Exclusões de mês não devem gravar na auditoria real.
    monkeypatch.setattr(month_routes, "audit", lambda *args, **kwargs: None)
    engine = create_engine(f"sqlite:///{(tmp_path / 'months.db').as_posix()}")
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        session.add_all([
            Person(name="Ana", position=0, is_primary=True),
            Person(name="Bia", position=1),
            Category(slug="contas", name="Contas", color="#000", position=0),
        ])
        session.commit()
        yield session


REQUEST = SimpleNamespace(client=None)


def test_register_month_uses_defaults_and_blocks_duplicates(db):
    from app.api.routers.months import create_month, list_months, suggest_month
    from app.api.schemas import MonthCreate

    suggestion = suggest_month("2026-11", db)
    assert suggestion["reference_period"] == "2026-10"
    assert (suggestion["start_date"], suggestion["end_date"]) == ("2026-10-01", "2026-10-31")

    month = create_month(MonthCreate(period="2026-11"), db)
    assert month["registered"] is True
    assert [person["name"] for person in month["people"]] == ["Ana", "Bia"]
    assert list_months(db) == ["2026-11"]
    with pytest.raises(HTTPException) as error:
        create_month(MonthCreate(period="2026-11"), db)
    assert error.value.status_code == 409


def test_browsing_a_month_does_not_register_it(db):
    from app.api.routers.months import get_month, list_months

    assert get_month("2027-01", db)["registered"] is False
    assert list_months(db) == []


def test_edit_moves_records_and_refuses_closed_or_taken_months(db):
    from app.api.routers.records import create_entry
    from app.api.routers.months import create_month, set_month_closed, update_month
    from app.api.schemas import ClosedPayload, EntryPayload, MonthCreate, MonthUpdate

    create_month(MonthCreate(period="2026-10"), db)
    create_month(MonthCreate(period="2026-11"), db)
    create_entry("2026-11", EntryPayload(description="Luz", amount_cents=10_000, category_slug="contas"), db)

    moved = update_month("2026-11", MonthUpdate(period="2026-12", start_date="2026-11-05", end_date="2026-12-04"), db)
    assert (moved["period"], moved["start_date"], moved["end_date"]) == ("2026-12", "2026-11-05", "2026-12-04")
    assert [entry["description"] for entry in moved["entries"]] == ["Luz"]
    with pytest.raises(HTTPException) as error:
        update_month("2026-12", MonthUpdate(period="2026-10"), db)
    assert error.value.status_code == 409
    set_month_closed("2026-12", ClosedPayload(closed=True), db)
    with pytest.raises(HTTPException):
        update_month("2026-12", MonthUpdate(start_date="2026-11-01"), db)


def test_only_open_months_without_records_can_be_deleted(db):
    from app.api.routers.records import create_entry, delete_entry
    from app.api.routers.months import create_month, delete_month, list_months, set_month_closed
    from app.api.schemas import ClosedPayload, EntryPayload, MonthCreate

    create_month(MonthCreate(period="2026-11"), db)
    entry = create_entry("2026-11", EntryPayload(description="Água", amount_cents=5_000, category_slug="contas"), db)
    with pytest.raises(HTTPException) as error:
        delete_month("2026-11", REQUEST, db)
    assert "registros" in error.value.detail
    assert list_months(db) == ["2026-11"]

    delete_entry(entry["id"], db)
    set_month_closed("2026-11", ClosedPayload(closed=True), db)
    with pytest.raises(HTTPException) as error:
        delete_month("2026-11", REQUEST, db)
    assert "fechado" in error.value.detail

    set_month_closed("2026-11", ClosedPayload(closed=False), db)
    delete_month("2026-11", REQUEST, db)
    assert list_months(db) == []
    with pytest.raises(HTTPException) as error:
        delete_month("2026-11", REQUEST, db)
    assert error.value.status_code == 404
