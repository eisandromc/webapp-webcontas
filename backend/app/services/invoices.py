"""Revisão de faturas: faixa do mês, detecção de itens já salvos e serialização do rascunho."""
from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Entry, Invoice, InvoiceDraftItem
from app.services.months import month_or_virtual
from app.services.periods import month_range


def invoice_period_bounds(db: Session, period: str | None) -> tuple[str | None, str | None]:
    if not period:
        return None, None
    return month_range(db, month_or_virtual(db, period))


def item_key(date_value: str | None, description: str, amount_cents: int, installment_current: int | None) -> tuple:
    return (date_value, description.strip().lower(), amount_cents, installment_current or 0)


def saved_invoice_entries(db: Session) -> Counter:
    return Counter(
        item_key(entry.date, entry.description, entry.amount_cents, entry.installment_current)
        for entry in db.scalars(select(Entry).where(Entry.origin == "fatura"))
    )


def duplicate_item_ids(invoice: Invoice, db: Session | None) -> set[int]:
    """Itens da fatura que já existem como lançamentos salvos (mesma data, nome, valor e parcela)."""
    if db is None:
        return set()
    available = saved_invoice_entries(db)
    ordered = sorted(invoice.items, key=lambda item: item.line_index)
    for item in ordered:
        if item.imported_entry_id is not None:
            entry = db.get(Entry, item.imported_entry_id)
            if entry:
                key = item_key(entry.date, entry.description, entry.amount_cents, entry.installment_current)
                if available[key] > 0:
                    available[key] -= 1
    duplicates: set[int] = set()
    for item in ordered:
        if item.imported_entry_id is not None:
            continue
        key = item_key(item.date, item.description, item.amount_cents, item.installment_current)
        if available[key] > 0:
            available[key] -= 1
            duplicates.add(item.id)
    return duplicates


def serialize_invoice(invoice: Invoice, start_date: str | None = None, end_date: str | None = None, db: Session | None = None) -> dict:
    duplicates = duplicate_item_ids(invoice, db)

    def in_period(item: InvoiceDraftItem) -> bool:
        if item.installment_total:
            return True
        return not start_date or not end_date or bool(item.date and start_date <= item.date <= end_date)

    selected = sum(item.amount_cents for item in invoice.items if item.included and in_period(item))
    full_selected = sum(item.amount_cents for item in invoice.items if item.included)
    outside_range = sum(1 for item in invoice.items if not in_period(item))
    return {
        "id": invoice.id,
        "filename": invoice.filename,
        "file_hash": invoice.file_hash,
        "total_cents": invoice.total_cents,
        "parsed_sum_cents": invoice.parsed_sum_cents,
        "selected_sum_cents": selected,
        "full_selected_sum_cents": full_selected,
        "difference_cents": None if invoice.total_cents is None or outside_range else selected - invoice.total_cents,
        "outside_range_count": outside_range,
        "range_start": start_date,
        "range_end": end_date,
        "imported_at": invoice.imported_at,
        "items": [
            {
                "id": item.id,
                "date": item.date,
                "description": item.description,
                "amount_cents": item.amount_cents,
                "installment_current": item.installment_current,
                "installment_total": item.installment_total,
                "category_slug": item.category_slug,
                "included": item.included,
                "suggested_exclude": item.suggested_exclude,
                "confidence": item.confidence,
                "imported": item.imported_entry_id is not None or item.id in duplicates,
                "in_period": in_period(item),
            }
            for item in invoice.items
        ],
    }
