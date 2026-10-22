"""checker.compare: order, column permutation, tolerance, multiplicity, None; run_gold."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from governor.eval.checker import compare, run_gold


def test_row_order_ignored_by_default():
    assert compare([(1, "a"), (2, "b")], [(2, "b"), (1, "a")]).equal


def test_row_order_counts_when_order_matters():
    result = compare([(1, "a"), (2, "b")], [(2, "b"), (1, "a")], order_matters=True)
    assert not result.equal
    assert "order" in result.reason
    assert compare([(1, "a"), (2, "b")], [(1, "a"), (2, "b")], order_matters=True).equal


def test_column_permutation_ignored():
    assert compare([(1, "a")], [("a", 1)]).equal
    assert compare([(1, "x", 2.5), (2, "y", 3.5)], [(3.5, 2, "y"), (2.5, 1, "x")]).equal


def test_column_permutation_with_order_matters():
    assert compare([(1, "a"), (2, "b")], [("a", 1), ("b", 2)], order_matters=True).equal


def test_permutation_must_hold_row_wise():
    # each column matches as a multiset, but no permutation keeps the rows together
    assert not compare([(1, 10), (2, 20)], [(1, 20), (2, 10)]).equal


def test_interchangeable_columns():
    assert compare([(1, 1), (2, 2)], [(2, 2), (1, 1)]).equal


@pytest.mark.parametrize(
    ("pred", "equal"),
    [
        (100.00005, True),  # rel diff 5e-7
        (100.0001, True),  # rel diff 1e-6, on the boundary
        (100.0002, False),  # rel diff 2e-6
        (100.01, False),
    ],
)
def test_tolerance_boundary(pred, equal):
    assert compare([(100.0,)], [(pred,)]).equal is equal


def test_custom_tolerance():
    assert compare([(100.0,)], [(101.0,)], rel_tol=0.02).equal
    assert not compare([(100.0,)], [(101.0,)], rel_tol=0.001).equal


def test_decimal_int_and_float_mix():
    assert compare([(Decimal("694322.00"), 7)], [(694322.0, 7.0)]).equal


def test_tolerance_pairs_rows_across_sort_order():
    gold = [(1.0, "b"), (1.0000001, "a")]
    pred = [(1.0000001, "b"), (1.0, "a")]
    assert compare(gold, pred).equal


def test_row_count_differs():
    result = compare([(1,), (2,)], [(1,)])
    assert not result.equal
    assert "row count" in result.reason


def test_column_count_differs():
    result = compare([(1, 2)], [(1, 2, 3)])
    assert not result.equal
    assert "column count" in result.reason


def test_duplicates_matter():
    assert not compare([(1,), (1,)], [(1,)]).equal
    assert not compare([(1,), (1,), (2,)], [(1,), (2,), (2,)]).equal
    assert compare([(1,), (1,), (2,)], [(2,), (1,), (1,)]).equal


def test_none_handling():
    assert compare([(None,)], [(None,)]).equal
    assert not compare([(None,)], [(0,)]).equal
    assert not compare([(0,)], [(None,)]).equal
    assert not compare([(None,)], [("",)]).equal
    assert compare([(None, 1), (2, None)], [(None, 2), (1, None)]).equal


def test_empty_results():
    assert compare([], []).equal
    assert not compare([], [(1,)]).equal


def test_strings_exact_and_bool_not_number():
    assert not compare([("a",)], [("A",)]).equal
    assert not compare([(True,)], [(1,)]).equal


def test_date_equals_midnight_timestamp():
    assert compare([(date(2026, 9, 1),)], [(datetime(2026, 9, 1),)]).equal
    assert not compare([(date(2026, 9, 1),)], [(datetime(2026, 9, 1, 12),)]).equal


def test_run_gold_reads_marts_unqualified():
    rows = run_gold("SELECT COUNT(account_id) FROM dim_accounts")
    assert rows == [(2000,)]
    assert isinstance(rows[0], tuple)


def test_run_gold_is_read_only():
    import duckdb

    with pytest.raises(duckdb.Error):
        run_gold("CREATE TABLE zz_probe AS SELECT 1 AS a")
