import io
import json
import os
import tempfile
import unittest
from decimal import Decimal as D

from helpers import make_group, spend
from splitkaro.csvio import export_csv, import_csv
from splitkaro.ledger import balances
from splitkaro.models import Split, SplitKaroError, SplitKind, Transfer
from splitkaro.report import build_report, filter_expenses
from splitkaro.storage import load, save
from splitkaro.upi import is_valid_vpa, payment_link


def sample_group():
    group = make_group("Asha", "Ravi", "Meera")
    group.member("Asha").upi = "asha@okbank"
    group.rates["USD"] = D("83.20")
    spend(
        group,
        "9000",
        "Asha",
        Split.weighted(SplitKind.SHARES, {"Asha": D(2), "Ravi": D(1), "Meera": D(1)}),
        category="stay",
    )
    spend(
        group,
        "1200",
        {"Ravi": "700", "Meera": "500"},
        Split.weighted(SplitKind.PERCENT, {"Asha": D("50"), "Ravi": D("25"), "Meera": D("25")}),
        day=2,
        category="food",
    )
    spend(group, "30", "Meera", currency="USD", day=3, category="fun")
    group.add_transfer(Transfer("Ravi", "Asha", D("100")))
    return group


class StorageTests(unittest.TestCase):
    def test_round_trip_keeps_everything(self):
        group = sample_group()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "splitkaro.json")
            save(group, path)
            loaded = load(path)
            with open(path, encoding="utf-8") as handle:
                raw = json.load(handle)
        self.assertEqual(loaded, group)
        self.assertEqual(raw["expenses"][0]["amount"], "9000.00")  # strings, never floats

    def test_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "splitkaro.json")
            with self.assertRaisesRegex(SplitKaroError, "not found"):
                load(path)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("{broken")
            with self.assertRaisesRegex(SplitKaroError, "not valid JSON"):
                load(path)
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"version": 99}, handle)
            with self.assertRaisesRegex(SplitKaroError, "unsupported file version"):
                load(path)


class CsvTests(unittest.TestCase):
    def test_export_then_import_reproduces_balances(self):
        group = sample_group()
        group.transfers = []
        buffer = io.StringIO()
        self.assertEqual(export_csv(group, buffer), 3)

        fresh = make_group("Asha", "Ravi", "Meera")
        fresh.rates["USD"] = D("83.20")
        buffer.seek(0)
        added = import_csv(fresh, buffer)
        self.assertEqual(len(added), 3)
        self.assertEqual(balances(fresh), balances(group))

    def test_minimal_columns_and_defaults(self):
        group = make_group("A", "B")
        text = "date,description,amount,paid_by\n2026-11-01,Chai,40,a\n"
        (expense,) = import_csv(group, io.StringIO(text))
        self.assertEqual(
            (expense.paid_by, expense.split.among, expense.category),
            ({"A": D("40.00")}, ["A", "B"], "general"),
        )

    def test_import_is_all_or_nothing(self):
        group = make_group("A", "B")
        text = "date,description,amount,paid_by\n2026-11-01,Ok,10,A\n2026-11-02,Bad,10,Nobody\n"
        with self.assertRaisesRegex(SplitKaroError, "row 3: no member called 'Nobody'"):
            import_csv(group, io.StringIO(text))
        self.assertEqual((group.expenses, group.next_id), ([], 1))

    def test_missing_columns(self):
        with self.assertRaisesRegex(SplitKaroError, "missing column"):
            import_csv(make_group("A"), io.StringIO("date,amount\n"))


class UpiTests(unittest.TestCase):
    def test_link(self):
        link = payment_link("asha@okbank", "Asha Rao", D("450"), note="Goa trip")
        self.assertEqual(link, "upi://pay?pa=asha%40okbank&pn=Asha+Rao&am=450.00&cu=INR&tn=Goa+trip")

    def test_vpa_validation(self):
        self.assertTrue(is_valid_vpa("asha.rao-1@okicici"))
        for bad in ["asha", "@bank", "a@b", "asha@", "asha bank@ok", "asha@1bank"]:
            with self.subTest(bad=bad):
                self.assertFalse(is_valid_vpa(bad))
        with self.assertRaises(SplitKaroError):
            payment_link("nope", "X", D("1"))
        with self.assertRaises(SplitKaroError):
            payment_link("asha@okbank", "X", D("0"))


class ReportTests(unittest.TestCase):
    def test_report(self):
        group = sample_group()
        report = build_report(group, filter_expenses(group))
        self.assertEqual(report.total, D("12696.00"))
        self.assertEqual(list(report.by_category), ["stay", "fun", "food"])
        self.assertEqual(sum(report.paid_by_member.values()), report.total)
        self.assertEqual(sum(report.share_by_member.values()), report.total)

    def test_filters(self):
        group = sample_group()
        self.assertEqual(len(filter_expenses(group, category="FOOD")), 1)
        self.assertEqual(len(filter_expenses(group, month="2026-10")), 0)
        self.assertEqual([e.id for e in filter_expenses(group, member="asha")], [1, 2, 3])
        group.add_member("Zoe")
        self.assertEqual(filter_expenses(group, member="zoe"), [])


if __name__ == "__main__":
    unittest.main()
