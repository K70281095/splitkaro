import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

from splitkaro.cli import main


class CliTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.file = os.path.join(self._tmp.name, "trip.json")

    def tearDown(self):
        self._tmp.cleanup()

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(["--file", self.file, *argv])
        return code, out.getvalue(), err.getvalue()

    def ok(self, *argv):
        code, out, err = self.run_cli(*argv)
        self.assertEqual(code, 0, err)
        return out

    def setup_trip(self):
        self.ok("init", "Goa trip")
        self.ok("member", "add", "Asha", "Ravi", "Meera")
        self.ok("member", "upi", "asha", "asha@okbank")
        self.ok(
            "add",
            "Hotel",
            "9000",
            "--paid-by",
            "Asha",
            "--shares",
            "Asha=2,Ravi=1,Meera=1",
            "--date",
            "2026-11-01",
        )
        self.ok("add", "Dinner", "2400", "--paid-by", "Ravi", "--category", "food", "--date", "2026-11-01")

    def test_full_flow(self):
        self.setup_trip()
        balances = json.loads(self.ok("balances", "--json"))["balances"]
        self.assertEqual(balances, {"Asha": "3700.00", "Ravi": "-650.00", "Meera": "-3050.00"})

        plan = json.loads(self.ok("settle", "--json", "--upi"))["payments"]
        self.assertEqual(
            [(p["from"], p["to"], p["amount"]) for p in plan],
            [("Meera", "Asha", "3050.00"), ("Ravi", "Asha", "650.00")],
        )
        self.assertTrue(plan[0]["upi"].startswith("upi://pay?pa=asha%40okbank"))

        for payment in plan:
            self.ok("pay", payment["from"], payment["to"], payment["amount"])
        self.assertIn("Everyone is settled up", self.ok("settle"))

    def test_text_output(self):
        self.setup_trip()
        self.assertIn("Asha             gets back ₹3,700.00", self.ok("balances"))
        report = self.ok("report")
        self.assertIn("2 expense(s), ₹11,400.00 in total", report)
        self.assertIn("food", report)
        self.assertIn("#2", self.ok("list", "--category", "food"))
        self.assertIn("Ravi owes ₹650.00", self.ok("statement", "ravi"))

    def test_multiple_payers_and_exact_split(self):
        self.setup_trip()
        out = self.ok(
            "add",
            "Cab",
            "900",
            "--paid-by",
            "Asha=500",
            "--paid-by",
            "Ravi=400",
            "--exact",
            "Asha=300,Ravi=300,Meera=300",
        )
        self.assertIn("Added #3", out)

    def test_delete(self):
        self.setup_trip()
        self.ok("delete", "2")
        self.assertNotIn("Dinner", self.ok("list"))

    def test_foreign_currency_needs_rate(self):
        self.setup_trip()
        code, _, err = self.run_cli("add", "Parasailing", "30", "--paid-by", "Meera", "--currency", "usd")
        self.assertEqual(code, 1)
        self.assertIn("splitkaro rate USD", err)
        self.ok("rate", "usd", "83.20")
        self.ok("add", "Parasailing", "30", "--paid-by", "Meera", "--currency", "usd")

    def test_errors_exit_1_and_do_not_save(self):
        self.setup_trip()
        before = open(self.file, encoding="utf-8").read()
        for argv in (
            ["add", "X", "100", "--paid-by", "Nobody"],
            ["add", "X", "abc", "--paid-by", "Asha"],
            ["add", "X", "100", "--paid-by", "Asha", "--percent", "Asha=50"],
            ["add", "X", "100", "--paid-by", "Asha", "--date", "04/11/2026"],
            ["pay", "Asha", "Asha", "10"],
            ["member", "add", "Zoe", "--upi", "not-a-upi"],
        ):
            with self.subTest(argv=argv):
                code, _, err = self.run_cli(*argv)
                self.assertEqual(code, 1)
                self.assertTrue(err.startswith("splitkaro: "))
        self.assertEqual(open(self.file, encoding="utf-8").read(), before)

    def test_init_refuses_to_overwrite(self):
        self.ok("init", "A")
        self.assertEqual(self.run_cli("init", "B")[0], 1)
        self.ok("init", "B", "--force")

    def test_missing_group_file(self):
        code, _, err = self.run_cli("balances")
        self.assertEqual(code, 1)
        self.assertIn("splitkaro init", err)

    def test_csv_round_trip(self):
        self.setup_trip()
        csv_path = os.path.join(self._tmp.name, "out.csv")
        self.ok("export", csv_path)
        self.ok("delete", "1")
        self.ok("delete", "2")
        self.assertIn("Imported 2", self.ok("import", csv_path))
        balances = json.loads(self.ok("balances", "--json"))["balances"]
        self.assertEqual(balances["Asha"], "3700.00")


if __name__ == "__main__":
    unittest.main()
