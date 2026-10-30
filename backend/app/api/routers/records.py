"""Lançamentos, vales/descontos e pagamentos de um mês."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.api.schemas import AdjustmentPatch, AdjustmentPayload, EntryPatch, EntryPayload, PaymentPatch, PaymentPayload
from app.db.database import get_db
from app.db.models import Adjustment, Category, Entry, InvoiceDraftItem, Month, Payment
from app.services.months import ensure_open, get_or_create_month, participant_ids


router = APIRouter()
NOT_PARTICIPANT = "A pessoa escolhida não participa deste mês."


def open_month_by_id(db: Session, month_id: int) -> Month:
    month = db.scalar(select(Month).where(Month.id == month_id).options(selectinload(Month.shares)))
    ensure_open(month)
    return month


def check_entry_fields(db: Session, month: Month, data: dict) -> None:
    if "category_slug" in data and db.get(Category, data["category_slug"]) is None:
        raise HTTPException(400, "Categoria inválida.")
    if data.get("paid_by_person_id") is not None and data["paid_by_person_id"] not in participant_ids(month):
        raise HTTPException(400, "A pessoa que pagou não participa deste mês.")


# ---- Lançamentos ----

@router.post("/months/{period}/entries", status_code=201)
def create_entry(period: str, payload: EntryPayload, db: Session = Depends(get_db)) -> dict:
    month = get_or_create_month(db, period)
    ensure_open(month)
    data = payload.model_dump()
    check_entry_fields(db, month, data)
    entry = Entry(month_id=month.id, origin="manual", **data)
    db.add(entry)
    db.commit()
    return {"id": entry.id}


@router.patch("/entries/{entry_id}")
def update_entry(entry_id: int, payload: EntryPatch, db: Session = Depends(get_db)) -> dict:
    entry = db.get(Entry, entry_id)
    if not entry:
        raise HTTPException(404, "Lançamento não encontrado.")
    month = open_month_by_id(db, entry.month_id)
    data = payload.model_dump(exclude_unset=True)
    for key in ("description", "amount_cents", "category_slug"):
        if key in data and data[key] is None:
            raise HTTPException(400, "Preencha descrição, valor e categoria.")
    check_entry_fields(db, month, data)
    for key, value in data.items():
        setattr(entry, key, value)
    db.commit()
    return {"id": entry.id}


@router.delete("/entries/{entry_id}", status_code=204)
def delete_entry(entry_id: int, db: Session = Depends(get_db)) -> None:
    entry = db.get(Entry, entry_id)
    if not entry:
        raise HTTPException(404, "Lançamento não encontrado.")
    open_month_by_id(db, entry.month_id)
    # Itens de fatura apontam para o lançamento que geraram; desvincula antes de excluir.
    db.execute(update(InvoiceDraftItem).where(InvoiceDraftItem.imported_entry_id == entry.id).values(imported_entry_id=None))
    db.delete(entry)
    db.commit()


# ---- Vales e descontos ----

@router.post("/months/{period}/adjustments", status_code=201)
def create_adjustment(period: str, payload: AdjustmentPayload, db: Session = Depends(get_db)) -> dict:
    month = get_or_create_month(db, period)
    ensure_open(month)
    if payload.distribution == "person" and payload.person_id not in participant_ids(month):
        raise HTTPException(400, NOT_PARTICIPANT)
    item = Adjustment(month_id=month.id, **payload.model_dump())
    db.add(item)
    db.commit()
    return {"id": item.id}


@router.patch("/adjustments/{item_id}")
def update_adjustment(item_id: int, payload: AdjustmentPatch, db: Session = Depends(get_db)) -> dict:
    item = db.get(Adjustment, item_id)
    if not item:
        raise HTTPException(404, "Ajuste não encontrado.")
    month = open_month_by_id(db, item.month_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("kind") not in {None, "vale", "desconto"}:
        raise HTTPException(400, "Tipo de ajuste inválido.")
    for key in ("description", "amount_cents"):
        if key in data and data[key] is None:
            raise HTTPException(400, "Preencha descrição e valor.")
    distribution = data.get("distribution") or item.distribution or "proportional"
    kind = data.get("kind") or item.kind
    person_id = data.get("person_id", item.person_id)
    if distribution not in {"proportional", "equal", "person"}:
        raise HTTPException(400, "Forma de desconto inválida.")
    if kind == "vale":
        data["distribution"] = "proportional"
        data["person_id"] = None
    elif distribution == "person":
        if person_id not in participant_ids(month):
            raise HTTPException(400, NOT_PARTICIPANT)
    else:
        data["person_id"] = None
    for key, value in data.items():
        if value is not None or key == "person_id":
            setattr(item, key, value)
    db.commit()
    return {"id": item.id}


@router.delete("/adjustments/{item_id}", status_code=204)
def delete_adjustment(item_id: int, db: Session = Depends(get_db)) -> None:
    item = db.get(Adjustment, item_id)
    if not item:
        raise HTTPException(404, "Ajuste não encontrado.")
    open_month_by_id(db, item.month_id)
    db.delete(item)
    db.commit()


# ---- Pagamentos ----

@router.post("/months/{period}/payments", status_code=201)
def create_payment(period: str, payload: PaymentPayload, db: Session = Depends(get_db)) -> dict:
    month = get_or_create_month(db, period)
    ensure_open(month)
    if payload.person_id not in participant_ids(month):
        raise HTTPException(400, NOT_PARTICIPANT)
    item = Payment(month_id=month.id, **payload.model_dump())
    db.add(item)
    db.commit()
    return {"id": item.id}


@router.patch("/payments/{item_id}")
def update_payment(item_id: int, payload: PaymentPatch, db: Session = Depends(get_db)) -> dict:
    item = db.get(Payment, item_id)
    if not item:
        raise HTTPException(404, "Pagamento não encontrado.")
    month = open_month_by_id(db, item.month_id)
    data = payload.model_dump(exclude_unset=True)
    for key in ("person_id", "amount_cents"):
        if key in data and data[key] is None:
            raise HTTPException(400, "Escolha a pessoa e informe o valor.")
    if "person_id" in data and data["person_id"] not in participant_ids(month):
        raise HTTPException(400, NOT_PARTICIPANT)
    for key, value in data.items():
        setattr(item, key, value)
    db.commit()
    return {"id": item.id}


@router.delete("/payments/{item_id}", status_code=204)
def delete_payment(item_id: int, db: Session = Depends(get_db)) -> None:
    item = db.get(Payment, item_id)
    if not item:
        raise HTTPException(404, "Pagamento não encontrado.")
    open_month_by_id(db, item.month_id)
    db.delete(item)
    db.commit()
