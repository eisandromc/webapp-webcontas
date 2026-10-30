from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import MAX_UPLOAD_BYTES
from app.db.database import get_db
from app.db.models import Adjustment, Entry, ImportBatch, ImportIssue
from app.services.months import get_or_create_month
from app.services.spreadsheet_import import SpreadsheetPreview, parse_spreadsheet


router = APIRouter()


def commit_spreadsheet(preview: SpreadsheetPreview, filename: str, db: Session) -> dict:
    existing = db.scalar(select(ImportBatch).where(ImportBatch.file_hash == preview.file_hash))
    if existing:
        return {"status": "already_imported", "batch_id": existing.id, **preview.public()}
    batch = ImportBatch(file_hash=preview.file_hash, filename=filename[:180])
    db.add(batch)
    db.flush()
    inserted = 0
    skipped_closed = 0
    for record in preview.records:
        month = get_or_create_month(db, record.period)
        if month.closed:
            # Meses fechados não recebem registros novos; reabra o mês e importe de novo.
            skipped_closed += 1
            continue
        if record.kind == "entry":
            if not db.scalar(select(Entry.id).where(Entry.source_key == record.source_key)):
                db.add(
                    Entry(
                        month_id=month.id,
                        date=record.date,
                        description=record.description,
                        amount_cents=record.amount_cents,
                        category_slug=record.category_slug or "extras",
                        origin="planilha",
                        source_key=record.source_key,
                    )
                )
                inserted += 1
        else:
            if not db.scalar(select(Adjustment.id).where(Adjustment.source_key == record.source_key)):
                db.add(
                    Adjustment(
                        month_id=month.id,
                        kind=record.adjustment_kind or "desconto",
                        description=record.description,
                        amount_cents=record.amount_cents,
                        source_key=record.source_key,
                    )
                )
                inserted += 1
    for issue in preview.issues:
        db.add(ImportIssue(batch_id=batch.id, **issue.__dict__))
    db.commit()
    return {"status": "imported", "batch_id": batch.id, "inserted": inserted, "skipped_closed": skipped_closed, **preview.public()}


@router.post("/imports/spreadsheet")
async def import_spreadsheet(
    file: UploadFile = File(...),
    commit: bool = Query(False),
    db: Session = Depends(get_db),
) -> dict:
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "A planilha excede o limite de 15 MB.")
    if not (file.filename or "").lower().endswith(".xlsx"):
        raise HTTPException(400, "Envie uma planilha .xlsx.")
    try:
        preview = parse_spreadsheet(data)
    except Exception as exc:
        raise HTTPException(400, f"Não foi possível ler a planilha: {exc}") from exc
    if not commit:
        return {"status": "preview", **preview.public()}
    return commit_spreadsheet(preview, file.filename or "planilha.xlsx", db)


@router.get("/imports/issues")
def import_issues(db: Session = Depends(get_db)) -> list[dict]:
    issues = list(db.scalars(select(ImportIssue).order_by(ImportIssue.id.desc())))
    return [
        {
            "id": issue.id,
            "period": issue.period,
            "sheet": issue.sheet,
            "cell": issue.cell,
            "code": issue.code,
            "message": issue.message,
            "source_value": issue.source_value,
            "resolved": issue.resolved,
        }
        for issue in issues
    ]
