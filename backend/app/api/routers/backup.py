from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.schemas import ResetPayload
from app.api.security import client_of, require_localhost
from app.config import MAX_UPLOAD_BYTES
from app.db.database import get_db
from app.services.maintenance import audit, create_backup, list_audit, list_backups, reset_data, restore_database, validate_database_file


router = APIRouter()


@router.get("/backups")
def backups() -> list[dict]:
    return list_backups()


@router.get("/backup/download")
def download_backup(request: Request) -> FileResponse:
    require_localhost(request)
    try:
        path = create_backup("backup")
    except Exception as exc:
        audit("backup", "erro", str(exc), client_of(request))
        raise HTTPException(500, "Não foi possível criar o backup.") from exc
    audit("backup", "ok", f"Backup criado: {path.name}", client_of(request))
    return FileResponse(path, media_type="application/octet-stream", filename=path.name)


@router.post("/backup/import")
async def import_database(request: Request, file: UploadFile = File(...)) -> dict:
    require_localhost(request)
    client = client_of(request)
    data = await file.read(MAX_UPLOAD_BYTES * 4 + 1)
    if len(data) > MAX_UPLOAD_BYTES * 4:
        audit("importar banco", "erro", f"{file.filename}: arquivo grande demais", client)
        raise HTTPException(413, "O banco excede o limite de 60 MB.")
    with tempfile.TemporaryDirectory() as folder:
        incoming = Path(folder) / "incoming.db"
        incoming.write_bytes(data)
        try:
            validate_database_file(incoming)
        except ValueError as exc:
            audit("importar banco", "erro", f"{file.filename}: {exc}", client)
            raise HTTPException(400, str(exc)) from exc
        safety = create_backup("antes-de-importar")
        try:
            restore_database(incoming)
        except Exception as exc:
            audit("importar banco", "erro", f"{file.filename}: falha ao restaurar ({exc})", client)
            raise HTTPException(500, "Não foi possível importar o banco. O banco atual foi mantido.") from exc
    audit("importar banco", "ok", f"Importado {file.filename}. Cópia de segurança: {safety.name}", client)
    return {"status": "imported", "safety_backup": safety.name}


@router.post("/backup/reset")
def reset_database(payload: ResetPayload, request: Request, db: Session = Depends(get_db)) -> dict:
    require_localhost(request)
    client = client_of(request)
    if payload.confirm.strip().upper() != "ZERAR":
        raise HTTPException(400, "Digite ZERAR para confirmar.")
    safety = create_backup("antes-do-reset")
    try:
        counts = reset_data(db)
    except Exception as exc:
        db.rollback()
        audit("reset", "erro", str(exc), client)
        raise HTTPException(500, "Não foi possível resetar o banco.") from exc
    removed = ", ".join(f"{value} {label}" for label, value in counts.items() if value)
    audit("reset", "ok", f"Removidos: {removed or 'nada'}. Cópia de segurança: {safety.name}", client)
    return {"status": "reset", "removed": counts, "safety_backup": safety.name}


@router.get("/audit-log")
def audit_log(limit: int = Query(50, ge=1, le=500)) -> list[dict]:
    return list_audit(limit)
