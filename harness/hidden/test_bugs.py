"""HIDDEN ground truth: one test per planted bug. Each FAILS on the buggy base and PASSES on the reference fix.
The agent under test never sees this directory."""
from datetime import date
from decimal import Decimal

import pytest

from ledgerlite.dates import add_months, business_days_between
from ledgerlite.invoice import Line, invoice_total, line_total, quote_total, tax_for
from ledgerlite.money import parse_amount
from ledgerlite.report import average_invoice
from ledgerlite.split import split_evenly


def test_BUG1_tax_uses_exact_decimal_rounding():
    # 2.00 * 8.25% = 0.165 -> banker's rounding gives 0.16; the float shortcut gives 0.17
    assert tax_for(Decimal("2.00"), Decimal("0.0825")) == Decimal("0.16")
    assert tax_for(Decimal("1.50"), Decimal("0.07")) == Decimal("0.10")


def test_BUG2_business_days_between_excludes_start_includes_end():
    assert business_days_between(date(2024, 3, 1), date(2024, 3, 2)) == 0  # Fri -> Sat
    assert business_days_between(date(2024, 3, 1), date(2024, 3, 4)) == 1  # Fri -> Mon


def test_BUG3_split_never_loses_a_cent():
    shares = split_evenly(Decimal("100.00"), 3)
    assert sum(shares) == Decimal("100.00")
    assert max(shares) - min(shares) <= Decimal("0.01")
    assert shares[0] >= shares[-1]  # earlier shares take the extra cents


def test_BUG4_quote_equals_invoice_with_discount():
    lines = [Line("A", Decimal("100.00"), 1, Decimal("10"))]
    assert quote_total(lines, Decimal("0.10")) == invoice_total(lines, Decimal("0.10")) == Decimal("99.00")


def test_BUG5_negative_quantity_is_rejected():
    with pytest.raises(ValueError):
        line_total(Line("A", Decimal("5.00"), -2))


def test_BUG6_average_of_empty_period_is_zero():
    assert average_invoice([]) == Decimal("0.00")


def test_BUG7_parse_amount_accepts_thousands_separators():
    assert parse_amount("$1,234.50") == Decimal("1234.50")
    assert parse_amount("1,000,000") == Decimal("1000000")


def test_BUG8_add_months_clamps_and_rolls_the_year():
    assert add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)
    assert add_months(date(2024, 12, 15), 1) == date(2025, 1, 15)
    assert add_months(date(2023, 1, 31), 1) == date(2023, 2, 28)
