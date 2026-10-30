import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session


@pytest.fixture()
def db(tmp_path):
    from app.db.models import Base, Category, Person

    engine = create_engine(f"sqlite:///{(tmp_path / 'rules.db').as_posix()}")
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        session.add_all([
            Person(name="Ana", position=0, is_primary=True),
            Person(name="Bia", position=1),
            Person(name="Caio", position=2),
            Category(slug="contas", name="Contas", color="#000", position=0),
        ])
        session.commit()
        yield session


def entry(description="Luz", amount=9_000):
    from app.api.schemas import EntryPayload

    return EntryPayload(description=description, amount_cents=amount, category_slug="contas")


def parts(month):
    return {person["name"]: person["part_cents"] for person in month["people"]}


def test_people_changes_only_affect_open_months(db):
    from app.api.routers.months import get_month, set_month_closed
    from app.api.routers.people import update_person
    from app.api.routers.records import create_entry
    from app.api.schemas import ClosedPayload, PersonUpdate

    create_entry("2026-10", entry(), db)
    create_entry("2026-11", entry(), db)
    set_month_closed("2026-10", ClosedPayload(closed=True), db)

    update_person(3, PersonUpdate(active=False), db)

    assert parts(get_month("2026-10", db)) == {"Ana": 3_001, "Bia": 3_000, "Caio": 2_999}
    assert parts(get_month("2026-11", db)) == {"Ana": 4_500, "Bia": 4_500}


def test_primary_change_keeps_closed_month_primary(db):
    from app.api.routers.months import get_month, set_month_closed
    from app.api.routers.people import update_person
    from app.api.routers.records import create_entry
    from app.api.schemas import ClosedPayload, PersonUpdate

    create_entry("2026-10", entry(), db)
    create_entry("2026-11", entry(), db)
    set_month_closed("2026-10", ClosedPayload(closed=True), db)

    update_person(2, PersonUpdate(is_primary=True), db)

    assert get_month("2026-10", db)["primary_person_id"] == 1
    assert get_month("2026-11", db)["primary_person_id"] == 2


def test_stored_percentages_drive_the_split(db):
    from app.api.routers.months import update_shares
    from app.api.routers.records import create_entry
    from app.api.schemas import ShareUpdate

    create_entry("2026-11", entry(amount=10_000), db)
    month = update_shares("2026-11", [ShareUpdate(person_id=1, percentage_bp=5_000, position=0), ShareUpdate(person_id=2, percentage_bp=5_000, position=1)], db)
    assert parts(month) == {"Ana": 5_000, "Bia": 5_000}
    assert [person["percentage_bp"] for person in month["people"]] == [5_000, 5_000]


def test_closed_month_refuses_changes(db):
    from app.api.routers.months import set_month_closed, update_month_range
    from app.api.routers.records import create_entry, create_payment, delete_entry, update_entry
    from app.api.schemas import ClosedPayload, EntryPatch, MonthRangePayload, PaymentPayload

    created = create_entry("2026-11", entry(), db)
    set_month_closed("2026-11", ClosedPayload(closed=True), db)
    attempts = [
        lambda: create_entry("2026-11", entry("Água"), db),
        lambda: update_entry(created["id"], EntryPatch(description="Outra"), db),
        lambda: delete_entry(created["id"], db),
        lambda: create_payment("2026-11", PaymentPayload(person_id=2, amount_cents=100), db),
        lambda: update_month_range("2026-11", MonthRangePayload(start_date="2026-10-01", end_date="2026-10-31"), db),
    ]
    for attempt in attempts:
        with pytest.raises(HTTPException) as error:
            attempt()
        assert "fechado" in error.value.detail


def test_reading_a_month_writes_nothing(db):
    from app.api.routers.months import get_month
    from app.db.models import Month, MonthPerson

    data = get_month("2027-03", db)
    assert data["registered"] is False
    assert [person["name"] for person in data["people"]] == ["Ana", "Bia", "Caio"]
    db.rollback()
    assert db.scalar(select(func.count()).select_from(Month)) == 0
    assert db.scalar(select(func.count()).select_from(MonthPerson)) == 0


def test_edits_validate_references(db):
    from app.api.routers.records import create_entry, create_payment, update_entry
    from app.api.routers.people import create_person
    from app.api.routers.months import set_month_closed
    from app.api.schemas import ClosedPayload, EntryPatch, PaymentPayload, PersonCreate

    created = create_entry("2026-11", entry(), db)
    with pytest.raises(HTTPException) as error:
        update_entry(created["id"], EntryPatch(category_slug="nao-existe"), db)
    assert error.value.status_code == 400
    with pytest.raises(HTTPException):
        update_entry(created["id"], EntryPatch(paid_by_person_id=999), db)

    # Pessoa nova entra só nos meses abertos; meses fechados continuam sem ela.
    set_month_closed("2026-11", ClosedPayload(closed=True), db)
    set_month_closed("2026-11", ClosedPayload(closed=False), db)
    newcomer = create_person(PersonCreate(name="Davi"), db)
    create_entry("2026-12", entry(), db)
    create_payment("2026-12", PaymentPayload(person_id=newcomer["id"], amount_cents=100), db)


def test_request_guard_blocks_foreign_hosts_and_origins():
    from app.api.security import is_allowed_host, request_guard

    assert is_allowed_host("localhost:8000")
    assert is_allowed_host("192.168.0.10:8000")
    assert is_allowed_host("[::1]:8000")
    assert not is_allowed_host("evil.example.com:8000")

    app = FastAPI()
    app.middleware("http")(request_guard)

    @app.post("/api/x")
    def write() -> dict:
        return {"ok": True}

    client = TestClient(app)
    assert client.post("/api/x").status_code == 200
    assert client.post("/api/x", headers={"Origin": "http://testserver"}).status_code == 200
    assert client.post("/api/x", headers={"Origin": "http://localhost:5173"}).status_code == 200
    assert client.post("/api/x", headers={"Origin": "https://evil.example.com"}).status_code == 403
    assert client.post("/api/x", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert client.post("/api/x", headers={"Host": "evil.example.com"}).status_code == 400
