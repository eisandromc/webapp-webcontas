"""Zera o banco de dados, sempre com uma cópia de segurança antes.

Uso: python scripts/zerar_banco.py [--tudo] [--sim]

Sem opções, faz o mesmo que o botão "Zerar" de Configurações: apaga lançamentos, vales,
descontos, pagamentos, faturas, importações, regras de categoria e acertos, e reabre os meses.
Pessoas, categorias, meses cadastrados e configurações são mantidos.

--tudo  apaga também pessoas, categorias, meses e configurações e recria o cadastro inicial.
--sim   não pede confirmação (para uso em scripts).

A senha do PDF fica no cofre do sistema e não é apagada; remova-a em Configurações.
O registro de auditoria (auditoria.db) é mantido e recebe uma linha sobre o reset.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import delete  # noqa: E402

from app.config import DATABASE_PATH  # noqa: E402
from app.db.database import Base, SessionLocal, init_db  # noqa: E402
from app.seed import seed_database  # noqa: E402
from app.services.maintenance import audit, create_backup, reset_data  # noqa: E402


def wipe_everything(db) -> dict[str, int]:
    counts: dict[str, int] = {}
    # Tabelas dependentes primeiro, para respeitar as chaves estrangeiras.
    for table in reversed(Base.metadata.sorted_tables):
        counts[table.name] = db.execute(delete(table)).rowcount or 0
    db.commit()
    seed_database(db)
    return counts


def main() -> int:
    args = set(sys.argv[1:])
    if args - {"--tudo", "--sim"}:
        print(__doc__)
        return 2
    everything = "--tudo" in args
    if not DATABASE_PATH.exists():
        print(f"Banco não encontrado: {DATABASE_PATH}")
        return 1

    scope = "TODOS os dados (inclusive pessoas, categorias e meses)" if everything else "os lançamentos, pagamentos e faturas"
    print(f"Banco: {DATABASE_PATH}")
    print(f"Isto vai apagar {scope}.")
    if "--sim" not in args and input('Digite ZERAR para confirmar: ').strip().upper() != "ZERAR":
        print("Cancelado. Nada foi alterado.")
        return 1

    init_db()
    safety = create_backup("antes-do-reset")
    with SessionLocal() as db:
        try:
            counts = wipe_everything(db) if everything else reset_data(db)
        except Exception as exc:
            db.rollback()
            audit("reset", "erro", f"script: {exc}", "script")
            print(f"Falha ao zerar: {exc}. O banco não foi alterado.")
            return 1
    removed = ", ".join(f"{value} {label}" for label, value in counts.items() if value) or "nada"
    audit("reset", "ok", f"script{' --tudo' if everything else ''}. Removidos: {removed}. Cópia de segurança: {safety.name}", "script")
    print(f"Removidos: {removed}.")
    print(f"Cópia de segurança: {safety}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
