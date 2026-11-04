"""UPI payment links, so a suggested settlement is one tap away.

A link like ``upi://pay?pa=asha@okbank&pn=Asha&am=450.00&cu=INR&tn=Goa+trip``
opens any UPI app (GPay, PhonePe, Paytm, BHIM...) with the payee and amount
filled in. The payer still reviews and confirms the payment in their app.
"""

from __future__ import annotations

import re
from decimal import Decimal
from urllib.parse import urlencode

from splitkaro.models import SplitKaroError

_VPA_RE = re.compile(r"^[A-Za-z0-9.\-_]{2,256}@[A-Za-z][A-Za-z0-9]{1,64}$")


def is_valid_vpa(vpa: str) -> bool:
    """Check the shape of a UPI ID (virtual payment address), e.g. ``name@bank``."""
    return bool(_VPA_RE.match(vpa))


def payment_link(vpa: str, name: str, amount: Decimal, note: str = "") -> str:
    if not is_valid_vpa(vpa):
        raise SplitKaroError(f"{vpa!r} does not look like a UPI ID (expected something like name@bank)")
    if amount <= 0:
        raise SplitKaroError("a UPI payment must be greater than zero")
    params = {"pa": vpa, "pn": name, "am": f"{amount:.2f}", "cu": "INR"}
    if note:
        # Many UPI apps cut the note at about 50 characters.
        params["tn"] = note[:50]
    return "upi://pay?" + urlencode(params)
