import unittest
from decimal import Decimal as D

from helpers import make_group, spend
from splitkaro.models import Split, SplitKaroError, SplitKind, Transfer


class SplitTests(unittest.TestCase):
    def test_equal(self):
        self.assertEqual(Split.equal(["A", "B"]).portions(D("10.01")), {"A": D("5.01"), "B": D("5.00")})

    def test_exact(self):
        split = Split.weighted(SplitKind.EXACT, {"A": D("300"), "B": D("900")})
        self.assertEqual(split.portions(D("1200.00")), {"A": D("300.00"), "B": D("900.00")})
        with self.assertRaisesRegex(SplitKaroError, "add up to 1200.00, not the total 1000.00"):
            split.portions(D("1000.00"))

    def test_percent(self):
        split = Split.weighted(SplitKind.PERCENT, {"A": D("40"), "B": D("60")})
        self.assertEqual(split.portions(D("500.00")), {"A": D("200.00"), "B": D("300.00")})
        with self.assertRaisesRegex(SplitKaroError, "not 100"):
            Split.weighted(SplitKind.PERCENT, {"A": D("40"), "B": D("50")}).portions(D("1.00"))

    def test_shares(self):
        split = Split.weighted(SplitKind.SHARES, {"Couple": D(2), "Single": D(1)})
        self.assertEqual(split.portions(D("3000.00")), {"Couple": D("2000.00"), "Single": D("1000.00")})

    def test_invalid_splits(self):
        with self.assertRaises(SplitKaroError):
            Split.equal([]).portions(D("1.00"))
        with self.assertRaises(SplitKaroError):
            Split.equal(["A", "A"]).portions(D("1.00"))
        with self.assertRaises(SplitKaroError):
            Split.weighted(SplitKind.SHARES, {"A": D(0)}).portions(D("1.00"))


class GroupTests(unittest.TestCase):
    def test_members_are_case_insensitive_and_unique(self):
        group = make_group("Asha")
        self.assertEqual(group.resolve("ASHA"), "Asha")
        with self.assertRaisesRegex(SplitKaroError, "already a member"):
            group.add_member("asha")
        with self.assertRaisesRegex(SplitKaroError, "no member called 'Zoe'"):
            group.resolve("Zoe")

    def test_expense_names_are_normalised(self):
        group = make_group("Asha", "Ravi")
        expense = spend(group, "100", "asha", Split.equal(["ASHA", "ravi"]))
        self.assertEqual(expense.paid_by, {"Asha": D("100")})
        self.assertEqual(expense.split.among, ["Asha", "Ravi"])

    def test_ids_increase_and_survive_deletion(self):
        group = make_group("A", "B")
        first = spend(group, "10", "A")
        group.delete_expense(first.id)
        self.assertEqual(spend(group, "10", "A").id, 2)

    def test_expense_validation(self):
        group = make_group("A", "B")
        with self.assertRaisesRegex(SplitKaroError, "greater than zero"):
            spend(group, "0", "A")
        with self.assertRaisesRegex(SplitKaroError, "payers paid 50.00 in total"):
            spend(group, "100", {"A": "30", "B": "20"})
        with self.assertRaisesRegex(SplitKaroError, "no exchange rate for USD"):
            spend(group, "10", "A", currency="USD")

    def test_cannot_remove_member_with_history(self):
        group = make_group("A", "B", "C")
        spend(group, "10", "A", Split.equal(["A", "B"]))
        with self.assertRaisesRegex(SplitKaroError, "appears in expenses"):
            group.remove_member("B")
        group.remove_member("C")
        self.assertEqual([m.name for m in group.members], ["A", "B"])

    def test_transfer_validation(self):
        group = make_group("A", "B")
        with self.assertRaisesRegex(SplitKaroError, "cannot pay themselves"):
            group.add_transfer(Transfer("A", "a", D("1")))
        with self.assertRaisesRegex(SplitKaroError, "greater than zero"):
            group.add_transfer(Transfer("A", "B", D("0")))


if __name__ == "__main__":
    unittest.main()
