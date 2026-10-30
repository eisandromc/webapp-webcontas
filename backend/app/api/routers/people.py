from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.api.schemas import PersonCreate, PersonUpdate
from app.db.database import get_db
from app.db.models import Adjustment, Entry, Month, MonthPerson, MonthSettlement, Payment, Person
from app.services.months import resync_open_months


router = APIRouter()


def serialize_person(person: Person) -> dict:
    return {"id": person.id, "name": person.name, "active": person.active, "position": person.position, "is_primary": person.is_primary}


@router.get("/people")
def list_people(db: Session = Depends(get_db)) -> list[dict]:
    return [serialize_person(person) for person in db.scalars(select(Person).order_by(Person.position))]


@router.post("/people", status_code=201)
def create_person(payload: PersonCreate, db: Session = Depends(get_db)) -> dict:
    position = db.scalar(select(func.max(Person.position)))
    person = Person(name=payload.name.strip(), position=(position or 0) + 1, active=True, is_primary=False)
    db.add(person)
    db.flush()
    resync_open_months(db)
    db.commit()
    db.refresh(person)
    return serialize_person(person)


@router.patch("/people/{person_id}")
def update_person(person_id: int, payload: PersonUpdate, db: Session = Depends(get_db)) -> dict:
    person = db.get(Person, person_id)
    if not person:
        raise HTTPException(404, "Pessoa não encontrada.")
    before = (person.active, person.is_primary)
    if payload.name is not None:
        person.name = payload.name.strip()
    if payload.active is not None:
        if not payload.active:
            active_count = db.scalar(select(func.count()).select_from(Person).where(Person.active.is_(True))) or 0
            if active_count <= 1 and person.active:
                raise HTTPException(400, "Mantenha ao menos uma pessoa ativa.")
        person.active = payload.active
        if not payload.active:
            person.is_primary = False
    if payload.is_primary is not None:
        if payload.is_primary:
            if not person.active:
                raise HTTPException(400, "Somente uma pessoa ativa pode ser a fonte primária.")
            db.execute(update(Person).where(Person.id != person.id).values(is_primary=False))
        person.is_primary = payload.is_primary
    db.flush()
    if (person.active, person.is_primary) != before:
        resync_open_months(db)
    db.commit()
    return serialize_person(person)


@router.delete("/people/{person_id}", status_code=204)
def delete_person(person_id: int, db: Session = Depends(get_db)) -> None:
    person = db.get(Person, person_id)
    if not person:
        raise HTTPException(404, "Pessoa não encontrada.")
    if person.is_primary:
        raise HTTPException(400, "A fonte primária não pode ser excluída. Marque outra pessoa antes.")
    others = list(db.scalars(select(Person).where(Person.id != person_id)))
    if not others:
        raise HTTPException(400, "Mantenha ao menos uma pessoa.")
    if person.active and not any(other.active for other in others):
        raise HTTPException(400, "Mantenha ao menos uma pessoa ativa.")
    used = (
        (db.scalar(select(func.count()).select_from(Payment).where(Payment.person_id == person_id)) or 0)
        + (db.scalar(select(func.count()).select_from(Entry).where(Entry.paid_by_person_id == person_id)) or 0)
        + (db.scalar(select(func.count()).select_from(Adjustment).where(Adjustment.person_id == person_id)) or 0)
    )
    if used:
        raise HTTPException(400, "Esta pessoa possui pagamentos ou lançamentos registrados. Desative-a em vez de excluir.")
    in_closed = (
        (db.scalar(select(func.count()).select_from(MonthPerson).join(Month).where(MonthPerson.person_id == person_id, Month.closed.is_(True))) or 0)
        + (db.scalar(select(func.count()).select_from(Month).where(Month.primary_person_id == person_id, Month.closed.is_(True))) or 0)
    )
    if in_closed:
        raise HTTPException(400, "Esta pessoa participa de meses fechados. Desative-a em vez de excluir.")
    db.execute(delete(MonthSettlement).where(MonthSettlement.person_id == person_id))
    db.execute(delete(MonthPerson).where(MonthPerson.person_id == person_id))
    db.execute(update(Month).where(Month.primary_person_id == person_id).values(primary_person_id=None))
    db.delete(person)
    db.flush()
    resync_open_months(db)
    db.commit()
