"""The data that makes up a group's splitkaro: members, expenses and payments."""

from __future__ import annotations

import datetime as dt
import enum
from dataclasses import dataclass, field
from decimal import Decimal

from splitkaro.money import ZERO, MoneyError, allocate, to_money

HUNDRED = Decimal(100)


class SplitKaroError(ValueError):
    """A request that would leave the group's records inconsistent."""


class SplitKind(str, enum.Enum):
    EQUAL = "equal"  # everyone in `among` pays the same
    EXACT = "exact"  # values are amounts and must add up to the total
    PERCENT = "percent"  # values are percentages and must add up to 100
    SHARES = "shares"  # values are weights, e.g. 2 shares for a couple


@dataclass
class Split:
    kind: SplitKind
    # Members taking part, in order. For EQUAL only this is used; for the other
    # kinds it is the keys of `values`.
    among: list[str]
    values: dict[str, Decimal] = field(default_factory=dict)

    @classmethod
    def equal(cls, among: list[str]) -> Split:
        return cls(SplitKind.EQUAL, list(among))

    @classmethod
    def weighted(cls, kind: SplitKind, values: dict[str, Decimal]) -> Split:
        return cls(kind, list(values), dict(values))

    def portions(self, total: Decimal) -> dict[str, Decimal]:
        """How much of ``total`` each member owes. Always adds up exactly."""
        if not self.among:
            raise SplitKaroError("an expense must be split among at least one member")
        if len(set(self.among)) != len(self.among):
            raise SplitKaroError("a member appears twice in the split")

        if self.kind is SplitKind.EQUAL:
            weights = [Decimal(1)] * len(self.among)
        elif self.kind is SplitKind.EXACT:
            amounts = {name: to_money(v) for name, v in self.values.items()}
            if any(v < ZERO for v in amounts.values()):
                raise SplitKaroError("exact amounts cannot be negative")
            if sum(amounts.values()) != total:
                raise SplitKaroError(
                    f"exact amounts add up to {sum(amounts.values())}, not the total {total}"
                )
            return amounts
        elif self.kind is SplitKind.PERCENT:
            if sum(self.values.values()) != HUNDRED:
                raise SplitKaroError(f"percentages add up to {sum(self.values.values())}, not 100")
            weights = [self.values[name] for name in self.among]
        else:
            weights = [self.values[name] for name in self.among]

        try:
            parts = allocate(total, weights)
        except MoneyError as exc:
            raise SplitKaroError(str(exc)) from None
        return dict(zip(self.among, parts))


@dataclass
class Member:
    name: str
    upi: str | None = None  # e.g. "asha@okbank", used for payment links


@dataclass
class Expense:
    id: int
    description: str
    amount: Decimal
    # Who paid, and how much each. Usually one person paid everything.
    paid_by: dict[str, Decimal]
    split: Split
    date: dt.date
    currency: str
    category: str = "general"
    note: str = ""

    def validate(self) -> None:
        if self.amount <= ZERO:
            raise SplitKaroError("an expense amount must be greater than zero")
        if not self.paid_by:
            raise SplitKaroError("an expense needs at least one payer")
        if any(v <= ZERO for v in self.paid_by.values()):
            raise SplitKaroError("each payer must have paid more than zero")
        paid = sum(self.paid_by.values())
        if paid != self.amount:
            raise SplitKaroError(f"payers paid {paid} in total, but the expense is {self.amount}")
        self.split.portions(self.amount)  # raises if the split is inconsistent


@dataclass
class Transfer:
    """Money handed from one member to another to settle up."""

    sender: str
    receiver: str
    amount: Decimal
    date: dt.date | None = None
    note: str = ""


@dataclass
class Group:
    name: str
    currency: str = "INR"
    members: list[Member] = field(default_factory=list)
    expenses: list[Expense] = field(default_factory=list)
    transfers: list[Transfer] = field(default_factory=list)
    # Value of one unit of a foreign currency in the group currency,
    # e.g. {"USD": Decimal("83.20")} for a group that keeps accounts in INR.
    rates: dict[str, Decimal] = field(default_factory=dict)
    next_id: int = 1

    # -- members -------------------------------------------------------

    def member(self, name: str) -> Member:
        for m in self.members:
            if m.name.casefold() == name.casefold():
                return m
        known = ", ".join(m.name for m in self.members) or "nobody yet"
        raise SplitKaroError(f"no member called {name!r} (members: {known})")

    def resolve(self, name: str) -> str:
        """Return the member's canonical spelling; names are case-insensitive."""
        return self.member(name).name

    def add_member(self, name: str, upi: str | None = None) -> Member:
        name = name.strip()
        if not name:
            raise SplitKaroError("a member needs a name")
        if any(m.name.casefold() == name.casefold() for m in self.members):
            raise SplitKaroError(f"{name!r} is already a member")
        member = Member(name, upi)
        self.members.append(member)
        return member

    def remove_member(self, name: str) -> None:
        name = self.resolve(name)
        if self._mentions(name):
            raise SplitKaroError(f"{name} appears in expenses or payments; settle up and delete those first")
        self.members = [m for m in self.members if m.name != name]

    def _mentions(self, name: str) -> bool:
        for e in self.expenses:
            if name in e.paid_by or name in e.split.among:
                return True
        return any(name in (t.sender, t.receiver) for t in self.transfers)

    # -- expenses and payments ----------------------------------------

    def add_expense(self, expense: Expense) -> Expense:
        expense.amount = to_money(expense.amount)
        expense.paid_by = {self.resolve(k): to_money(v) for k, v in expense.paid_by.items()}
        expense.split.among = [self.resolve(n) for n in expense.split.among]
        expense.split.values = {self.resolve(k): v for k, v in expense.split.values.items()}
        if expense.currency != self.currency and expense.currency not in self.rates:
            cur = expense.currency
            raise SplitKaroError(f"no exchange rate for {cur}; set one with: splitkaro rate {cur} <value>")
        expense.validate()
        expense.id = self.next_id
        self.next_id += 1
        self.expenses.append(expense)
        return expense

    def expense(self, expense_id: int) -> Expense:
        for e in self.expenses:
            if e.id == expense_id:
                return e
        raise SplitKaroError(f"no expense with id {expense_id}")

    def delete_expense(self, expense_id: int) -> Expense:
        expense = self.expense(expense_id)
        self.expenses.remove(expense)
        return expense

    def add_transfer(self, transfer: Transfer) -> Transfer:
        transfer.sender = self.resolve(transfer.sender)
        transfer.receiver = self.resolve(transfer.receiver)
        transfer.amount = to_money(transfer.amount)
        if transfer.sender == transfer.receiver:
            raise SplitKaroError("a member cannot pay themselves")
        if transfer.amount <= ZERO:
            raise SplitKaroError("a payment must be greater than zero")
        self.transfers.append(transfer)
        return transfer

    def to_group_currency(self, amount: Decimal, currency: str) -> Decimal:
        if currency == self.currency:
            return amount
        return to_money(amount * self.rates[currency])
