import pytest

from app.services.pdf_parser import brl_to_cents, normalize_merchant, parse_ourocard_text, suggest_category


@pytest.mark.parametrize(("value", "expected"), [("1.234,56", 123456), ("-19,90", -1990), ("19,90-", -1990), ("0,01", 1)])
def test_brl_to_cents(value, expected):
    assert brl_to_cents(value) == expected


def test_merchant_normalization_and_category():
    assert normalize_merchant("Atacadão 12/09") == "ATACADAO"
    assert suggest_category("ATACADAO 12/09") == "alimentacao"
    assert suggest_category("IFD*RESTAURANTE EXEMPLO") == "alimentacao"
    assert suggest_category("ESTAC. CENTRO") == "transporte"


def test_ourocard_parser_excludes_payments_and_future_installments():
    text = """
    Vencimento
    01/09/2026
    Resumo da fatura
    Total R$ 90,00
    Lançamentos nesta fatura
    Data Descrição País Valor
    Pagamentos
    31/07 PGTO. FATURA AGENCIA BR R$ 100,00-
    Créditos diversos
    11/08 LOJA TESTE SAO PAULO BR R$ 10,00-
    Compras diversas
    12/08 MERCADO EXEMPLO PORTO ALEGRE BR R$ 100,00
    Parcelamentos Próxima Fatura
    12/08 COMPRA FUTURA PARC 02/10 SAO PAULO R$ 50,00
    """
    items, total = parse_ourocard_text(text)
    assert total == 9_000
    assert len(items) == 3
    assert items[0].suggested_exclude is True
    assert items[1].amount_cents == -1_000
    assert items[2].date == "2026-08-12"
    assert sum(item.amount_cents for item in items if not item.suggested_exclude) == total
