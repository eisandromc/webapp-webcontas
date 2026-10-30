from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from app.config import AUDIT_DB_PATH, BACKUP_DIR, DATABASE_PATH
from app.db.models import (
    Adjustment,
    Entry,
    ImportBatch,
    ImportIssue,
    Invoice,
    InvoiceDraftItem,
    MerchantRule,
    Month,
    MonthSettlement,
    Payment,
)

REQUIRED_TABLES = {"people", "months", "entries", "categories", "payments", "adjustments"}


# ---- Registro de operações em base separada (sobrevive a importação e reset) ----

def _audit_connection() -> sqlite3.Connection:
    AUDIT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(AUDIT_DB_PATH)
    connection.execute(
        "CREATE TABLE IF NOT EXISTS audit_log ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, action TEXT NOT NULL, "
        "status TEXT NOT NULL, detail TEXT, client TEXT)"
    )
    return connection


def audit(action: str, status: str, detail: str = "", client: str | None = None) -> None:
    connection = _audit_connection()
    try:
        connection.execute(
            "INSERT INTO audit_log (at, action, status, detail, client) VALUES (?, ?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), action, status, detail[:500], client),
        )
        connection.commit()
    finally:
        connection.close()


def list_audit(limit: int = 100) -> list[dict]:
    connection = _audit_connection()
    try:
        rows = connection.execute(
            "SELECT id, at, action, status, detail, client FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    finally:
        connection.close()
    return [dict(zip(("id", "at", "action", "status", "detail", "client"), row)) for row in rows]


# ---- Backup ----

def create_backup(label: str = "backup") -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = BACKUP_DIR / f"contas-{label}-{stamp}.db"
    source = sqlite3.connect(DATABASE_PATH)
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    return target


def list_backups() -> list[dict]:
    if not BACKUP_DIR.exists():
        return []
    files = sorted(BACKUP_DIR.glob("contas-*.db"), key=lambda path: path.stat().st_mtime, reverse=True)
    return [
        {
            "name": path.name,
            "size_bytes": path.stat().st_size,
            "created_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
        }
        for path in files
    ]


def validate_database_file(path: Path) -> None:
    with path.open("rb") as handle:
        if handle.read(16) != b"SQLite format 3\x00":
            raise ValueError("O arquivo enviado não é um banco SQLite.")
    try:
        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        try:
            if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("O banco enviado está corrompido.")
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            connection.close()
    except sqlite3.DatabaseError as exc:
        raise ValueError("Não foi possível ler o banco enviado.") from exc
    missing = REQUIRED_TABLES - tables
    if missing:
        raise ValueError(f"O banco enviado não parece ser do Divisão de Contas (faltam: {', '.join(sorted(missing))}).")


def restore_database(path: Path) -> None:
    from app.db.database import engine, init_db

    engine.dispose()
    source = sqlite3.connect(path)
    destination = sqlite3.connect(DATABASE_PATH)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    engine.dispose()
    init_db()


# ---- Reset ----

def reset_data(db: Session) -> dict[str, int]:
    counts: dict[str, int] = {}
    for label, model in (
        ("itens de fatura", InvoiceDraftItem),
        ("lançamentos", Entry),
        ("vales e descontos", Adjustment),
        ("pagamentos", Payment),
        ("faturas", Invoice),
        ("avisos de importação", ImportIssue),
        ("importações", ImportBatch),
        ("regras de categoria", MerchantRule),
        ("acertos", MonthSettlement),
    ):
        counts[label] = db.execute(delete(model)).rowcount or 0
    db.execute(update(Month).values(closed=False))
    db.commit()
    return counts
