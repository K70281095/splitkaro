"""Save a group as a readable JSON file (splitkaro.json by default).

Amounts are stored as strings ("1200.50") so no precision is ever lost, and
the file is written atomically so a crash can never leave it half-written.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import tempfile
from decimal import Decimal
from typing import Any

from splitkaro.models import Expense, Group, Member, Split, SplitKaroError, SplitKind, Transfer
from splitkaro.money import to_decimal, to_money

DEFAULT_FILE = "splitkaro.json"
SCHEMA_VERSION = 1


def load(path: str) -> Group:
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        raise SplitKaroError(f"{path} not found; create a group first with: splitkaro init <name>") from None
    except json.JSONDecodeError as exc:
        raise SplitKaroError(f"{path} is not valid JSON: {exc}") from None
    return from_dict(data)


def save(group: Group, path: str) -> None:
    text = json.dumps(to_dict(group), indent=2, ensure_ascii=False) + "\n"
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".splitkaro-", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def to_dict(group: Group) -> dict[str, Any]:
    return {
        "version": SCHEMA_VERSION,
        "name": group.name,
        "currency": group.currency,
        "next_id": group.next_id,
        "rates": {k: str(v) for k, v in group.rates.items()},
        "members": [{"name": m.name, "upi": m.upi} for m in group.members],
        "expenses": [_expense_to_dict(e) for e in group.expenses],
        "transfers": [
            {
                "from": t.sender,
                "to": t.receiver,
                "amount": str(t.amount),
                "date": t.date.isoformat() if t.date else None,
                "note": t.note,
            }
            for t in group.transfers
        ],
    }


def from_dict(data: dict[str, Any]) -> Group:
    version = data.get("version")
    if version != SCHEMA_VERSION:
        raise SplitKaroError(f"unsupported file version {version!r}; expected {SCHEMA_VERSION}")
    try:
        return Group(
            name=data["name"],
            currency=data["currency"],
            next_id=int(data["next_id"]),
            rates={k: to_decimal(v) for k, v in data.get("rates", {}).items()},
            members=[Member(m["name"], m.get("upi")) for m in data["members"]],
            expenses=[_expense_from_dict(e) for e in data["expenses"]],
            transfers=[
                Transfer(
                    t["from"],
                    t["to"],
                    to_money(t["amount"]),
                    dt.date.fromisoformat(t["date"]) if t.get("date") else None,
                    t.get("note", ""),
                )
                for t in data["transfers"]
            ],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise SplitKaroError(f"the file is damaged or incomplete ({exc})") from None


def _expense_to_dict(e: Expense) -> dict[str, Any]:
    return {
        "id": e.id,
        "date": e.date.isoformat(),
        "description": e.description,
        "amount": str(e.amount),
        "currency": e.currency,
        "category": e.category,
        "paid_by": {k: str(v) for k, v in e.paid_by.items()},
        "split": {
            "kind": e.split.kind.value,
            "among": e.split.among,
            "values": {k: str(v) for k, v in e.split.values.items()},
        },
        "note": e.note,
    }


def _expense_from_dict(d: dict[str, Any]) -> Expense:
    split = d["split"]
    values: dict[str, Decimal] = {k: to_decimal(v) for k, v in split.get("values", {}).items()}
    return Expense(
        id=int(d["id"]),
        description=d["description"],
        amount=to_money(d["amount"]),
        paid_by={k: to_money(v) for k, v in d["paid_by"].items()},
        split=Split(SplitKind(split["kind"]), list(split["among"]), values),
        date=dt.date.fromisoformat(d["date"]),
        currency=d["currency"],
        category=d.get("category", "general"),
        note=d.get("note", ""),
    )
