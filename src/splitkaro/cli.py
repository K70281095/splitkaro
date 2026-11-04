"""Command-line interface for splitkaro."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from decimal import Decimal

from splitkaro import __version__
from splitkaro.csvio import export_csv, import_csv
from splitkaro.ledger import balances, settle, statement
from splitkaro.models import Expense, Group, Split, SplitKaroError, SplitKind, Transfer
from splitkaro.money import MoneyError, format_money, to_decimal, to_money
from splitkaro.report import build_report, filter_expenses
from splitkaro.storage import DEFAULT_FILE, load, save
from splitkaro.upi import is_valid_vpa, payment_link

EXIT_OK = 0
EXIT_ERROR = 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="splitkaro",
        description="Split shared expenses fairly and settle up with the fewest payments.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "-f",
        "--file",
        default=os.environ.get("SPLITKARO_FILE", DEFAULT_FILE),
        help=f"group file (default: $SPLITKARO_FILE or {DEFAULT_FILE})",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    p = sub.add_parser("init", help="start a new group")
    p.add_argument("name", help='group name, e.g. "Goa trip" or "Flat 302"')
    p.add_argument("--currency", default="INR", help="currency the accounts are kept in (default: INR)")
    p.add_argument("--force", action="store_true", help="overwrite an existing group file")

    p = sub.add_parser("member", help="add, list or remove members")
    msub = p.add_subparsers(dest="member_command", metavar="ACTION")
    msub.required = True
    m = msub.add_parser("add", help="add a member")
    m.add_argument("names", nargs="+", help="one or more names")
    m.add_argument("--upi", help="UPI ID for payment links (only with a single name)")
    msub.add_parser("list", help="list members")
    m = msub.add_parser("remove", help="remove a member with no expenses or payments")
    m.add_argument("name")
    m = msub.add_parser("upi", help="set a member's UPI ID")
    m.add_argument("name")
    m.add_argument("upi", help="e.g. asha@okbank")

    p = sub.add_parser("add", help="record an expense")
    p.add_argument("description", help='what it was for, e.g. "Dinner at Fisherman\'s Wharf"')
    p.add_argument("amount", help="total amount, e.g. 1200 or 1,250.50")
    p.add_argument(
        "--paid-by",
        action="append",
        required=True,
        metavar="NAME[=AMOUNT]",
        help="who paid; repeat with NAME=AMOUNT when several people paid",
    )
    how = p.add_mutually_exclusive_group()
    how.add_argument("--among", metavar="A,B,C", help="split equally among these members (default: everyone)")
    how.add_argument("--exact", metavar="A=300,B=900", help="split by exact amounts")
    how.add_argument("--percent", metavar="A=40,B=60", help="split by percentages (must add up to 100)")
    how.add_argument("--shares", metavar="A=2,B=1", help="split by shares, e.g. a couple counts as 2")
    p.add_argument("--category", default="general", help="e.g. food, travel, rent (default: general)")
    p.add_argument("--date", help="YYYY-MM-DD (default: today)")
    p.add_argument("--currency", help="currency of this expense if different from the group's")
    p.add_argument("--note", default="", help="free text")

    p = sub.add_parser("list", help="list expenses")
    _add_filters(p)

    p = sub.add_parser("delete", help="delete an expense by id")
    p.add_argument("id", type=int)

    p = sub.add_parser("balances", help="show who is owed and who owes")
    p.add_argument("--json", action="store_true", help="machine-readable output")

    p = sub.add_parser("settle", help="suggest the fewest payments to settle up")
    p.add_argument(
        "--upi", action="store_true", help="include UPI payment links when the receiver has a UPI ID"
    )
    p.add_argument("--json", action="store_true", help="machine-readable output")

    p = sub.add_parser("pay", help="record a payment between members")
    p.add_argument("sender", help="who paid")
    p.add_argument("receiver", help="who received the money")
    p.add_argument("amount")
    p.add_argument("--date", help="YYYY-MM-DD (default: today)")
    p.add_argument("--note", default="")

    p = sub.add_parser("statement", help="every entry that changed one member's balance")
    p.add_argument("name")

    p = sub.add_parser("report", help="spending by category, month and member")
    _add_filters(p)
    p.add_argument("--json", action="store_true", help="machine-readable output")

    p = sub.add_parser("rate", help="set the exchange rate for a foreign currency")
    p.add_argument("currency", help="e.g. USD")
    p.add_argument("value", help="value of 1 unit in the group currency, e.g. 83.20")

    p = sub.add_parser("export", help="export expenses to CSV")
    p.add_argument("path", help="file to write, or - for standard output")

    p = sub.add_parser("import", help="import expenses from CSV (all rows or none)")
    p.add_argument("path", help="file to read, or - for standard input")

    return parser


def _add_filters(p: argparse.ArgumentParser) -> None:
    p.add_argument("--month", help="only this month, YYYY-MM")
    p.add_argument("--category", help="only this category")
    p.add_argument("--member", help="only expenses this member paid for or shares in")


def main(argv: list[str] | None = None) -> int:
    # Some consoles (e.g. Windows code pages) cannot print "₹"; show "?" instead of crashing.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init":
            return _cmd_init(args)
        group = load(args.file)
        handler = COMMANDS[args.command]
        changed = handler(group, args)
        if changed:
            save(group, args.file)
        return EXIT_OK
    except (SplitKaroError, MoneyError) as exc:
        print(f"splitkaro: {exc}", file=sys.stderr)
        return EXIT_ERROR


# Each handler returns True when the group changed and must be saved.


def _cmd_init(args: argparse.Namespace) -> int:
    if os.path.exists(args.file) and not args.force:
        raise SplitKaroError(f"{args.file} already exists (use --force to overwrite)")
    group = Group(name=args.name, currency=args.currency.upper())
    save(group, args.file)
    print(f"Created group {args.name!r} in {args.file} ({group.currency}).")
    print("Next: splitkaro member add <name> <name> ...")
    return EXIT_OK


def _cmd_member(group: Group, args: argparse.Namespace) -> bool:
    if args.member_command == "add":
        if args.upi and len(args.names) > 1:
            raise SplitKaroError("--upi can only be used when adding one member")
        if args.upi and not is_valid_vpa(args.upi):
            raise SplitKaroError(f"{args.upi!r} does not look like a UPI ID (expected name@bank)")
        for name in args.names:
            group.add_member(name, args.upi)
        print(f"Added {', '.join(args.names)}.")
        return True
    if args.member_command == "remove":
        group.remove_member(args.name)
        print(f"Removed {args.name}.")
        return True
    if args.member_command == "upi":
        if not is_valid_vpa(args.upi):
            raise SplitKaroError(f"{args.upi!r} does not look like a UPI ID (expected name@bank)")
        group.member(args.name).upi = args.upi
        print(f"Set UPI ID for {group.resolve(args.name)}.")
        return True

    if not group.members:
        print("No members yet. Add some with: splitkaro member add <name> ...")
    for m in group.members:
        print(f"{m.name}{'  (' + m.upi + ')' if m.upi else ''}")
    return False


def _cmd_add(group: Group, args: argparse.Namespace) -> bool:
    if not group.members:
        raise SplitKaroError("add members first: splitkaro member add <name> ...")
    amount = to_money(args.amount)

    if args.exact:
        split = Split.weighted(SplitKind.EXACT, _parse_pairs(args.exact, to_money))
    elif args.percent:
        split = Split.weighted(SplitKind.PERCENT, _parse_pairs(args.percent, to_decimal))
    elif args.shares:
        split = Split.weighted(SplitKind.SHARES, _parse_pairs(args.shares, to_decimal))
    else:
        among = [n.strip() for n in args.among.split(",")] if args.among else [m.name for m in group.members]
        split = Split.equal(among)

    expense = group.add_expense(
        Expense(
            id=0,
            description=args.description,
            amount=amount,
            paid_by=_parse_payers(args.paid_by, amount),
            split=split,
            date=_parse_date(args.date),
            currency=(args.currency or group.currency).upper(),
            category=args.category,
            note=args.note,
        )
    )
    print(f"Added #{expense.id}: {expense.description}, {format_money(expense.amount, expense.currency)}")
    for name, portion in expense.split.portions(expense.amount).items():
        print(f"  {name:<16} {format_money(portion, expense.currency):>14}")
    return True


def _cmd_list(group: Group, args: argparse.Namespace) -> bool:
    expenses = filter_expenses(group, args.month, args.category, args.member)
    if not expenses:
        print("No expenses.")
        return False
    for e in expenses:
        payers = ", ".join(e.paid_by)
        print(
            f"#{e.id:<4} {e.date}  {format_money(e.amount, e.currency):>14}  "
            f"{e.description}  [{e.category}]  paid by {payers}"
        )
    return False


def _cmd_delete(group: Group, args: argparse.Namespace) -> bool:
    expense = group.delete_expense(args.id)
    print(f"Deleted #{expense.id}: {expense.description}")
    return True


def _cmd_balances(group: Group, args: argparse.Namespace) -> bool:
    net = balances(group)
    if args.json:
        _print_json({"currency": group.currency, "balances": {k: str(v) for k, v in net.items()}})
        return False
    for name, amount in sorted(net.items(), key=lambda kv: (-kv[1], kv[0])):
        if amount > 0:
            status = f"gets back {format_money(amount, group.currency)}"
        elif amount < 0:
            status = f"owes {format_money(-amount, group.currency)}"
        else:
            status = "settled up"
        print(f"{name:<16} {status}")
    return False


def _cmd_settle(group: Group, args: argparse.Namespace) -> bool:
    plan = settle(balances(group))
    links = {}
    if args.upi:
        if group.currency != "INR":
            raise SplitKaroError("UPI links are only available for groups that use INR")
        for t in plan:
            vpa = group.member(t.receiver).upi
            if vpa:
                links[id(t)] = payment_link(vpa, t.receiver, t.amount, note=f"splitkaro: {group.name}")

    if args.json:
        _print_json(
            {
                "currency": group.currency,
                "payments": [
                    {"from": t.sender, "to": t.receiver, "amount": str(t.amount), "upi": links.get(id(t))}
                    for t in plan
                ],
            }
        )
        return False

    if not plan:
        print("Everyone is settled up. 🎉")
        return False
    print(f"{len(plan)} payment(s) settle everything:")
    for t in plan:
        print(f"  {t.sender} pays {t.receiver} {format_money(t.amount, group.currency)}")
        if id(t) in links:
            print(f"    {links[id(t)]}")
    print("\nAfter paying, record it with: splitkaro pay <from> <to> <amount>")
    return False


def _cmd_pay(group: Group, args: argparse.Namespace) -> bool:
    t = group.add_transfer(
        Transfer(args.sender, args.receiver, to_money(args.amount), _parse_date(args.date), args.note)
    )
    print(f"Recorded: {t.sender} paid {t.receiver} {format_money(t.amount, group.currency)}")
    return True


def _cmd_statement(group: Group, args: argparse.Namespace) -> bool:
    lines = statement(group, args.name)
    running = Decimal("0.00")
    for line in lines:
        running += line.change
        print(
            f"{line.date:<10}  {format_money(line.change, group.currency):>14}  "
            f"{format_money(running, group.currency):>14}  {line.description}"
        )
    name = group.resolve(args.name)
    if running > 0:
        print(f"\n{name} gets back {format_money(running, group.currency)}")
    elif running < 0:
        print(f"\n{name} owes {format_money(-running, group.currency)}")
    else:
        print(f"\n{name} is settled up")
    return False


def _cmd_report(group: Group, args: argparse.Namespace) -> bool:
    report = build_report(group, filter_expenses(group, args.month, args.category, args.member))
    if args.json:
        _print_json(
            {
                "currency": group.currency,
                "total": str(report.total),
                "count": report.count,
                "by_category": {k: str(v) for k, v in report.by_category.items()},
                "by_month": {k: str(v) for k, v in report.by_month.items()},
                "paid_by_member": {k: str(v) for k, v in report.paid_by_member.items()},
                "share_by_member": {k: str(v) for k, v in report.share_by_member.items()},
            }
        )
        return False

    cur = group.currency
    print(f"{group.name}: {report.count} expense(s), {format_money(report.total, cur)} in total\n")
    print("By category")
    for name, amount in report.by_category.items():
        print(f"  {name:<16} {format_money(amount, cur):>14}  {_percent(amount, report.total)}")
    print("\nBy month")
    for month, amount in report.by_month.items():
        print(f"  {month:<16} {format_money(amount, cur):>14}")
    print(f"\n  {'member':<16} {'paid':>14} {'share':>14}")
    for name in report.paid_by_member:
        print(
            f"  {name:<16} {format_money(report.paid_by_member[name], cur):>14} "
            f"{format_money(report.share_by_member[name], cur):>14}"
        )
    return False


def _cmd_rate(group: Group, args: argparse.Namespace) -> bool:
    currency = args.currency.upper()
    if currency == group.currency:
        raise SplitKaroError(f"{currency} is already the group currency")
    value = to_decimal(args.value)
    if value <= 0:
        raise SplitKaroError("an exchange rate must be greater than zero")
    group.rates[currency] = value
    print(f"1 {currency} = {value} {group.currency}")
    return True


def _cmd_export(group: Group, args: argparse.Namespace) -> bool:
    if args.path == "-":
        export_csv(group, sys.stdout)
        return False
    with open(args.path, "w", encoding="utf-8", newline="") as handle:
        count = export_csv(group, handle)
    print(f"Exported {count} expense(s) to {args.path}")
    return False


def _cmd_import(group: Group, args: argparse.Namespace) -> bool:
    try:
        if args.path == "-":
            added = import_csv(group, sys.stdin)
        else:
            with open(args.path, encoding="utf-8-sig", newline="") as handle:
                added = import_csv(group, handle)
    except FileNotFoundError:
        raise SplitKaroError(f"{args.path} not found") from None
    print(f"Imported {len(added)} expense(s).")
    return bool(added)


COMMANDS = {
    "member": _cmd_member,
    "add": _cmd_add,
    "list": _cmd_list,
    "delete": _cmd_delete,
    "balances": _cmd_balances,
    "settle": _cmd_settle,
    "pay": _cmd_pay,
    "statement": _cmd_statement,
    "report": _cmd_report,
    "rate": _cmd_rate,
    "export": _cmd_export,
    "import": _cmd_import,
}


def _parse_pairs(text: str, parse) -> dict[str, Decimal]:
    pairs = {}
    for item in text.split(","):
        name, sep, value = item.partition("=")
        if not sep or not name.strip():
            raise SplitKaroError(f"expected NAME=VALUE, got {item.strip()!r}")
        pairs[name.strip()] = parse(value)
    return pairs


def _parse_payers(values: list[str], amount: Decimal) -> dict[str, Decimal]:
    if len(values) == 1 and "=" not in values[0]:
        return {values[0].strip(): amount}
    payers: dict[str, Decimal] = {}
    for value in values:
        if "=" not in value:
            raise SplitKaroError("with several payers, give each as NAME=AMOUNT")
        payers.update(_parse_pairs(value, to_money))
    return payers


def _parse_date(value: str | None) -> dt.date:
    if not value:
        return dt.date.today()
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        raise SplitKaroError(f"invalid date {value!r}; use YYYY-MM-DD") from None


def _percent(part: Decimal, total: Decimal) -> str:
    if not total:
        return ""
    return f"{(part / total * 100):.0f}%"


def _print_json(data: object) -> None:
    json.dump(data, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    sys.exit(main())
