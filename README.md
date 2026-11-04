# splitkaro: split expenses & settle up with UPI

**A bill splitter for friends, flatmates and trips: track shared expenses, see who owes whom, and settle up with the fewest payments and one-tap UPI links.**

[![CI](https://github.com/K70281095/splitkaro/actions/workflows/ci.yml/badge.svg)](https://github.com/K70281095/splitkaro/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.9%20%E2%80%93%203.13-blue)
![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

*Split karo* is Hinglish for "split it". It is the phrase every group says at the end of a trip,
right before the *hisaab* (the accounts) gets complicated.

Every trip, every shared flat and every office lunch ends with the same questions:

- Who paid for what, and who still owes whom?
- The hotel was ₹9,000, but a couple shared one room. How do we split that fairly?
- Five people owe each other money. Do we really need ten transfers?
- Somebody paid in dollars. What is that in rupees?

`splitkaro` answers all of them from your terminal. It keeps the group's records in one readable
JSON file, does every calculation with exact decimal arithmetic so the totals always add up to
the paisa, and works out the smallest set of payments that settles everyone, with UPI links you
can open in GPay, PhonePe, Paytm or BHIM.

```console
$ splitkaro balances
Asha             gets back ₹2,618.00
Ravi             owes ₹682.00
Meera            owes ₹1,936.00

$ splitkaro settle --upi
2 payment(s) settle everything:
  Meera pays Asha ₹1,936.00
    upi://pay?pa=asha%40okbank&pn=Asha&am=1936.00&cu=INR&tn=splitkaro%3A+Goa+trip
  Ravi pays Asha ₹682.00
    upi://pay?pa=asha%40okbank&pn=Asha&am=682.00&cu=INR&tn=splitkaro%3A+Goa+trip
```

---

## Contents

- [Features](#features)
- [Install](#install)
- [A full example: a Goa trip](#a-full-example-a-goa-trip)
- [Ways to split](#ways-to-split)
- [Command reference](#command-reference)
- [Your data](#your-data)
- [Using splitkaro from Python](#using-splitkaro-from-python)
- [How it works](#how-it-works)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

## Features

| | |
|---|---|
| **Four ways to split** | Equally, by exact amounts, by percentage, or by shares (a couple counts as 2). |
| **Several payers** | "I paid ₹1,000 and you paid ₹500" for the same bill works naturally. |
| **Fewest payments** | Suggests at most *n − 1* transfers for *n* people, and pairs up exact matches first. |
| **UPI links** | One `upi://pay` link per payment; the payer just confirms it in their app. |
| **Exact to the paisa** | Decimal arithmetic and fair rounding: ₹100 split three ways is 33.34 + 33.33 + 33.33. |
| **Foreign currency** | Record an expense in USD or EUR; it is converted with the rate you set. |
| **Reports** | Spending by category and month, and who paid vs. who consumed. |
| **Statements** | A running, line-by-line history of one person's balance. |
| **CSV import/export** | Move data to and from spreadsheets. Imports are all-or-nothing. |
| **Your data, your file** | Plain JSON you can read, back up, sync or put under git. No account, no server, no ads. |
| **Zero dependencies** | Pure Python standard library, Python 3.9+. |

## Install

```bash
pip install splitkaro
```

Or straight from GitHub:

```bash
pip install git+https://github.com/K70281095/splitkaro.git
```

Check it works:

```bash
splitkaro --version
```

## A full example: a Goa trip

Asha, Ravi and Meera go to Goa. Asha travels with her partner, so on the hotel she counts as two.

```bash
splitkaro init "Goa trip"
splitkaro member add Asha Ravi Meera
splitkaro member upi Asha asha@okbank          # so others can pay her with one tap

# Hotel: Asha paid, split by shares (Asha 2, Ravi 1, Meera 1)
splitkaro add "Hotel (2 nights)" 9000 --paid-by Asha --shares Asha=2,Ravi=1,Meera=1 --category stay

# Dinner: Ravi paid, split equally among everyone (the default)
splitkaro add "Dinner at the shack" 2400 --paid-by Ravi --category food

# Scooters: two people paid, and only they used them
splitkaro add "Scooter rental" 1500 --paid-by Asha=1000 --paid-by Meera=500 --among Asha,Meera --category travel

# Parasailing was paid in dollars
splitkaro rate USD 83.20
splitkaro add "Parasailing" 30 --currency USD --paid-by Meera --category fun

# Groceries: everyone took different things
splitkaro add "Groceries" 1260 --paid-by Ravi --exact Asha=500,Ravi=460,Meera=300 --category food
```

Where does everyone stand, and how do they square up?

```console
$ splitkaro settle
2 payment(s) settle everything:
  Meera pays Asha ₹1,936.00
  Ravi pays Asha ₹682.00
```

Where did the money go?

```console
$ splitkaro report
Goa trip: 5 expense(s), ₹16,656.00 in total

By category
  stay                  ₹9,000.00  54%
  food                  ₹3,660.00  22%
  fun                   ₹2,496.00  15%
  travel                ₹1,500.00  9%

By month
  2026-11              ₹16,656.00

  member                     paid          share
  Asha                 ₹10,000.00      ₹7,382.00
  Ravi                  ₹3,660.00      ₹4,342.00
  Meera                 ₹2,996.00      ₹4,932.00
```

Meera wants to see exactly how she ended up owing ₹1,936:

```console
$ splitkaro statement meera
2026-11-01      -₹2,250.00      -₹2,250.00  #1 Hotel (2 nights)
2026-11-01        -₹800.00      -₹3,050.00  #2 Dinner at the shack
2026-11-02        -₹250.00      -₹3,300.00  #3 Scooter rental
2026-11-02       ₹1,664.00      -₹1,636.00  #4 Parasailing
2026-11-03        -₹300.00      -₹1,936.00  #5 Groceries

Meera owes ₹1,936.00
```

Once the money has moved, record it, and everyone is back to zero:

```bash
splitkaro pay Meera Asha 1936
splitkaro pay Ravi Asha 682
splitkaro settle      # Everyone is settled up. 🎉
```

The same trip is available as [`examples/goa-trip.csv`](examples/goa-trip.csv), which you can
load with `splitkaro import examples/goa-trip.csv`.

## Ways to split

| Option | Example | Meaning |
|---|---|---|
| *(none)* | `--paid-by Ravi` | Equally among **all** members. |
| `--among` | `--among Asha,Meera` | Equally among the listed members. |
| `--exact` | `--exact Asha=500,Ravi=460,Meera=300` | Fixed amounts; must add up to the total. |
| `--percent` | `--percent Asha=50,Ravi=25,Meera=25` | Percentages; must add up to 100. |
| `--shares` | `--shares Asha=2,Ravi=1,Meera=1` | Proportional weights, e.g. couples, or nights stayed. |

Whoever paid is given with `--paid-by NAME`, or `--paid-by NAME=AMOUNT` repeated when several
people paid the same bill. Names are case-insensitive.

## Command reference

| Command | What it does |
|---|---|
| `splitkaro init NAME [--currency INR]` | Start a group (creates `splitkaro.json`). |
| `splitkaro member add NAME... [--upi ID]` | Add members. |
| `splitkaro member upi NAME ID` | Set a member's UPI ID. |
| `splitkaro member list` / `remove NAME` | List members, or remove one who has no history. |
| `splitkaro add DESC AMOUNT --paid-by ...` | Record an expense (`--category`, `--date`, `--currency`, `--note`). |
| `splitkaro list [--month YYYY-MM] [--category C] [--member M]` | List expenses. |
| `splitkaro delete ID` | Delete an expense. |
| `splitkaro balances [--json]` | Who gets money back, who owes. |
| `splitkaro settle [--upi] [--json]` | Fewest payments to settle everything. |
| `splitkaro pay FROM TO AMOUNT` | Record a payment between members. |
| `splitkaro statement NAME` | Running history of one member's balance. |
| `splitkaro report [filters] [--json]` | Totals by category, month and member. |
| `splitkaro rate CUR VALUE` | Exchange rate: 1 CUR = VALUE in the group currency. |
| `splitkaro export FILE` / `import FILE` | CSV out and in (`-` for stdout/stdin). |

Every command accepts `--file PATH` (or the `SPLITKARO_FILE` environment variable) to work with
more than one group, for example `splitkaro -f flat.json balances`.

Errors are printed as `splitkaro: <message>` with exit code `1`, and nothing is saved when a command
fails.

## Your data

A group lives in a single JSON file, `splitkaro.json` by default (shortened here):

```json
{
  "version": 1,
  "name": "Goa trip",
  "currency": "INR",
  "members": [{ "name": "Asha", "upi": "asha@okbank" }, { "name": "Ravi", "upi": null }],
  "expenses": [
    {
      "id": 2,
      "date": "2026-11-01",
      "description": "Dinner at the shack",
      "amount": "2400.00",
      "paid_by": { "Ravi": "2400.00" },
      "split": { "kind": "equal", "among": ["Asha", "Ravi", "Meera"], "values": {} }
    }
  ]
}
```

- Amounts are stored as strings, never floats, so nothing is ever rounded away.
- Files are written atomically: a crash or a full disk cannot leave a half-written file.
- There is no account, server or tracking. Share the file however your group likes.

The CSV format is documented in [docs/csv-format.md](docs/csv-format.md).

## Using splitkaro from Python

```python
import datetime as dt
from decimal import Decimal

from splitkaro import Expense, Group, Split, balances, settle

group = Group("Flat 302")
for name in ("Asha", "Ravi", "Meera"):
    group.add_member(name)

group.add_expense(Expense(
    id=0, description="Electricity", amount=Decimal("3120"),
    paid_by={"Ravi": Decimal("3120")}, split=Split.equal(["Asha", "Ravi", "Meera"]),
    date=dt.date(2026, 11, 5), currency="INR", category="bills",
))

for t in settle(balances(group)):
    print(f"{t.sender} pays {t.receiver} {t.amount}")
```

## How it works

- **Rounding:** amounts are split with the largest-remainder method on whole paise, so the parts
  always add up to the exact total and nobody is ever short-changed by more than one paisa.
- **Balances:** each member's balance is what they paid minus their share, plus payments made
  minus payments received. Balances always add up to exactly zero.
- **Settling:** exact matches (someone owes exactly what someone else is owed) are paired first;
  the rest is settled greedily between the largest debtor and the largest creditor. This never
  needs more than *n − 1* payments.

The details, with worked examples, are in [docs/how-it-works.md](docs/how-it-works.md).

## Roadmap

- [ ] Recurring expenses (rent, Wi-Fi, maid) added automatically each month
- [ ] UPI QR codes in the terminal
- [ ] Simplify across groups (one payment per pair of people for several trips)
- [ ] Budgets per category with warnings
- [ ] Hindi and other Indian language output
- [ ] A small web or mobile front end on top of the same file format

Ideas and pull requests are welcome, see the [issues](https://github.com/K70281095/splitkaro/issues).

## Contributing

Bug reports, ideas, translations and code are all welcome. Please read
[CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md). To report a
security problem, see [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE) © 2026 Kanhaiya Kumar

*UPI is a system of the National Payments Corporation of India. splitkaro only creates standard
`upi://pay` links and never handles money, bank details or PINs.*
