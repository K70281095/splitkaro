# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x | ✅ |

## What splitkaro does and does not do

- splitkaro **never moves money**, and never asks for bank details, card numbers or UPI PINs.
- UPI support is limited to building standard `upi://pay` links. The payer always reviews and
  confirms the payment in their own UPI app.
- All data stays in a local JSON file. splitkaro makes no network requests.

## Reporting a vulnerability

**Please do not open a public issue for security problems.** Use GitHub's private
vulnerability reporting instead:
[Report a vulnerability](https://github.com/K70281095/splitkaro/security/advisories/new).

Please include what you found, steps to reproduce it (with made-up data), and the splitkaro and
Python versions. You can expect an acknowledgement within 7 days.

Examples of issues we want to hear about:

- a crafted CSV or JSON file that makes splitkaro crash, hang or write outside its own file,
- a way to make a UPI link pay a different person or amount than the one shown,
- calculations that create or lose money (balances not adding up to zero).
