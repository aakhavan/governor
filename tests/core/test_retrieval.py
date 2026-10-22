"""Chunk ids, catalog cards, and the grade loop. No network and no index."""

from __future__ import annotations

import json
import re

from triage.config import PROJECT_DIR
from triage.grading import run_grade_loop
from triage.retrieval import chunk_folder, chunk_tree, rrf, write_catalog
from triage.retrieval import Chunk
from triage.schemas import GradeHit, RetrievalGrade
from triage.trace import current_trace, reset_trace

KNOWLEDGE = PROJECT_DIR / "knowledge"
_BANNED = ("INC-", "German", "cents", "subscription_id", "amount_eur", "monthly_price")
_CHUNK_ID = re.compile(r"(runbook|postmortem|catalog):[^#]+#\d+")


class _AlwaysIrrelevant:
    def __init__(self):
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        return {
            "parsed": RetrievalGrade(
                grades=[GradeHit(chunk_id="runbook:x.md#0", relevant=False, reason="no")],
                rewritten_query=f"attempt {self.calls + 1}",
            ),
            "raw": None,
        }


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


def test_authored_corpus_does_not_name_planted_faults():
    runbooks = sorted((KNOWLEDGE / "runbooks").glob("*.md"))
    posts = sorted((KNOWLEDGE / "postmortems").glob("*.md"))
    assert 8 <= len(runbooks) <= 10
    assert len(posts) == 4
    for path in runbooks + posts:
        text = path.read_text(encoding="utf-8")
        for token in _BANNED:
            assert token not in text, f"{path.name} contains {token}"
    chunks = chunk_folder(KNOWLEDGE / "runbooks", "runbooks")
    assert chunks
    assert all(chunk.chunk_id.startswith("runbook:") for chunk in chunks)
    assert all(_CHUNK_ID.fullmatch(chunk.chunk_id) for chunk in chunks)
    post_chunks = chunk_folder(KNOWLEDGE / "postmortems", "postmortems")
    assert {chunk.chunk_id.split("#")[0] for chunk in post_chunks} == {
        f"postmortem:{path.name}" for path in posts
    }


def test_catalog_card_lists_owner_columns_and_tests(tmp_path):
    count = write_catalog(tmp_path)
    assert count == 18
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


def test_grade_loop_stops_after_two_rewrites():
    searches: list[str] = []

    def search_again(query: str) -> dict:
        searches.append(query)
        return {
            "status": "ok",
            "hits": [
                {
                    "chunk_id": "runbook:x.md#0",
                    "source": "runbooks/x.md",
                    "text": "<untrusted>no</untrusted>",
                    "score": 0.01,
                }
            ],
            "summary": "1 runbooks hits",
        }

    reset_trace()
    result = run_grade_loop(
        query="weak",
        corpus="runbooks",
        top_k=4,
        payload={
            "status": "ok",
            "hits": [
                {
                    "chunk_id": "runbook:x.md#0",
                    "source": "runbooks/x.md",
                    "text": "<untrusted>no</untrusted>",
                    "score": 0.01,
                }
            ],
            "summary": "1 runbooks hits",
        },
        rewrites_used=0,
        grader=_AlwaysIrrelevant(),
        search_again=search_again,
    )
    assert result.rewrites_performed == 2
    assert searches == ["attempt 2", "attempt 3"]
    body = json.loads(result.content)
    assert body["summary"] == "no relevant knowledge found"
    assert body["hits"] == []
    assert len([event for event in current_trace() if event["event"] == "retrieval_rewrite"]) == 2
