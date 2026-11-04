import datetime as dt
from decimal import Decimal

from splitkaro.models import Expense, Group, Split

D = Decimal


def make_group(*names, currency="INR"):
    group = Group(name="Test", currency=currency)
    for name in names:
        group.add_member(name)
    return group


def spend(group, amount, payer, split=None, currency=None, day=1, category="general", description="thing"):
    """Add an expense paid in full by ``payer`` (a name) or by several payers (a dict)."""
    amount = D(amount)
    paid_by = {payer: amount} if isinstance(payer, str) else {k: D(v) for k, v in payer.items()}
    return group.add_expense(
        Expense(
            id=0,
            description=description,
            amount=amount,
            paid_by=paid_by,
            split=split or Split.equal([m.name for m in group.members]),
            date=dt.date(2026, 11, day),
            currency=currency or group.currency,
            category=category,
        )
    )
