"""Summaries: where the money went, and who carried how much of it."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from splitkaro.ledger import effect
from splitkaro.models import Expense, Group
from splitkaro.money import ZERO


@dataclass
class Report:
    total: Decimal = ZERO
    count: int = 0
    by_category: dict[str, Decimal] = field(default_factory=dict)
    by_month: dict[str, Decimal] = field(default_factory=dict)
    paid_by_member: dict[str, Decimal] = field(default_factory=dict)
    share_by_member: dict[str, Decimal] = field(default_factory=dict)


def filter_expenses(
    group: Group,
    month: str | None = None,
    category: str | None = None,
    member: str | None = None,
) -> list[Expense]:
    """Expenses matching every filter given. ``month`` is ``YYYY-MM``."""
    name = group.resolve(member) if member else None
    result = []
    for e in sorted(group.expenses, key=lambda x: (x.date, x.id)):
        if month and e.date.strftime("%Y-%m") != month:
            continue
        if category and e.category.casefold() != category.casefold():
            continue
        if name and name not in e.paid_by and name not in e.split.among:
            continue
        result.append(e)
    return result


def build_report(group: Group, expenses: list[Expense]) -> Report:
    by_category: dict[str, Decimal] = defaultdict(lambda: ZERO)
    by_month: dict[str, Decimal] = defaultdict(lambda: ZERO)
    paid: dict[str, Decimal] = {m.name: ZERO for m in group.members}
    share: dict[str, Decimal] = {m.name: ZERO for m in group.members}
    total = ZERO

    for expense in expenses:
        e = effect(group, expense)
        amount = sum(e.paid.values())
        total += amount
        by_category[expense.category] += amount
        by_month[expense.date.strftime("%Y-%m")] += amount
        for name, value in e.paid.items():
            paid[name] += value
        for name, value in e.owed.items():
            share[name] += value

    return Report(
        total=total,
        count=len(expenses),
        by_category=dict(sorted(by_category.items(), key=lambda kv: (-kv[1], kv[0]))),
        by_month=dict(sorted(by_month.items())),
        paid_by_member=paid,
        share_by_member=share,
    )
