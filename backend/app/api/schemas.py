from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator


class PersonCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class PersonUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    active: bool | None = None
    is_primary: bool | None = None


class MonthCreate(BaseModel):
    period: str
    start_date: str | None = None
    end_date: str | None = None


class MonthUpdate(BaseModel):
    period: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class MonthRangePayload(BaseModel):
    start_date: str
    end_date: str


class PeriodDefaultsPayload(BaseModel):
    start_day: int = Field(ge=1, le=31)
    end_day: int = Field(ge=1, le=31)


class ShareUpdate(BaseModel):
    person_id: int
    percentage_bp: int = Field(ge=0, le=10_000)
    position: int = Field(ge=0)


class EntryPayload(BaseModel):
    date: str | None = None
    description: str = Field(min_length=1, max_length=250)
    amount_cents: int
    category_slug: str
    paid_by_person_id: int | None = None


class EntryPatch(BaseModel):
    date: str | None = None
    description: str | None = Field(default=None, min_length=1, max_length=250)
    amount_cents: int | None = None
    category_slug: str | None = None
    paid_by_person_id: int | None = None


class AdjustmentPayload(BaseModel):
    kind: str
    description: str = Field(min_length=1, max_length=250)
    amount_cents: int
    distribution: str = "proportional"
    person_id: int | None = None

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, value: str) -> str:
        if value not in {"vale", "desconto"}:
            raise ValueError("Tipo de ajuste inválido.")
        return value

    @model_validator(mode="after")
    def validate_distribution(self):
        if self.distribution not in {"proportional", "equal", "person"}:
            raise ValueError("Forma de desconto inválida.")
        if self.kind == "vale":
            self.distribution = "proportional"
            self.person_id = None
        elif self.distribution == "person" and self.person_id is None:
            raise ValueError("Escolha a pessoa que receberá o desconto.")
        elif self.distribution != "person":
            self.person_id = None
        return self


class AdjustmentPatch(BaseModel):
    kind: str | None = None
    description: str | None = Field(default=None, min_length=1, max_length=250)
    amount_cents: int | None = None
    distribution: str | None = None
    person_id: int | None = None


class PaymentPayload(BaseModel):
    person_id: int
    date: str | None = None
    amount_cents: int
    note: str | None = Field(default=None, max_length=250)


class PaymentPatch(BaseModel):
    person_id: int | None = None
    date: str | None = None
    amount_cents: int | None = None
    note: str | None = Field(default=None, max_length=250)


class PasswordPayload(BaseModel):
    password: str = Field(min_length=1, max_length=200)


class InvoiceItemPatch(BaseModel):
    included: bool | None = None
    description: str | None = Field(default=None, min_length=1, max_length=250)
    amount_cents: int | None = None
    category_slug: str | None = None


class InvoiceImportPayload(BaseModel):
    period: str
    paid_by_person_id: int | None = None


class ResetPayload(BaseModel):
    confirm: str


class ClosedPayload(BaseModel):
    closed: bool


class SettlementPayload(BaseModel):
    received: bool


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    color: str = Field(default="#65726f", pattern=r"^#[0-9a-fA-F]{6}$")


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
