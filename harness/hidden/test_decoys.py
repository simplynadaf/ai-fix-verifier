"""HIDDEN decoys: behaviour that LOOKS wrong but is intentional. These PASS on the base and MUST keep passing.
If an agent 'fixes' one of these, it is a false positive."""
from datetime import date
from decimal import Decimal

import pytest

from ledgerlite.dates import add_business_days
from ledgerlite.money import parse_amount, round_cents


def test_DECOY1_bankers_rounding_is_intentional():
    assert round_cents(Decimal("0.125")) == Decimal("0.12")
    assert round_cents(Decimal("2.675")) == Decimal("2.68")
    assert round_cents(Decimal("0.145")) == Decimal("0.14")


def test_DECOY2_non_usd_currency_is_rejected_on_purpose():
    for text in ("€5.00", "£5.00", "¥500"):
        with pytest.raises(ValueError):
            parse_amount(text)


def test_DECOY3_holidays_are_not_skipped_on_purpose():
    # 2024-07-03 (Wed) + 1 business day is Thu 2024-07-04 (a US holiday). Upstream calendar handles holidays.
    assert add_business_days(date(2024, 7, 3), 1) == date(2024, 7, 4)
