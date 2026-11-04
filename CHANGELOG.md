# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-11-04

### Added

- Groups stored in a readable JSON file, written atomically.
- Members with optional UPI IDs; names are case-insensitive.
- Expenses with one or several payers, categories, dates, notes and foreign currencies.
- Four ways to split: equal, exact, percent and shares, always exact to the paisa.
- Balances, a settle-up plan with at most n − 1 payments, and UPI payment links.
- Statements with a running balance, and reports by category, month and member.
- CSV import (all or nothing) and export.
- JSON output for `balances`, `settle` and `report`.

[Unreleased]: https://github.com/K70281095/splitkaro/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/K70281095/splitkaro/releases/tag/v0.1.0
