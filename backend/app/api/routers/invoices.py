from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.schemas import InvoiceImportPayload, InvoiceItemPatch
from app.config import MAX_UPLOAD_BYTES
from app.db.database import get_db
from app.db.models import Category, Entry, Invoice, InvoiceDraftItem, MerchantRule
from app.services.invoices import duplicate_item_ids, invoice_period_bounds, serialize_invoice
from app.services.months import ensure_open, get_or_create_month, participant_ids
from app.services.pdf_parser import PARSER_VERSION, normalize_merchant, parse_invoice, suggest_category
from app.services.periods import month_range
from app.services.secrets import SecretStoreError, get_pdf_password


router = APIRouter()


def load_invoice(db: Session, invoice_id: int) -> Invoice | None:
    return db.scalar(select(Invoice).where(Invoice.id == invoice_id).options(selectinload(Invoice.items)))


@router.post("/invoices/analyze")
async def analyze_invoice(period: str | None = Query(None), file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict:
    start_date, end_date = invoice_period_bounds(db, period)
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "O PDF excede o limite de 15 MB.")
    if not data.startswith(b"%PDF"):
        raise HTTPException(400, "Envie um arquivo PDF válido.")
    try:
        password = get_pdf_password()
    except SecretStoreError as exc:
        raise HTTPException(400, str(exc)) from exc
    if password is None:
        raise HTTPException(400, "Configure a senha do PDF antes de analisar a fatura.")
    digest = hashlib.sha256(data).hexdigest()
    existing = db.scalar(select(Invoice).where(Invoice.file_hash == digest).options(selectinload(Invoice.items)))
    if existing:
        if existing.imported_at is None:
            for item in existing.items:
                item.included = False
            db.commit()
        return serialize_invoice(existing, start_date, end_date, db=db)
    try:
        parsed = parse_invoice(data, password)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    invoice = Invoice(
        file_hash=parsed["file_hash"],
        filename=(file.filename or "fatura.pdf")[:180],
        parser_version=PARSER_VERSION,
        total_cents=parsed["total_cents"],
        parsed_sum_cents=parsed["parsed_sum_cents"],
    )
    db.add(invoice)
    db.flush()
    rules = {rule.normalized: rule.category_slug for rule in db.scalars(select(MerchantRule))}
    for index, item in enumerate(parsed["items"]):
        normalized = normalize_merchant(item.description)
        category = rules.get(normalized, suggest_category(item.description))
        db.add(
            InvoiceDraftItem(
                invoice_id=invoice.id,
                line_index=index,
                date=item.date,
                description=item.description,
                amount_cents=item.amount_cents,
                installment_current=item.installment_current,
                installment_total=item.installment_total,
                category_slug=category,
                included=False,
                suggested_exclude=item.suggested_exclude,
                confidence=item.confidence,
            )
        )
    db.commit()
    return serialize_invoice(load_invoice(db, invoice.id), start_date, end_date, db=db)


@router.get("/invoice-drafts/{invoice_id}")
def get_invoice_draft(invoice_id: int, period: str | None = Query(None), db: Session = Depends(get_db)) -> dict:
    invoice = load_invoice(db, invoice_id)
    if not invoice:
        raise HTTPException(404, "Fatura não encontrada.")
    return serialize_invoice(invoice, *invoice_period_bounds(db, period), db=db)


@router.patch("/invoice-drafts/{invoice_id}/items/{item_id}")
def update_invoice_item(
    invoice_id: int,
    item_id: int,
    payload: InvoiceItemPatch,
    period: str | None = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    item = db.scalar(select(InvoiceDraftItem).where(InvoiceDraftItem.id == item_id, InvoiceDraftItem.invoice_id == invoice_id))
    if not item:
        raise HTTPException(404, "Item não encontrado.")
    if payload.category_slug is not None and db.get(Category, payload.category_slug) is None:
        raise HTTPException(400, "Categoria inválida.")
    previous_category = item.category_slug
    for key, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(item, key, value)
    if payload.category_slug and payload.category_slug != previous_category:
        normalized = normalize_merchant(item.description)
        if normalized:
            rule = db.scalar(select(MerchantRule).where(MerchantRule.normalized == normalized))
            if rule:
                rule.category_slug = payload.category_slug
            else:
                db.add(MerchantRule(normalized=normalized, category_slug=payload.category_slug))
    db.commit()
    return serialize_invoice(load_invoice(db, invoice_id), *invoice_period_bounds(db, period), db=db)


@router.post("/invoice-drafts/{invoice_id}/import")
def import_invoice(invoice_id: int, payload: InvoiceImportPayload, db: Session = Depends(get_db)) -> dict:
    invoice = load_invoice(db, invoice_id)
    if not invoice:
        raise HTTPException(404, "Fatura não encontrada.")
    month = get_or_create_month(db, payload.period)
    ensure_open(month)
    start_date, end_date = month_range(db, month)
    if payload.paid_by_person_id is not None and payload.paid_by_person_id not in participant_ids(month):
        raise HTTPException(400, "A pessoa que pagou não participa deste mês.")
    inserted = 0
    ignored = 0
    outside_range = 0
    duplicates = duplicate_item_ids(invoice, db)
    for item in invoice.items:
        if item.id in duplicates:
            ignored += 1
            continue
        if not item.installment_total and (not item.date or not (start_date <= item.date <= end_date)):
            outside_range += 1
            continue
        if not item.included or item.imported_entry_id is not None:
            ignored += 1
            continue
        source_key = f"invoice:{invoice.file_hash}:{item.line_index}"
        existing = db.scalar(select(Entry).where(Entry.source_key == source_key))
        if existing:
            item.imported_entry_id = existing.id
            ignored += 1
            continue
        entry = Entry(
            month_id=month.id,
            date=item.date,
            description=item.description,
            amount_cents=item.amount_cents,
            category_slug=item.category_slug,
            origin="fatura",
            invoice_id=invoice.id,
            paid_by_person_id=payload.paid_by_person_id,
            installment_current=item.installment_current,
            installment_total=item.installment_total,
            source_key=source_key,
        )
        db.add(entry)
        db.flush()
        item.imported_entry_id = entry.id
        inserted += 1
    invoice.imported_at = datetime.now(timezone.utc)
    db.commit()
    return {
        "inserted": inserted,
        "ignored": ignored,
        "outside_range": outside_range,
        "period": payload.period,
        "start_date": start_date,
        "end_date": end_date,
    }
