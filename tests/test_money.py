import random
import unittest
from decimal import Decimal as D

from splitkaro.money import MoneyError, allocate, format_money, to_money


class ToMoneyTests(unittest.TestCase):
    def test_parsing(self):
        self.assertEqual(to_money("1200"), D("1200.00"))
        self.assertEqual(to_money("1,250.505"), D("1250.51"))  # half up
        self.assertEqual(to_money(7), D("7.00"))
        self.assertEqual(to_money(0.1), D("0.10"))

    def test_invalid(self):
        for bad in ["", "abc", "NaN", "Infinity", "12..5"]:
            with self.subTest(bad=bad), self.assertRaises(MoneyError):
                to_money(bad)


class AllocateTests(unittest.TestCase):
    def test_three_way_split_adds_up(self):
        self.assertEqual(allocate(D("100.00"), [D(1)] * 3), [D("33.34"), D("33.33"), D("33.33")])

    def test_weighted(self):
        self.assertEqual(
            allocate(D("9000.00"), [D(2), D(1), D(1)]), [D("4500.00"), D("2250.00"), D("2250.00")]
        )

    def test_negative_total(self):
        self.assertEqual(allocate(D("-10.00"), [D(1)] * 3), [D("-3.34"), D("-3.33"), D("-3.33")])

    def test_zero_weight_gets_nothing(self):
        self.assertEqual(allocate(D("10.00"), [D(1), D(0)]), [D("10.00"), D("0.00")])

    def test_always_adds_up_exactly(self):
        rng = random.Random(42)
        for _ in range(500):
            total = D(rng.randint(1, 10_000_000)) / 100
            weights = [D(rng.randint(0, 9)) for _ in range(rng.randint(1, 12))]
            if sum(weights) == 0:
                weights[0] = D(1)
            parts = allocate(total, weights)
            self.assertEqual(sum(parts), total)
            self.assertTrue(all(p >= 0 for p in parts))

    def test_errors(self):
        with self.assertRaises(MoneyError):
            allocate(D("1.00"), [])
        with self.assertRaises(MoneyError):
            allocate(D("1.00"), [D(0)])
        with self.assertRaises(MoneyError):
            allocate(D("1.00"), [D(1), D(-1)])


class FormatTests(unittest.TestCase):
    def test_indian_grouping_for_rupees(self):
        self.assertEqual(format_money(D("1234567.5")), "₹12,34,567.50")
        self.assertEqual(format_money(D("999")), "₹999.00")
        self.assertEqual(format_money(D("-1500")), "-₹1,500.00")

    def test_other_currencies(self):
        self.assertEqual(format_money(D("1234567.5"), "USD"), "$1,234,567.50")
        self.assertEqual(format_money(D("12"), "CHF"), "12.00 CHF")


if __name__ == "__main__":
    unittest.main()
