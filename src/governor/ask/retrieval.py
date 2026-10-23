"""Hybrid schema retrieval over catalog and metric cards.

BM25 over card text, dense search over cached card embeddings, and
reciprocal rank fusion (k=60) of the two, reusing ``governor.core.retrieval.rrf``.
Each retriever contributes its own top ``max(10, k)``; ``k`` is applied after
fusion. Cards come from ``artifacts/catalog_cards.jsonl`` (built from the
metadata store when the file is missing).

Embeddings are cached in ``artifacts/card_embeddings.npz`` with a key over
the embedder name and the card texts, so they are rebuilt when cards change.
``HashEmbedder`` is a deterministic offline embedder for tests and
``--embedder fake``.

    uv run python -m governor.ask.retrieval eval --split tune --mode bm25 --k 3 [--embedder fake]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
from langchain_core.embeddings import Embeddings

from governor.ask import catalog
from governor.core import paths
from governor.core.retrieval import PER_QUERY_K, RRF_K, Chunk, rrf

EMBEDDINGS_PATH = paths.ARTIFACTS / "card_embeddings.npz"
Mode = Literal["hybrid", "bm25", "dense"]


@dataclass(frozen=True)
class Hit:
    card_id: str
    score: float
    tables: list[str]


def tokens(text: str) -> list[str]:
    """Lowercase words; a snake_case word also yields its parts.

    ``days_outstanding`` -> ``days_outstanding``, ``days``, ``outstanding``.
    """
    out: list[str] = []
    for word in re.findall(r"[a-z0-9_]+", text.lower()):
        parts = [p for p in word.split("_") if p]
        if len(parts) > 1:
            out.append("_".join(parts))
        out.extend(parts)
    return out


class HashEmbedder(Embeddings):
    """Bag of hashed tokens, L2-normalised. Same text, same vector, on any machine."""

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim
        self.name = f"hash-{dim}"

    def _vector(self, text: str) -> list[float]:
        vector = np.zeros(self.dim, dtype=np.float64)
        for token in tokens(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dim
            vector[index] += 1.0 if digest[4] & 1 else -1.0
        norm = float(np.linalg.norm(vector))
        return (vector / norm if norm else vector).tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


def get_embedder(embedder: Embeddings | str | None) -> Embeddings:
    """``None`` or ``"default"`` -> the configured embedding model; ``"fake"`` -> HashEmbedder."""
    if isinstance(embedder, Embeddings):
        return embedder
    if embedder == "fake":
        return HashEmbedder()
    if embedder in (None, "default"):
        from governor.core.llm import get_embeddings

        return get_embeddings()
    raise ValueError(f"unknown embedder {embedder!r}")


def _embedder_name(embedder: Embeddings) -> str:
    name = getattr(embedder, "name", None) or getattr(embedder, "model", None) or getattr(embedder, "model_name", None)
    return f"{type(embedder).__name__}:{name}"


def load_cards(path: Path = catalog.CARDS_PATH) -> list[dict]:
    """Cards from ``path``; built from the metadata store and written there when missing."""
    if path.is_file():
        return catalog.read_cards(path)
    cards = catalog.build_cards()
    catalog.write_cards(cards, path)
    return cards


def card_vectors(cards: list[dict], embedder: Embeddings, cache: Path | None = EMBEDDINGS_PATH) -> np.ndarray:
    """One row per card, L2-normalised. Reuses ``cache`` when its key matches."""
    key = hashlib.sha256(
        json.dumps([_embedder_name(embedder), [(c["id"], c["text"]) for c in cards]]).encode("utf-8")
    ).hexdigest()
    if cache is not None and cache.is_file():
        with np.load(cache, allow_pickle=False) as stored:
            if str(stored["key"]) == key:
                return stored["vectors"]
    vectors = np.asarray(embedder.embed_documents([c["text"] for c in cards]), dtype=np.float64)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    vectors = vectors / np.where(norms == 0, 1.0, norms)
    if cache is not None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        np.savez(cache, key=np.array(key), vectors=vectors)
    return vectors


def bm25_rank(cards: list[dict], query: str, k: int) -> list[tuple[dict, float]]:
    from rank_bm25 import BM25Okapi

    if not cards or k < 1:
        return []
    scores = BM25Okapi([tokens(c["text"]) or ["empty"] for c in cards]).get_scores(tokens(query))
    order = sorted(range(len(cards)), key=lambda i: (-float(scores[i]), cards[i]["id"]))
    return [(cards[i], float(scores[i])) for i in order[:k]]


def dense_rank(
    cards: list[dict], query: str, k: int, embedder: Embeddings, cache: Path | None = EMBEDDINGS_PATH
) -> list[tuple[dict, float]]:
    if not cards or k < 1:
        return []
    vectors = card_vectors(cards, embedder, cache)
    q = np.asarray(embedder.embed_query(query), dtype=np.float64)
    norm = float(np.linalg.norm(q))
    scores = vectors @ (q / norm if norm else q)
    order = sorted(range(len(cards)), key=lambda i: (-float(scores[i]), cards[i]["id"]))
    return [(cards[i], float(scores[i])) for i in order[:k]]


def fuse(ranked_lists: list[list[dict]], k: int = RRF_K) -> list[tuple[dict, float]]:
    """RRF over ranked card lists, via ``governor.core.retrieval.rrf``."""
    by_id = {c["id"]: c for ranked in ranked_lists for c in ranked}
    chunk_lists = [[Chunk(chunk_id=c["id"], corpus="catalog", source=c["name"], text="") for c in r] for r in ranked_lists]
    return [(by_id[chunk.chunk_id], score) for chunk, score in rrf(chunk_lists, k=k)]


def search(
    query: str,
    k: int = 5,
    mode: Mode = "hybrid",
    embedder: Embeddings | str | None = None,
    cards: list[dict] | None = None,
    cache: Path | None = EMBEDDINGS_PATH,
) -> list[Hit]:
    """Top ``k`` cards for ``query``. ``cards`` defaults to the built card file."""
    if mode not in ("hybrid", "bm25", "dense"):
        raise ValueError(f"unknown mode {mode!r}")
    cards = load_cards() if cards is None else cards
    if mode == "bm25":
        found = bm25_rank(cards, query, k)
    elif mode == "dense":
        found = dense_rank(cards, query, k, get_embedder(embedder), cache)
    else:
        depth = max(PER_QUERY_K, k)
        dense = [c for c, _ in dense_rank(cards, query, depth, get_embedder(embedder), cache)]
        sparse = [c for c, _ in bm25_rank(cards, query, depth)]
        found = fuse([dense, sparse])[:k]
    return [Hit(card_id=c["id"], score=round(score, 6), tables=list(c["tables"])) for c, score in found]


def evaluate(split: str, mode: Mode, k: int, embedder: Embeddings | str | None = None) -> dict:
    """Mean share of gold tables (from each question's gold SQL) found in the top-k hits."""
    from governor.eval.golden import load_golden, load_split

    golden = load_golden().by_id()
    ids = getattr(load_split(), split)
    cards = load_cards()
    chosen = get_embedder(embedder) if mode != "bm25" else None
    recalls: list[float] = []
    for qid in ids:
        question = golden[qid]
        if not question.gold_sql:
            continue
        gold = set(catalog.sql_tables(question.gold_sql))
        if not gold:
            continue
        hits = search(question.question, k=k, mode=mode, embedder=chosen, cards=cards)
        found = {t for h in hits for t in h.tables}
        recalls.append(len(gold & found) / len(gold))
    recall = round(sum(recalls) / len(recalls), 4) if recalls else 0.0
    return {"mode": mode, "k": k, "n": len(recalls), "recall": recall}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Schema retrieval over catalog cards.")
    sub = parser.add_subparsers(dest="command", required=True)
    ev = sub.add_parser("eval", help="recall of gold tables in the top-k hits")
    ev.add_argument("--split", choices=["tune", "holdout"], default="tune")
    ev.add_argument("--mode", choices=["bm25", "dense", "hybrid"], default="hybrid")
    ev.add_argument("--k", type=int, default=5)
    ev.add_argument("--embedder", choices=["default", "fake"], default="default")
    args = parser.parse_args(argv)
    print(json.dumps(evaluate(args.split, args.mode, args.k, args.embedder)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
