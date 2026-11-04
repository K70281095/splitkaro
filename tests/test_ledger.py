import random
import unittest
from decimal import Decimal as D

from helpers import make_group, spend
from splitkaro.ledger import balances, settle, statement
from splitkaro.models import Split, SplitKind, Transfer
from splitkaro.money import ZERO


def apply(net, plan):
    net = dict(net)
    for t in plan:
        net[t.sender] += t.amount
        net[t.receiver] -= t.amount
    return net


class BalanceTests(unittest.TestCase):
    def test_goa_trip(self):
        group = make_group("Asha", "Ravi", "Meera")
        spend(
            group,
            "9000",
            "Asha",
            Split.weighted(SplitKind.SHARES, {"Asha": D(2), "Ravi": D(1), "Meera": D(1)}),
        )
        spend(group, "2400", "Ravi")
        spend(group, "1500", {"Asha": "1000", "Meera": "500"}, Split.equal(["Asha", "Meera"]))
        self.assertEqual(
            balances(group), {"Asha": D("3950.00"), "Ravi": D("-650.00"), "Meera": D("-3300.00")}
        )

    def test_foreign_currency_is_converted(self):
        group = make_group("A", "B")
        group.rates["USD"] = D("83.20")
        spend(group, "30", "A", currency="USD")
        self.assertEqual(balances(group), {"A": D("1248.00"), "B": D("-1248.00")})

    def test_multi_payer_conversion_never_drifts(self):
        group = make_group("A", "B", "C")
        group.rates["EUR"] = D("90.137")
        spend(group, "10.01", {"A": "3.33", "B": "3.34", "C": "3.34"}, currency="EUR")
        self.assertEqual(sum(balances(group).values()), ZERO)

    def test_transfers_reduce_debt(self):
        group = make_group("A", "B")
        spend(group, "100", "A")
        group.add_transfer(Transfer("B", "A", D("50")))
        self.assertEqual(balances(group), {"A": ZERO, "B": ZERO})

    def test_balances_always_sum_to_zero(self):
        rng = random.Random(7)
        names = ["A", "B", "C", "D", "E"]
        group = make_group(*names)
        for _ in range(200):
            among = rng.sample(names, rng.randint(1, 5))
            amount = D(rng.randint(1, 500_000)) / 100
            spend(group, amount, rng.choice(names), Split.equal(among))
        self.assertEqual(sum(balances(group).values()), ZERO)


class SettleTests(unittest.TestCase):
    def test_nothing_to_settle(self):
        self.assertEqual(settle({"A": ZERO, "B": ZERO}), [])

    def test_exact_matches_are_paired_directly(self):
        net = {"A": D("100"), "B": D("30"), "C": D("-30"), "D": D("-100")}
        plan = settle(net)
        self.assertEqual(len(plan), 2)
        self.assertEqual(
            {(t.sender, t.receiver, t.amount) for t in plan}, {("C", "B", D("30")), ("D", "A", D("100"))}
        )

    def test_settles_everything_with_at_most_n_minus_1_payments(self):
        rng = random.Random(3)
        for _ in range(300):
            n = rng.randint(2, 9)
            values = [D(rng.randint(-100_000, 100_000)) / 100 for _ in range(n - 1)]
            values.append(-sum(values))
            net = {f"P{i}": v for i, v in enumerate(values)}
            plan = settle(net)
            self.assertTrue(all(v == ZERO for v in apply(net, plan).values()))
            nonzero = sum(1 for v in values if v != 0)
            self.assertLessEqual(len(plan), max(nonzero - 1, 0))
            self.assertTrue(all(t.amount > 0 for t in plan))

    def test_deterministic(self):
        net = {"A": D("10"), "B": D("10"), "C": D("-10"), "D": D("-10")}
        self.assertEqual(settle(net), settle(dict(reversed(list(net.items())))))


class StatementTests(unittest.TestCase):
    def test_running_total_matches_balance(self):
        group = make_group("A", "B")
        spend(group, "100", "A", day=1)
        spend(group, "40", "B", day=2)
        group.add_transfer(Transfer("B", "A", D("10")))
        lines = statement(group, "b")
        self.assertEqual(sum(line.change for line in lines), balances(group)["B"])
        self.assertEqual([line.description for line in lines][:2], ["#1 thing", "#2 thing"])


if __name__ == "__main__":
    unittest.main()
