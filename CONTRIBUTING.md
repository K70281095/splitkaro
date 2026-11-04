# Contributing to splitkaro

Thank you for helping! splitkaro is meant to be useful to anyone who has ever split a bill, so
contributions from non-programmers (ideas, translations, bug reports, docs) are just as welcome
as code.

## Ways to help

- **Report a bug.** Include the commands you ran and what you expected. Please replace real
  names, UPI IDs and amounts with made-up ones.
- **Suggest a feature.** Describe the real-life situation first ("our flat splits rent by room
  size..."), then the idea.
- **Improve the docs or add examples** of how your group splits things.
- **Pick up a `good first issue`** if you are new to the project.

## Development setup

splitkaro has no runtime dependencies, so a plain Python 3.9+ install is enough.

```bash
git clone https://github.com/K70281095/splitkaro.git
cd splitkaro
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Run the tests, the linter and the formatter:

```bash
python -m unittest discover -s tests -v
ruff check .
ruff format --check .
```

Try your change on the example trip:

```bash
cd "$(mktemp -d)"
splitkaro init "Goa trip" && splitkaro member add Asha Ravi Meera && splitkaro rate USD 83.20
splitkaro import /path/to/splitkaro/examples/goa-trip.csv
splitkaro settle
```

## Project layout

| File | Responsibility |
|---|---|
| `src/splitkaro/money.py` | Parsing, exact splitting (`allocate`) and formatting of amounts |
| `src/splitkaro/models.py` | Members, expenses, splits, payments and the `Group` that validates them |
| `src/splitkaro/ledger.py` | Balances, the settle-up algorithm and statements |
| `src/splitkaro/report.py` | Filters and summaries |
| `src/splitkaro/storage.py` | The JSON file format |
| `src/splitkaro/csvio.py` | CSV import and export |
| `src/splitkaro/upi.py` | UPI ID validation and payment links |
| `src/splitkaro/cli.py` | The `splitkaro` command |

## Rules that keep the numbers right

1. **Never use floats for money.** Use `to_money()` and `Decimal`.
2. **Totals must add up exactly.** Split with `allocate()`; never round parts independently.
3. **Balances must sum to zero.** If you change how expenses or payments affect balances, add a
   test that checks it.
4. **Fail loudly, change nothing.** Invalid input raises `SplitKaroError`, and a failed command must
   not modify the file.
5. **Keep the file format stable.** A change to the JSON format needs a new `SCHEMA_VERSION` and
   a way to read older files.

## Pull request checklist

- [ ] One logical change per pull request.
- [ ] Tests added or updated.
- [ ] `python -m unittest discover -s tests`, `ruff check .` and `ruff format --check .` pass.
- [ ] User-facing changes described in `CHANGELOG.md` under **Unreleased**.

## Releasing (maintainers)

1. Move the **Unreleased** entries in `CHANGELOG.md` under a new version heading.
2. Bump `version` in `pyproject.toml` and `__version__` in `src/splitkaro/__init__.py`.
3. Commit and push, then create a GitHub release whose tag is `v` + that version, e.g. `v0.1.0`.
4. The **Release** workflow checks the tag, builds the package and uploads it to PyPI.

One-time PyPI setup (trusted publishing, no API token needed):

1. On [pypi.org](https://pypi.org), open **Your projects → Publishing → Add a new pending
   publisher** and fill in: project `splitkaro`, owner `K70281095`, repository `splitkaro`, workflow
   `release.yml`, environment `pypi`.
2. On GitHub, create the environment under **Settings → Environments → New environment →
   `pypi`**.

By contributing, you agree that your contributions are licensed under the [MIT License](LICENSE)
and that you will follow the [Code of Conduct](CODE_OF_CONDUCT.md).
