"""Import and export expenses as CSV, for spreadsheets and other apps.

Columns (only ``date``, ``description``, ``amount`` and ``paid_by`` are required):

    date,description,amount,paid_by,split,split_kind,category,currency,note
    2026-11-02,Dinner,1200,Asha,,equal,food,INR,
    2026-11-03,Cab,900,Asha:500;Ravi:400,Asha;Ravi,equal,travel,INR,
    2026-11-03,Hotel,6000,Ravi,Asha:2;Ravi:1,shares,stay,INR,

``paid_by`` is one name (who paid everything) or ``name:amount`` pairs.
``split`` lists names for ``equal`` (empty means every member) or
``name:value`` pairs for ``exact``, ``percent`` and ``shares``.
"""

from __future__ import annotations

import copy
import csv
import datetime as dt
from typing import IO

from splitkaro.models import Expense, Group, Split, SplitKaroError, SplitKind
from splitkaro.money import MoneyError, to_decimal, to_money

COLUMNS = [
    "id",
    "date",
    "description",
    "amount",
    "currency",
    "category",
    "paid_by",
    "split_kind",
    "split",
    "note",
]
REQUIRED = {"date", "description", "amount", "paid_by"}


def export_csv(group: Group, handle: IO[str]) -> int:
    writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    for e in sorted(group.expenses, key=lambda x: (x.date, x.id)):
        if e.split.kind is SplitKind.EQUAL:
            split = ";".join(e.split.among)
        else:
            split = ";".join(f"{k}:{v}" for k, v in e.split.values.items())
        writer.writerow(
            {
                "id": e.id,
                "date": e.date.isoformat(),
                "description": e.description,
                "amount": str(e.amount),
                "currency": e.currency,
                "category": e.category,
                "paid_by": ";".join(f"{k}:{v}" for k, v in e.paid_by.items()),
                "split_kind": e.split.kind.value,
                "split": split,
                "note": e.note,
            }
        )
    return len(group.expenses)


def import_csv(group: Group, handle: IO[str]) -> list[Expense]:
    """Add every row as an expense. Either all rows are added, or none are."""
    reader = csv.DictReader(handle)
    missing = REQUIRED - set(reader.fieldnames or [])
    if missing:
        raise SplitKaroError(f"CSV is missing column(s): {', '.join(sorted(missing))}")

    trial = copy.deepcopy(group)
    added = []
    for row_number, row in enumerate(reader, start=2):
        try:
            added.append(trial.add_expense(_row_to_expense(trial, row)))
        except (SplitKaroError, MoneyError, ValueError) as exc:
            raise SplitKaroError(f"row {row_number}: {exc}") from None

    # Every row is valid, so apply the result to the real group.
    group.expenses, group.next_id = trial.expenses, trial.next_id
    return added


def _row_to_expense(group: Group, row: dict[str, str]) -> Expense:
    amount = to_money(row["amount"])
    currency = (row.get("currency") or group.currency).strip().upper()
    kind = SplitKind((row.get("split_kind") or "equal").strip().lower())
    split_text = (row.get("split") or "").strip()

    if kind is SplitKind.EQUAL:
        among = [n.strip() for n in split_text.split(";") if n.strip()] or [m.name for m in group.members]
        split = Split.equal(among)
    else:
        split = Split.weighted(kind, {k: to_decimal(v) for k, v in _pairs(split_text).items()})

    paid_text = row["paid_by"].strip()
    if ":" in paid_text:
        paid_by = {k: to_money(v) for k, v in _pairs(paid_text).items()}
    else:
        paid_by = {paid_text: amount}

    return Expense(
        id=0,
        description=row["description"].strip(),
        amount=amount,
        paid_by=paid_by,
        split=split,
        date=dt.date.fromisoformat(row["date"].strip()),
        currency=currency,
        category=(row.get("category") or "general").strip() or "general",
        note=(row.get("note") or "").strip(),
    )


def _pairs(text: str) -> dict[str, str]:
    pairs = {}
    for item in text.split(";"):
        if not item.strip():
            continue
        name, sep, value = item.partition(":")
        if not sep:
            raise SplitKaroError(f"expected name:value, got {item!r}")
        pairs[name.strip()] = value.strip()
    return pairs
