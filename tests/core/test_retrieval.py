"""Chunk ids, catalog cards, and rank fusion. No network and no index."""

from __future__ import annotations

import re

from governor.core.retrieval import chunk_tree, chunk_folder, rrf, write_catalog
from governor.core.retrieval import Chunk

_CHUNK_ID = re.compile(r"(runbook|postmortem|catalog):[^#]+#\d+")


def test_chunk_ids_follow_corpus_file_and_index(tmp_path):
    runbooks = tmp_path / "runbooks"
    runbooks.mkdir()
    (runbooks / "stale_source.md").write_text(
        "# Stale\n\n## Recognise\n\nFreshness.\n\n## Next\n\nCall the owner.\n",
        encoding="utf-8",
    )
    postmortems = tmp_path / "postmortems"
    postmortems.mkdir()
    (postmortems / "permissions-error.md").write_text("# P\n\nAccess denied.\n", encoding="utf-8")
    catalog = tmp_path / "catalog"
    catalog.mkdir()
    (catalog / "model.billing_mart.dim_accounts.md").write_text("# D\n\nOwner.\n", encoding="utf-8")

    chunks = chunk_tree(tmp_path)
    ids = [chunk.chunk_id for chunk in chunks]
    assert ids == [
        "runbook:stale_source.md#0",
        "runbook:stale_source.md#1",
        "runbook:stale_source.md#2",
        "postmortem:permissions-error.md#0",
        "catalog:model.billing_mart.dim_accounts.md#0",
    ]
    assert all(_CHUNK_ID.fullmatch(chunk_id) for chunk_id in ids)


def test_catalog_card_lists_owner_columns_and_tests(tmp_path):
    count = write_catalog(tmp_path)
    assert count == 19
    invoices = (tmp_path / "source.billing_mart.billing.invoices.md").read_text(encoding="utf-8")
    assert "finance-data" in invoices
    assert "amount_eur" in invoices
    accounts = (tmp_path / "source.billing_mart.crm.accounts.md").read_text(encoding="utf-8")
    assert "pii:email" in accounts
    chunks = chunk_folder(tmp_path, "catalog")
    assert any(chunk.chunk_id.startswith("catalog:source.billing_mart.billing.invoices.md#") for chunk in chunks)


def test_rrf_fuses_ranks_and_does_not_rescore_text():
    first = Chunk("a", "runbooks", "runbooks/a.md", "alpha")
    second = Chunk("b", "runbooks", "runbooks/b.md", "beta")
    # b is rank 1 on both lists. a is rank 1 on one list only.
    fused = rrf([[second, first], [second]], k=60)
    assert [chunk.chunk_id for chunk, _score in fused] == ["b", "a"]
    assert fused[0][1] == (1 / 61) + (1 / 61)
    assert fused[1][1] == 1 / 62

