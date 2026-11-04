"""Exact money arithmetic.

Amounts are ``Decimal`` values rounded to two places (rupees and paise, or the
equivalent minor unit). Floats are never used, so 0.1 + 0.2 is exactly 0.3.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


class MoneyError(ValueError):
    pass


def to_money(value: object) -> Decimal:
    """Parse ``value`` (str, int or Decimal) into an amount with two decimals."""
    if isinstance(value, float):
        # Floats cannot represent most amounts exactly; make callers be explicit.
        value = repr(value)
    try:
        amount = Decimal(str(value).replace(",", "").strip())
    except InvalidOperation:
        raise MoneyError(f"not a valid amount: {value!r}") from None
    if not amount.is_finite():
        raise MoneyError(f"not a valid amount: {value!r}")
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def to_decimal(value: object) -> Decimal:
    """Parse a non-money number such as a share, a percentage or a rate."""
    try:
        number = Decimal(str(value).strip())
    except InvalidOperation:
        raise MoneyError(f"not a valid number: {value!r}") from None
    if not number.is_finite():
        raise MoneyError(f"not a valid number: {value!r}")
    return number


def allocate(total: Decimal, weights: list[Decimal]) -> list[Decimal]:
    """Split ``total`` in proportion to ``weights`` so the parts add up exactly.

    Uses the largest-remainder method on whole paise: every part is rounded
    down, then the leftover paise go to the parts that lost the most to
    rounding (earlier parts win ties). Splitting 100.00 three ways gives
    33.34, 33.33, 33.33.
    """
    if not weights:
        raise MoneyError("cannot split an amount among nobody")
    if any(w < 0 for w in weights):
        raise MoneyError("weights cannot be negative")
    weight_sum = sum(weights)
    if weight_sum == 0:
        raise MoneyError("weights add up to zero")

    sign = -1 if total < 0 else 1
    paise = int((abs(total) / CENT).to_integral_value())
    exact = [Decimal(paise) * w / weight_sum for w in weights]
    parts = [int(x) for x in exact]  # floor, since every value is >= 0
    leftover = paise - sum(parts)

    by_remainder = sorted(range(len(weights)), key=lambda i: (-(exact[i] - parts[i]), i))
    for i in by_remainder[:leftover]:
        parts[i] += 1

    return [sign * Decimal(p) * CENT for p in parts]


def format_money(amount: Decimal, currency: str = "INR") -> str:
    """Format for people: ``₹1,23,456.50``, ``$12.00``, or ``12.00 CHF``.

    Rupees use Indian digit grouping (lakhs and crores).
    """
    symbols = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥"}
    sign = "-" if amount < 0 else ""
    body = _indian_grouping(abs(amount)) if currency == "INR" else f"{abs(amount):,.2f}"
    if currency in symbols:
        return f"{sign}{symbols[currency]}{body}"
    return f"{sign}{body} {currency}"


def _indian_grouping(amount: Decimal) -> str:
    whole, fraction = f"{amount:.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        groups.insert(0, head)
        whole = ",".join(groups) + "," + tail
    return f"{whole}.{fraction}"
