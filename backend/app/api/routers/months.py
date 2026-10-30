from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.api.schemas import ClosedPayload, MonthCreate, MonthRangePayload, MonthUpdate, SettlementPayload, ShareUpdate
from app.api.security import client_of
from app.db.database import get_db
from app.db.models import Month, MonthPerson, MonthSettlement, Person
from app.services.maintenance import audit
from app.services.months import (
    active_people,
    all_month_counts,
    calculate_all_months,
    ensure_open,
    find_month,
    get_or_create_month,
    label_period,
    month_counts,
    month_or_virtual,
    month_settlement,
    new_month,
    next_period,
    participant_ids,
    received_by_month,
    registered_periods,
    reset_shares,
    serialize_month,
    validate_period,
    validate_range,
)
from app.services.periods import REFERENCE_OFFSET_MONTHS, default_period_range, get_period_defaults, reference_period


router = APIRouter()


def registered_month_or_404(db: Session, period: str) -> Month:
    validate_period(period)
    month = find_month(db, period)
    if month is None or period not in registered_periods(db):
        raise HTTPException(404, "Mês não cadastrado.")
    return month


def saved_month(db: Session, period: str) -> dict:
    db.expire_all()
    return serialize_month(db, find_month(db, period))


@router.get("/months")
def list_months(db: Session = Depends(get_db)) -> list[str]:
    return sorted(registered_periods(db), reverse=True)


@router.get("/months/suggestion")
def suggest_month(period: str | None = None, db: Session = Depends(get_db)) -> dict:
    """Prévia do cadastro: mês vigente (ou o próximo livre) com a faixa padrão das Configurações."""
    registered = registered_periods(db)
    if period is None:
        period = datetime.now().strftime("%Y-%m")
        while period in registered:
            period = next_period(period)
    validate_period(period)
    start_day, end_day = get_period_defaults(db)
    start_date, end_date = default_period_range(period, start_day, end_day, REFERENCE_OFFSET_MONTHS)
    return {
        "period": period,
        "reference_period": reference_period(period),
        "start_date": start_date,
        "end_date": end_date,
        "registered": period in registered,
        "people": [person.name for person in active_people(db)],
    }


@router.post("/months", status_code=201)
def create_month(payload: MonthCreate, db: Session = Depends(get_db)) -> dict:
    period = validate_period(payload.period)
    if period in registered_periods(db):
        raise HTTPException(409, f"O mês {label_period(period)} já está cadastrado.")
    month = find_month(db, period)
    if month is None:
        month = new_month(db, period)
        db.add(month)
        db.flush()
    else:
        # Mês criado antes sem cadastro: refaz a divisão com as pessoas ativas de agora.
        reset_shares(db, month)
    if payload.start_date or payload.end_date:
        month.start_date, month.end_date = validate_range(payload.start_date or "", payload.end_date or "")
    else:
        start_day, end_day = get_period_defaults(db)
        month.start_date, month.end_date = default_period_range(period, start_day, end_day, REFERENCE_OFFSET_MONTHS)
    month.registered = True
    db.commit()
    return saved_month(db, period)


@router.patch("/months/{period}")
def update_month(period: str, payload: MonthUpdate, db: Session = Depends(get_db)) -> dict:
    month = registered_month_or_404(db, period)
    ensure_open(month)
    if payload.start_date is not None or payload.end_date is not None:
        month.start_date, month.end_date = validate_range(payload.start_date or month.start_date or "", payload.end_date or month.end_date or "")
    if payload.period and payload.period != period:
        target = validate_period(payload.period)
        if target in registered_periods(db):
            raise HTTPException(409, f"O mês {label_period(target)} já está cadastrado.")
        # Um mês gravado sem cadastro nem registros é descartado para dar lugar a este.
        leftover = db.scalar(select(Month).where(Month.period == target))
        if leftover is not None:
            db.execute(delete(MonthSettlement).where(MonthSettlement.month_id == leftover.id))
            db.execute(delete(MonthPerson).where(MonthPerson.month_id == leftover.id))
            db.execute(delete(Month).where(Month.id == leftover.id))
            db.flush()
        month.period = target
    month.registered = True
    db.commit()
    return saved_month(db, month.period)


@router.delete("/months/{period}", status_code=204)
def delete_month(period: str, request: Request, db: Session = Depends(get_db)) -> None:
    month = registered_month_or_404(db, period)
    if month.closed:
        raise HTTPException(400, "Este mês está fechado e não pode ser excluído.")
    counts = month_counts(db, month.id)
    if any(counts.values()):
        raise HTTPException(
            400,
            f"Este mês possui registros ({counts['entries']} lançamentos, {counts['adjustments']} vales e descontos, "
            f"{counts['payments']} pagamentos) e não pode ser excluído.",
        )
    for model in (MonthSettlement, MonthPerson):
        db.execute(delete(model).where(model.month_id == month.id))
    db.execute(delete(Month).where(Month.id == month.id))
    db.commit()
    audit("excluir mês", "ok", period, client_of(request))


@router.get("/months/{period}")
def get_month(period: str, db: Session = Depends(get_db)) -> dict:
    return serialize_month(db, month_or_virtual(db, period))


@router.put("/months/{period}/range")
def update_month_range(period: str, payload: MonthRangePayload, db: Session = Depends(get_db)) -> dict:
    month = get_or_create_month(db, period)
    ensure_open(month)
    month.start_date, month.end_date = validate_range(payload.start_date, payload.end_date)
    month.registered = True
    db.commit()
    return saved_month(db, period)


@router.put("/months/{period}/closed")
def set_month_closed(period: str, payload: ClosedPayload, db: Session = Depends(get_db)) -> dict:
    month = get_or_create_month(db, period)
    month.closed = payload.closed
    month.registered = True
    db.commit()
    return saved_month(db, period)


@router.put("/months/{period}/settlements/{person_id}")
def set_settlement(period: str, person_id: int, payload: SettlementPayload, db: Session = Depends(get_db)) -> dict:
    month = get_or_create_month(db, period)
    if person_id not in participant_ids(month):
        raise HTTPException(400, "A pessoa escolhida não participa deste mês.")
    if person_id == month.primary_person_id:
        raise HTTPException(400, "A fonte primária já consta como paga.")
    existing = db.scalar(select(MonthSettlement).where(MonthSettlement.month_id == month.id, MonthSettlement.person_id == person_id))
    if payload.received and not existing:
        db.add(MonthSettlement(month_id=month.id, person_id=person_id))
    elif not payload.received and existing:
        db.delete(existing)
    month.registered = True
    db.commit()
    return saved_month(db, period)


@router.put("/months/{period}/shares")
def update_shares(period: str, payload: list[ShareUpdate], db: Session = Depends(get_db)) -> dict:
    month = get_or_create_month(db, period)
    ensure_open(month)
    if not payload or sum(item.percentage_bp for item in payload) != 10_000:
        raise HTTPException(400, "Os percentuais precisam somar 100%.")
    requested = {item.person_id for item in payload}
    if len(requested) != len(payload):
        raise HTTPException(400, "Cada pessoa pode aparecer uma vez só.")
    if {person.id for person in db.scalars(select(Person).where(Person.id.in_(requested)))} != requested:
        raise HTTPException(400, "Uma das pessoas não existe.")
    db.execute(delete(MonthPerson).where(MonthPerson.month_id == month.id))
    db.add_all([MonthPerson(month_id=month.id, **item.model_dump()) for item in payload])
    if month.primary_person_id not in requested:
        month.primary_person_id = None
    month.registered = True
    db.commit()
    return saved_month(db, period)


@router.get("/accounts")
def accounts(db: Session = Depends(get_db)) -> dict:
    summaries = calculate_all_months(db)
    months = list(db.scalars(select(Month).order_by(Month.period.desc()).options(selectinload(Month.shares).selectinload(MonthPerson.person))))
    counts = all_month_counts(db)
    received = received_by_month(db)
    items = []
    for month in months:
        if month.period not in summaries:
            continue
        settlement = month_settlement(month, received.get(month.id, {}))
        summary = summaries[month.period]
        items.append({
            "period": month.period,
            "reference_period": reference_period(month.period),
            "cost_cents": summary["cost_cents"],
            "net_cents": summary["net_cents"],
            "closed": month.closed,
            "start_date": month.start_date,
            "end_date": month.end_date,
            "counts": dict(counts[month.id]),
            "status": settlement["status"],
            "primary_person_id": settlement["primary_person_id"],
            "people": [
                {
                    "person_id": share.person_id,
                    "name": share.person.name,
                    "is_primary": share.person_id == settlement["primary_person_id"],
                    "status": settlement["people"][share.person_id]["status"],
                    "received_at": settlement["people"][share.person_id]["received_at"],
                    "part_cents": summary["people"][share.person_id]["part_cents"],
                }
                for share in month.shares
            ],
        })
    return {"months": items}
