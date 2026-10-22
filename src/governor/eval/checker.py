"""Execution-accuracy checker: does a predicted result equal the gold result?

Results are lists of row tuples. Column names are not compared (aliases vary);
column order is ignored by trying every permutation of the predicted columns
that is consistent column by column. Numbers compare with a relative
tolerance, None equals only None, and row multiplicity matters. Row order
matters only when ``order_matters`` is set.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator, Sequence

from governor.core.warehouse import connect

Row = tuple[Any, ...]
_ABS_TOL = 1e-9  # so 0 and a float rounding residue still compare equal
_MATCH_LIMIT = 300  # rows; above this a failed sorted match is not retried pairwise
_PERMUTATION_LIMIT = 5040  # 7! column assignments; only reached by many interchangeable columns


@dataclass(frozen=True)
class Comparison:
    equal: bool
    reason: str


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)


def _as_datetime(value: date) -> datetime:
    return value if isinstance(value, datetime) else datetime.combine(value, time())


def _same(gold: Any, pred: Any, rel_tol: float) -> bool:
    if gold is None or pred is None:
        return gold is None and pred is None
    if _is_number(gold) and _is_number(pred):
        a, b = float(gold), float(pred)
        if math.isnan(a) or math.isnan(b):
            return math.isnan(a) and math.isnan(b)
        return math.isclose(a, b, rel_tol=rel_tol, abs_tol=_ABS_TOL)
    if isinstance(gold, date) and isinstance(pred, date):
        return _as_datetime(gold) == _as_datetime(pred)
    if isinstance(gold, bool) != isinstance(pred, bool):
        return False
    return gold == pred


def _cell_key(value: Any) -> tuple:
    if value is None:
        return (0, 0)
    if isinstance(value, bool):
        return (1, int(value))
    if _is_number(value):
        number = float(value)
        return (2, math.inf if math.isnan(number) else number)
    if isinstance(value, str):
        return (3, value)
    if isinstance(value, date):
        return (4, _as_datetime(value).replace(tzinfo=None))
    return (5, repr(value))


def _row_key(row: Row) -> tuple:
    return tuple(_cell_key(v) for v in row)


def _rows_same(gold: Row, pred: Row, rel_tol: float) -> bool:
    return all(_same(g, p, rel_tol) for g, p in zip(gold, pred))


def _bipartite(gold: list[Row], pred: list[Row], rel_tol: float) -> bool:
    """Perfect matching of gold rows to pred rows (Kuhn's algorithm)."""
    edges = [[j for j, p in enumerate(pred) if _rows_same(g, p, rel_tol)] for g in gold]
    owner: list[int | None] = [None] * len(pred)

    def augment(i: int, seen: set[int]) -> bool:
        for j in edges[i]:
            if j in seen:
                continue
            seen.add(j)
            if owner[j] is None or augment(owner[j], seen):
                owner[j] = i
                return True
        return False

    return all(augment(i, set()) for i in range(len(gold)))


def _multiset_same(gold: list[Row], pred: list[Row], rel_tol: float) -> bool:
    gold_sorted = sorted(gold, key=_row_key)
    pred_sorted = sorted(pred, key=_row_key)
    if all(_rows_same(g, p, rel_tol) for g, p in zip(gold_sorted, pred_sorted)):
        return True
    # Sorting can pair rows wrongly when values differ within tolerance; retry exactly.
    return len(gold) <= _MATCH_LIMIT and _bipartite(gold, pred, rel_tol)


def _column(rows: Sequence[Row], index: int) -> list[Any]:
    return [row[index] for row in rows]


def _columns_compatible(gold: list[Any], pred: list[Any], order_matters: bool, rel_tol: float) -> bool:
    if not order_matters:
        gold = sorted(gold, key=_cell_key)
        pred = sorted(pred, key=_cell_key)
    return all(_same(g, p, rel_tol) for g, p in zip(gold, pred))


def _permutations(candidates: list[list[int]]) -> Iterator[list[int]]:
    """Every assignment gold column -> distinct pred column drawn from ``candidates``."""
    chosen: list[int] = []
    used: set[int] = set()

    def walk(i: int) -> Iterator[list[int]]:
        if i == len(candidates):
            yield list(chosen)
            return
        for j in candidates[i]:
            if j in used:
                continue
            used.add(j)
            chosen.append(j)
            yield from walk(i + 1)
            chosen.pop()
            used.discard(j)

    return walk(0)


def compare(
    gold_rows: Sequence[Row],
    pred_rows: Sequence[Row],
    *,
    order_matters: bool = False,
    rel_tol: float = 1e-6,
) -> Comparison:
    """Compare two results. See the module docstring for the rules."""
    gold = [tuple(r) for r in gold_rows]
    pred = [tuple(r) for r in pred_rows]
    if len(gold) != len(pred):
        return Comparison(False, f"row count differs: gold {len(gold)}, pred {len(pred)}")
    if not gold:
        return Comparison(True, "both empty")
    gold_widths = {len(r) for r in gold}
    pred_widths = {len(r) for r in pred}
    if len(gold_widths) > 1 or len(pred_widths) > 1:
        return Comparison(False, "rows have uneven widths")
    width = gold_widths.pop()
    if width != pred_widths.pop():
        return Comparison(False, f"column count differs: gold {width}, pred {len(pred[0])}")

    # Same position first, so the common case (columns already aligned) is tried first.
    candidates = [
        sorted(
            (j for j in range(width) if _columns_compatible(_column(gold, i), _column(pred, j), order_matters, rel_tol)),
            key=lambda j, i=i: j != i,
        )
        for i in range(width)
    ]
    unmatched = [i for i, c in enumerate(candidates) if not c]
    if unmatched:
        if order_matters and compare(gold, pred, order_matters=False, rel_tol=rel_tol).equal:
            return Comparison(False, "same rows, different order")
        return Comparison(False, f"gold column(s) {unmatched} have no matching pred column")

    for tried, perm in enumerate(_permutations(candidates)):
        if tried >= _PERMUTATION_LIMIT:
            return Comparison(False, f"gave up after {_PERMUTATION_LIMIT} column permutations")
        reordered = [tuple(row[j] for j in perm) for row in pred]
        if order_matters:
            if all(_rows_same(g, p, rel_tol) for g, p in zip(gold, reordered)):
                return Comparison(True, "equal (ordered)")
        elif _multiset_same(gold, reordered, rel_tol):
            return Comparison(True, "equal")
    if order_matters and compare(gold, pred, order_matters=False, rel_tol=rel_tol).equal:
        return Comparison(False, "same rows, different order")
    return Comparison(False, "values differ under every column permutation")


def run_gold(sql: str, database: str | Path | None = None) -> list[Row]:
    """Execute gold SQL on the green warehouse (read-only, unqualified mart names)."""
    connection = connect(database)
    try:
        return [tuple(row) for row in connection.execute(sql).fetchall()]
    finally:
        connection.close()
