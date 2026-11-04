# How splitkaro works

This page explains the three calculations behind every command: splitting an amount, computing
balances, and finding the payments that settle a group.

## 1. Splitting an amount exactly

Money is never stored as a float. Every amount is a `Decimal` with two places (rupees and
paise), so `0.10 + 0.20` is exactly `0.30`.

Splitting uses the **largest-remainder method** on whole paise:

1. Convert the total to paise: ₹100.00 → 10,000 paise.
2. Give everyone their exact share, rounded **down**: 10,000 / 3 = 3,333.33… → 3,333 each.
3. 10,000 − 3 × 3,333 = 1 paisa is left over. Give it to whoever lost the most to rounding;
   ties go to the person listed first.

Result: ₹33.34, ₹33.33, ₹33.33, which adds up to exactly ₹100.00. The same method handles
shares and percentages, because they are just weights: shares `2:1:1` of ₹9,000 give ₹4,500,
₹2,250 and ₹2,250.

Exact splits (`--exact`) are used as given, but must add up to the total; percentages must add
up to 100. splitkaro refuses an expense that doesn't add up rather than guessing.

## 2. Balances

For every member:

```
balance = (what they paid) − (their share of expenses)
        + (payments they made) − (payments they received)
```

A positive balance means the group owes them money; a negative one means they owe the group.
Because every rupee paid is someone's share, **the balances always add up to exactly zero**.
The test suite checks this on hundreds of random groups.

### Foreign currency

An expense in another currency is converted to the group currency with the rate you set
(`splitkaro rate USD 83.20`). The converted total is computed once and then split, so the
conversion can never create or lose a paisa. When several people paid a foreign bill, the
converted total is shared among the payers in proportion to what they paid, for the same reason.

## 3. Settling up with few payments

Take the Goa trip from the README:

| Member | Balance |
|---|---|
| Asha | +2,618 |
| Ravi | −682 |
| Meera | −1,936 |

Anyone with a negative balance pays someone with a positive one. splitkaro does this in two passes:

1. **Exact matches first.** If someone owes exactly what someone else is owed, they pay each
   other directly. That settles two people with one payment.
2. **Largest first.** Repeatedly take the person who owes the most and the person who is owed
   the most, and transfer the smaller of the two amounts. At least one of them reaches zero
   each time.

Each payment brings at least one person to zero, and the last payment always settles two
people, so a group of *n* people needs **at most n − 1 payments**, however many expenses there
were. For the trip above, that is two payments instead of the five expenses it started from.

Finding the absolute minimum number of payments is an NP-hard problem (it involves finding
groups of people whose balances add up to zero). The exact-match pass catches the most common
case of that in everyday groups, and the greedy pass keeps the result small and predictable.
Ties are broken by name, so the same group always gets the same suggestion.

## 4. UPI links

`splitkaro settle --upi` adds a standard link for every payment whose receiver has a UPI ID:

```
upi://pay?pa=asha@okbank&pn=Asha&am=1936.00&cu=INR&tn=splitkaro: Goa trip
```

| Parameter | Meaning |
|---|---|
| `pa` | payee address (UPI ID) |
| `pn` | payee name |
| `am` | amount |
| `cu` | currency (always INR) |
| `tn` | transaction note |

Opening the link on a phone launches a UPI app with everything filled in. The payer still checks
the details and enters their PIN; splitkaro never touches money or bank details.
