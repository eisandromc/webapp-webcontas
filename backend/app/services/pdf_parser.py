from __future__ import annotations

import hashlib
import io
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime

import pdfplumber
from pypdf import PdfReader
from pypdf.errors import FileNotDecryptedError, PdfReadError


PARSER_VERSION = "ourocard-2"
GENERIC_LINE_RE = re.compile(
    r"^(?P<date>\d{2}/\d{2}(?:/\d{2,4})?)\s+(?P<description>.+?)\s+"
    r"(?:R\$\s*)?(?P<amount>-?\d{1,3}(?:\.\d{3})*,\d{2}-?)\s*(?P<kind>[CD])?$",
    re.IGNORECASE,
)
OUROCARD_LINE_RE = re.compile(
    r"^(?P<date>\d{2}/\d{2})\s+(?P<description>.+?)\s+R\$\s*"
    r"(?P<amount>-?\d{1,3}(?:\.\d{3})*,\d{2}-?)$",
    re.IGNORECASE,
)
STATEMENT_TOTAL_RE = re.compile(r"^Total\s+R\$\s*(-?\d{1,3}(?:\.\d{3})*,\d{2}-?)$", re.IGNORECASE)
GENERIC_TOTAL_RE = re.compile(r"\bTOTAL(?:\s+DA\s+FATURA)?\b.*?(-?\d{1,3}(?:\.\d{3})*,\d{2}-?)", re.IGNORECASE)
INSTALLMENT_RE = re.compile(r"(?<!\d)(?P<current>\d{1,2})/(?P<total>\d{1,2})(?!\d)")
FULL_DATE_RE = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")
PAYMENT_WORDS = ("PAGAMENTO", "PAGTO", "PGTO")


@dataclass
class ParsedItem:
    date: str | None
    description: str
    amount_cents: int
    installment_current: int | None
    installment_total: int | None
    suggested_exclude: bool
    confidence: int


def brl_to_cents(value: str) -> int:
    stripped = value.strip()
    negative = stripped.startswith("-") or stripped.endswith("-")
    cleaned = stripped.strip("-").replace(".", "").replace(",", ".")
    amount = int(round(float(cleaned) * 100))
    return -amount if negative else amount


def normalize_merchant(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().upper()
    normalized = re.sub(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b", " ", normalized)
    normalized = re.sub(r"[^A-Z0-9]+", " ", normalized)
    return " ".join(normalized.split())[:180]


def suggest_category(description: str) -> str:
    text = normalize_merchant(description)
    if any(word in text for word in ("ATACADAO", "MERCADO", "BOURBON", "ZAFFARI", "MACROMIX", "IFOOD", "IFD", "99FOOD", "LANCH", "PIZZA", "CAFE", "RESTAURANTE", "PADARIA")):
        return "alimentacao"
    if any(word in text for word in ("UBER", "ESTAC", "INDIGO", "GASOLINA", "POSTO", "99APP", "TRANSP")):
        return "transporte"
    if any(word in text for word in ("ENERGIA", "CEEE", "CORSAN", "INTERNET", "CONDOMINIO", "GAS ")):
        return "contas"
    return "extras"


def _iso_transaction_date(raw: str, due_date: date | None) -> str:
    day, month = (int(part) for part in raw.split("/"))
    year = due_date.year if due_date else datetime.now().year
    if due_date and month > due_date.month:
        year -= 1
    return date(year, month, day).isoformat()


def _parsed_item(match: re.Match[str], due_date: date | None, confidence: int) -> ParsedItem:
    description = match.group("description").strip()
    amount = brl_to_cents(match.group("amount"))
    kind = (match.groupdict().get("kind") or "").upper()
    if kind == "C" and amount > 0:
        amount = -amount
    installment = INSTALLMENT_RE.search(description)
    raw_date = match.group("date")
    if len(raw_date) == 5:
        parsed_date = _iso_transaction_date(raw_date, due_date)
    else:
        date_format = "%d/%m/%Y" if len(raw_date) == 10 else "%d/%m/%y"
        parsed_date = datetime.strptime(raw_date, date_format).date().isoformat()
    return ParsedItem(
        date=parsed_date,
        description=description,
        amount_cents=amount,
        installment_current=int(installment.group("current")) if installment else None,
        installment_total=int(installment.group("total")) if installment else None,
        suggested_exclude=any(word in normalize_merchant(description) for word in PAYMENT_WORDS),
        confidence=confidence,
    )


def parse_ourocard_text(text: str) -> tuple[list[ParsedItem], int | None]:
    lines = [" ".join(raw.split()) for raw in text.splitlines() if raw.strip()]
    due_match = FULL_DATE_RE.search(text)
    due_date = datetime.strptime(due_match.group(1), "%d/%m/%Y").date() if due_match else None
    total_cents: int | None = None
    for line in lines:
        total_match = STATEMENT_TOTAL_RE.match(line)
        if total_match:
            total_cents = brl_to_cents(total_match.group(1))

    items: list[ParsedItem] = []
    in_statement = False
    for line in lines:
        normalized = normalize_merchant(line)
        if "LANCAMENTOS NESTA FATURA" in normalized:
            in_statement = True
            continue
        if in_statement and normalized.startswith("PARCELAMENTOS PROXIMA FATURA"):
            break
        if not in_statement:
            continue
        match = OUROCARD_LINE_RE.match(line)
        if match:
            items.append(_parsed_item(match, due_date, 95))
    return items, total_cents


def parse_generic_text(text: str) -> tuple[list[ParsedItem], int | None]:
    items: list[ParsedItem] = []
    total_cents: int | None = None
    due_match = FULL_DATE_RE.search(text)
    due_date = datetime.strptime(due_match.group(1), "%d/%m/%Y").date() if due_match else None
    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        if not line:
            continue
        total_match = GENERIC_TOTAL_RE.search(line)
        if total_match:
            total_cents = brl_to_cents(total_match.group(1))
        match = GENERIC_LINE_RE.match(line)
        if match:
            items.append(_parsed_item(match, due_date, 80))
    return items, total_cents


class OurocardParser:
    def parse(self, text: str) -> tuple[list[ParsedItem], int | None]:
        items, total = parse_ourocard_text(text)
        return (items, total) if items else parse_generic_text(text)


def parse_invoice(data: bytes, password: str) -> dict:
    file_hash = hashlib.sha256(data).hexdigest()
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            if not password:
                raise ValueError("Configure a senha do PDF antes de analisar a fatura.")
            if reader.decrypt(password) == 0:
                raise ValueError("Senha incorreta.")
    except (PdfReadError, FileNotDecryptedError) as exc:
        raise ValueError("Não foi possível abrir este PDF.") from exc

    try:
        with pdfplumber.open(io.BytesIO(data), password=password or None) as pdf:
            text = "\n".join(page.extract_text(x_tolerance=2, y_tolerance=3) or "" for page in pdf.pages)
    except Exception as exc:
        raise ValueError("Não foi possível extrair o conteúdo deste PDF.") from exc

    items, total_cents = OurocardParser().parse(text)
    if not items:
        raise ValueError("Nenhum lançamento foi reconhecido. O layout da fatura precisa ser revisado.")
    return {
        "file_hash": file_hash,
        "items": items,
        "total_cents": total_cents,
        "parsed_sum_cents": sum(item.amount_cents for item in items if not item.suggested_exclude),
    }
