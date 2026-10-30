from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session


def test_entry_imported_from_invoice_can_be_deleted(tmp_path):
    from app.api.routers.records import delete_entry
    from app.db.models import Base, Category, Entry, Invoice, InvoiceDraftItem, Month

    engine = create_engine(f"sqlite:///{(tmp_path / 'entries.db').as_posix()}")
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        month = Month(period="2026-10")
        db.add_all([month, Category(slug="contas", name="Contas", color="#000", position=0)])
        invoice = Invoice(file_hash="x" * 64, filename="fatura.pdf", parser_version="1")
        db.add(invoice)
        db.flush()
        entry = Entry(month_id=month.id, description="LANCHE", amount_cents=7970, category_slug="contas", origin="fatura", invoice_id=invoice.id)
        db.add(entry)
        db.flush()
        item = InvoiceDraftItem(invoice_id=invoice.id, line_index=0, description="LANCHE", amount_cents=7970, category_slug="contas", imported_entry_id=entry.id)
        db.add(item)
        db.commit()

        delete_entry(entry.id, db)

        assert db.get(Entry, entry.id) is None
        db.refresh(item)
        assert item.imported_entry_id is None
