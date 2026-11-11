"""Error redaction before an error reaches a model prompt (batch2d section 25).

Postgres and dbt errors quote data values (``invalid input syntax for type timestamp: "<value>"``, ``DETAIL:  Key
(customer_id)=(<value>) already exists.``). :func:`redact_error` keeps the shape of the error and the identifiers the
model needs to fix its SQL, and drops every value:

- lines starting with ``DETAIL``, ``HINT``, ``CONTEXT``, ``Failing row`` or ``Key (`` are removed;
- single-quoted literals become ``'…'``;
- a double-quoted span is kept only when its content is a known identifier (case-insensitive); any other becomes ``"…"``;
- runs of 7 or more digits become ``#``.

Pure function: no imports from other governor modules.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

_DROP = ("DETAIL", "HINT", "CONTEXT", "Failing row", "Key (")
# one left-to-right pass over both quote kinds, so a quote inside the other kind is not matched on its own
_QUOTED = re.compile(r"'[^'\n]*'|\"[^\"\n]*\"")
_DIGITS = re.compile(r"\d{7,}")


def redact_error(text: str, identifiers: Iterable[str]) -> str:
    """``text`` without data values; double-quoted ``identifiers`` stay as they are."""
    known = {str(i).lower() for i in identifiers or () if i}
    lines = [ln for ln in (text or "").splitlines() if not ln.lstrip().startswith(_DROP)]

    def quoted(match: re.Match) -> str:
        span = match.group(0)
        if span[0] == "'":
            return "'…'"
        return span if span[1:-1].lower() in known else '"…"'

    out = _QUOTED.sub(quoted, "\n".join(lines))
    return _DIGITS.sub("#", out)
