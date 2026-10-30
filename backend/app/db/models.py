from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Person(Base):
    __tablename__ = "people"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Month(Base):
    __tablename__ = "months"

    id: Mapped[int] = mapped_column(primary_key=True)
    period: Mapped[str] = mapped_column(String(7), unique=True, index=True)
    start_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    end_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    closed: Mapped[bool] = mapped_column(Boolean, default=False)
    # Cadastrado explicitamente em Contas (meses abertos só pela navegação ficam False).
    registered: Mapped[bool] = mapped_column(Boolean, default=False)
    # Fonte primária vigente no mês; meses fechados preservam a escolha da época.
    primary_person_id: Mapped[int | None] = mapped_column(ForeignKey("people.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    shares: Mapped[list[MonthPerson]] = relationship(
        back_populates="month", cascade="all, delete-orphan", order_by="MonthPerson.position"
    )


class MonthPerson(Base):
    __tablename__ = "month_people"
    __table_args__ = (UniqueConstraint("month_id", "person_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    month_id: Mapped[int] = mapped_column(ForeignKey("months.id", ondelete="CASCADE"), index=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id"), index=True)
    percentage_bp: Mapped[int] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(Integer)

    month: Mapped[Month] = relationship(back_populates="shares")
    person: Mapped[Person] = relationship()


class MonthSettlement(Base):
    __tablename__ = "month_settlements"
    __table_args__ = (UniqueConstraint("month_id", "person_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    month_id: Mapped[int] = mapped_column(ForeignKey("months.id", ondelete="CASCADE"), index=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id"), index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Category(Base):
    __tablename__ = "categories"

    slug: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[str] = mapped_column(String(60))
    color: Mapped[str] = mapped_column(String(20))
    position: Mapped[int] = mapped_column(Integer)


class Entry(Base):
    __tablename__ = "entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    month_id: Mapped[int] = mapped_column(ForeignKey("months.id", ondelete="CASCADE"), index=True)
    date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    description: Mapped[str] = mapped_column(String(250))
    amount_cents: Mapped[int] = mapped_column(Integer)
    category_slug: Mapped[str] = mapped_column(ForeignKey("categories.slug"), index=True)
    origin: Mapped[str] = mapped_column(String(30), default="manual")
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"), nullable=True, index=True)
    paid_by_person_id: Mapped[int | None] = mapped_column(ForeignKey("people.id"), nullable=True, index=True)
    installment_current: Mapped[int | None] = mapped_column(Integer, nullable=True)
    installment_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_key: Mapped[str | None] = mapped_column(String(180), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    category: Mapped[Category] = relationship()


class Adjustment(Base):
    __tablename__ = "adjustments"

    id: Mapped[int] = mapped_column(primary_key=True)
    month_id: Mapped[int] = mapped_column(ForeignKey("months.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)
    description: Mapped[str] = mapped_column(String(250))
    amount_cents: Mapped[int] = mapped_column(Integer)
    distribution: Mapped[str] = mapped_column(String(20), default="proportional")
    person_id: Mapped[int | None] = mapped_column(ForeignKey("people.id"), nullable=True, index=True)
    source_key: Mapped[str | None] = mapped_column(String(180), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    person: Mapped[Person | None] = relationship()


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    month_id: Mapped[int] = mapped_column(ForeignKey("months.id", ondelete="CASCADE"), index=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id"), index=True)
    date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    amount_cents: Mapped[int] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(String(250), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    person: Mapped[Person] = relationship()


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    file_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    filename: Mapped[str] = mapped_column(String(180))
    parser_version: Mapped[str] = mapped_column(String(30))
    total_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parsed_sum_cents: Mapped[int] = mapped_column(Integer, default=0)
    imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    items: Mapped[list[InvoiceDraftItem]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan", order_by="InvoiceDraftItem.line_index"
    )


class InvoiceDraftItem(Base):
    __tablename__ = "invoice_draft_items"
    __table_args__ = (UniqueConstraint("invoice_id", "line_index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    line_index: Mapped[int] = mapped_column(Integer)
    date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    description: Mapped[str] = mapped_column(String(250))
    amount_cents: Mapped[int] = mapped_column(Integer)
    installment_current: Mapped[int | None] = mapped_column(Integer, nullable=True)
    installment_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category_slug: Mapped[str] = mapped_column(ForeignKey("categories.slug"))
    included: Mapped[bool] = mapped_column(Boolean, default=True)
    suggested_exclude: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence: Mapped[int] = mapped_column(Integer, default=70)
    imported_entry_id: Mapped[int | None] = mapped_column(ForeignKey("entries.id"), nullable=True)

    invoice: Mapped[Invoice] = relationship(back_populates="items")


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    file_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    filename: Mapped[str] = mapped_column(String(180))
    status: Mapped[str] = mapped_column(String(30), default="completed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ImportIssue(Base):
    __tablename__ = "import_issues"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id", ondelete="CASCADE"), index=True)
    period: Mapped[str | None] = mapped_column(String(7), nullable=True)
    sheet: Mapped[str] = mapped_column(String(100))
    cell: Mapped[str | None] = mapped_column(String(20), nullable=True)
    code: Mapped[str] = mapped_column(String(60), index=True)
    message: Mapped[str] = mapped_column(Text)
    source_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)


class MerchantRule(Base):
    __tablename__ = "merchant_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    normalized: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    category_slug: Mapped[str] = mapped_column(ForeignKey("categories.slug"))


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
