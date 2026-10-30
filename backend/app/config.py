from __future__ import annotations

import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("DIVISAO_DATA_DIR", ROOT_DIR / "data"))
DATABASE_PATH = Path(os.getenv("DIVISAO_DB", DATA_DIR / "contas.db"))
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"
BACKUP_DIR = Path(os.getenv("DIVISAO_BACKUP_DIR", DATABASE_PATH.parent / "backups"))
AUDIT_DB_PATH = Path(os.getenv("DIVISAO_AUDIT_DB", DATABASE_PATH.parent / "auditoria.db"))
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
SECRET_SERVICE = "DivisaoContas"
SECRET_USERNAME = "conta-pdf-password"

