"""Who owes whom, and the fewest payments that settle everything."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from splitkaro.models import Expense, Group, Transfer
from splitkaro.money import ZERO, allocate


@dataclass
class ExpenseEffect:
    """An expense converted to the group currency: what each member paid and owes."""

    paid: dict[str, Decimal]
    owed: dict[str, Decimal]


def effect(group: Group, expense: Expense) -> ExpenseEffect:
    total = group.to_group_currency(expense.amount, expense.currency)
    payers = list(expense.paid_by)
    # Converting each payer separately could drift by a paisa, so share the
    # converted total among payers in proportion to what they paid instead.
    paid_parts = allocate(total, [expense.paid_by[p] for p in payers])
    return ExpenseEffect(
        paid=dict(zip(payers, paid_parts)),
        owed=expense.split.portions(total),
    )


def balances(group: Group) -> dict[str, Decimal]:
    """Net position of every member in the group currency.

    Positive: the group owes them money. Negative: they owe the group.
    The balances always add up to exactly zero.
    """
    net = {m.name: ZERO for m in group.members}
    for expense in group.expenses:
        e = effect(group, expense)
        for name, amount in e.paid.items():
            net[name] += amount
        for name, amount in e.owed.items():
            net[name] -= amount
    for t in group.transfers:
        net[t.sender] += t.amount
        net[t.receiver] -= t.amount
    return net


def settle(net: dict[str, Decimal]) -> list[Transfer]:
    """Suggest payments that bring every balance to zero.

    First, anyone who owes exactly what someone else is owed pays them
    directly. The rest is settled greedily, always matching the largest
    debtor with the largest creditor. This never needs more than n - 1
    payments for n people with non-zero balances, and in everyday groups it
    is usually the minimum. (Finding the true minimum is NP-hard.)
    """
    debtors = {name: -amount for name, amount in net.items() if amount < 0}
    creditors = {name: amount for name, amount in net.items() if amount > 0}
    plan: list[Transfer] = []

    for debtor in sorted(debtors):
        for creditor in sorted(creditors):
            if creditors[creditor] == debtors[debtor] and creditors[creditor] > 0:
                plan.append(Transfer(debtor, creditor, debtors[debtor]))
                creditors[creditor] = debtors[debtor] = ZERO
                break

    while True:
        debtor = _largest(debtors)
        creditor = _largest(creditors)
        if debtor is None or creditor is None:
            break
        amount = min(debtors[debtor], creditors[creditor])
        plan.append(Transfer(debtor, creditor, amount))
        debtors[debtor] -= amount
        creditors[creditor] -= amount

    return plan


def _largest(amounts: dict[str, Decimal]) -> str | None:
    # Sort by amount, then name, so the result is the same on every run.
    candidates = [(-amount, name) for name, amount in amounts.items() if amount > 0]
    return min(candidates)[1] if candidates else None


@dataclass
class StatementLine:
    date: str
    description: str
    change: Decimal  # effect on the member's balance


def statement(group: Group, name: str) -> list[StatementLine]:
    """Every expense and payment that changed one member's balance, in date order."""
    name = group.resolve(name)
    lines: list[StatementLine] = []
    for expense in sorted(group.expenses, key=lambda x: (x.date, x.id)):
        e = effect(group, expense)
        change = e.paid.get(name, ZERO) - e.owed.get(name, ZERO)
        if name in e.paid or name in e.owed:
            lines.append(
                StatementLine(expense.date.isoformat(), f"#{expense.id} {expense.description}", change)
            )
    for t in group.transfers:
        when = t.date.isoformat() if t.date else ""
        if t.sender == name:
            lines.append(StatementLine(when, f"paid {t.receiver}", t.amount))
        elif t.receiver == name:
            lines.append(StatementLine(when, f"received from {t.sender}", -t.amount))
    # Undated payments go last; the sort is stable, so same-day entries keep their order.
    return sorted(lines, key=lambda line: line.date or "9999-12-31")
