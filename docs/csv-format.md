# CSV format

`splitkaro export` writes, and `splitkaro import` reads, one expense per row.

```csv
date,description,amount,paid_by,split,split_kind,category,currency,note
2026-11-01,Hotel (2 nights),9000,Asha,Asha:2;Ravi:1;Meera:1,shares,stay,INR,
2026-11-01,Dinner at the shack,2400,Ravi,,equal,food,INR,
2026-11-02,Scooter rental,1500,Asha:1000;Meera:500,Asha;Meera,equal,travel,INR,
2026-11-03,Groceries,1260,Ravi,Asha:500;Ravi:460;Meera:300,exact,food,INR,
```

| Column | Required | Format |
|---|---|---|
| `date` | yes | `YYYY-MM-DD` |
| `description` | yes | any text |
| `amount` | yes | e.g. `1200`, `1,250.50` |
| `paid_by` | yes | one name (paid everything), or `name:amount` pairs separated by `;` |
| `split_kind` | no | `equal` (default), `exact`, `percent` or `shares` |
| `split` | no | for `equal`: names separated by `;` (empty = every member); otherwise `name:value` pairs |
| `category` | no | default `general` |
| `currency` | no | default: the group currency; others need `splitkaro rate` first |
| `note` | no | any text |
| `id` | no | written on export, ignored on import (new ids are assigned) |

Columns can be in any order. Members must already exist in the group (names are
case-insensitive).

## All or nothing

If any row is invalid, for example an unknown member or percentages that don't add up to 100,
the import stops with the row number and **nothing** is added:

```console
$ splitkaro import trip.csv
splitkaro: row 4: no member called 'Ravii' (members: Asha, Ravi, Meera)
```

Fix the row and import again.

## Spreadsheets

Export, open in Excel, Google Sheets or LibreOffice, and build any chart you like:

```bash
splitkaro export expenses.csv
```

Files with a UTF-8 byte-order mark (as saved by Excel) are read correctly.
