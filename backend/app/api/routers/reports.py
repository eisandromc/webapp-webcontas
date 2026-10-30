"""Leituras consolidadas: histórico, todos os lançamentos e painel."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.database import get_db
from app.db.models import Adjustment, Entry, Month, MonthPerson, Payment
from app.services.dashboard import build_dashboard
from app.services.months import calculate_all_months
from app.services.pdf_parser import normalize_merchant
from app.services.periods import month_range


router = APIRouter()


@router.get("/history")
def history(year: int | None = None, db: Session = Depends(get_db)) -> dict:
    summaries = calculate_all_months(db)
    months = {
        month.period: month
        for month in db.scalars(select(Month).where(Month.period.in_(list(summaries))).options(selectinload(Month.shares).selectinload(MonthPerson.person)))
    }
    items = []
    for period, summary in summaries.items():
        if year is not None and not period.startswith(str(year)):
            continue
        month = months[period]
        start_date, end_date = month_range(db, month)
        items.append(
            {
                "period": period,
                "start_date": start_date,
                "end_date": end_date,
                **{key: value for key, value in summary.items() if key != "people"},
                "people": [
                    {"person_id": share.person_id, "name": share.person.name, **summary["people"][share.person_id]}
                    for share in month.shares
                ],
            }
        )
    return {"months": items}


@router.get("/ledger")
def ledger(
    period: str | None = None,
    kind: str | None = None,
    category: str | None = None,
    q: str | None = None,
    limit: int = Query(500, ge=1, le=2000),
    db: Session = Depends(get_db),
) -> dict:
    month_rows = list(db.scalars(select(Month).order_by(Month.period.desc())))
    month_by_id = {month.id: month.period for month in month_rows}
    allowed_month_ids = {month.id for month in month_rows if period is None or month.period == period}
    items: list[dict] = []

    if kind in {None, "entry"}:
        entries = list(db.scalars(select(Entry).where(Entry.month_id.in_(allowed_month_ids)))) if allowed_month_ids else []
        for entry in entries:
            if category and entry.category_slug != category:
                continue
            items.append({
                "id": entry.id,
                "kind": "entry",
                "period": month_by_id[entry.month_id],
                "date": entry.date,
                "description": entry.description,
                "amount_cents": entry.amount_cents,
                "category_slug": entry.category_slug,
                "origin": entry.origin,
                "person_name": None,
            })
    if kind in {None, "adjustment"}:
        adjustments = list(db.scalars(select(Adjustment).where(Adjustment.month_id.in_(allowed_month_ids)).options(selectinload(Adjustment.person)))) if allowed_month_ids else []
        for item in adjustments:
            items.append({
                "id": item.id,
                "kind": item.kind,
                "period": month_by_id[item.month_id],
                "date": None,
                "description": item.description,
                "amount_cents": item.amount_cents,
                "category_slug": None,
                "origin": item.distribution or "proportional",
                "person_name": item.person.name if item.person else None,
            })
    if kind in {None, "payment"}:
        payments = list(db.scalars(select(Payment).where(Payment.month_id.in_(allowed_month_ids)).options(selectinload(Payment.person)))) if allowed_month_ids else []
        for item in payments:
            items.append({
                "id": item.id,
                "kind": "payment",
                "period": month_by_id[item.month_id],
                "date": item.date,
                "description": item.note or "Pagamento registrado",
                "amount_cents": item.amount_cents,
                "category_slug": None,
                "origin": "manual",
                "person_name": item.person.name,
            })
    if q:
        needle = normalize_merchant(q)
        items = [item for item in items if needle in normalize_merchant(f"{item['description']} {item.get('person_name') or ''}")]
    items.sort(key=lambda item: (item["period"], item["date"] or "", item["id"]), reverse=True)
    return {"items": items[:limit], "total": len(items)}


@router.get("/dashboard")
def dashboard(months: int = Query(12, ge=3, le=36), db: Session = Depends(get_db)) -> dict:
    return build_dashboard(db, months)
