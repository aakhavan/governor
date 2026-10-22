"""Hybrid search over runbooks, post-mortems, and catalog cards.

Dense vectors live in a local Chroma collection under ``.state/chroma``.
BM25 is rebuilt from ``.state/chunks.jsonl`` when the index is loaded.
The two ranked lists are fused with reciprocal rank fusion, k=60.

RRF is fusion, not reranking. It merges ranks the retrievers already
produced. It does not score the text again with another model. k=60
dampens a single list's top hit: rank 1 is worth 1/61 and rank 10 is
worth 1/70. This is the same fusion the Sprint 3 retriever uses.
Embeddings come from the existing embed config.

Catalog cards are generated from the green ``meta.duckdb``. Runbooks and
post-mortems are the files under ``knowledge/``.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from triage.config import CHROMA_DIR, CHUNKS_PATH, PROJECT_DIR
from triage.schemas import Hit, SearchKnowledgeResult, as_untrusted

KNOWLEDGE_DIR = PROJECT_DIR / "knowledge"
GREEN_META = PROJECT_DIR / "artifacts" / "green" / "meta.duckdb"
COLLECTION_NAME = "triage_knowledge"
COLLECTION_METADATA = {"hnsw:space": "cosine"}
BUILD_COMMAND = "uv run python -m triage.retrieval --build"
MISSING_INDEX = f"Retrieval index is not built. run: {BUILD_COMMAND}"

# Each retriever contributes its own top 10. top_k is applied after fusion.
PER_QUERY_K = 10
RRF_K = 60
_CHUNK_CHARS = 1400

_CORPORA = {
    "runbooks": "runbook",
    "postmortems": "postmortem",
    "catalog": "catalog",
}


class IndexNotReady(FileNotFoundError):
    """The chunk file or the Chroma collection is missing."""


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    corpus: str
    source: str
    text: str


def _tokens(text: str) -> list[str]:
    """Lowercase and split on non-letters, so case does not hide a match."""
    return re.findall(r"[a-z0-9]+", text.lower())


def _pieces(text: str, limit: int = _CHUNK_CHARS) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= limit:
        return [text]
    groups: list[str] = []
    current: list[str] = []
    size = 0
    for paragraph in text.split("\n\n"):
        if current and size + len(paragraph) + 2 > limit:
            groups.append("\n\n".join(current))
            current = []
            size = 0
        current.append(paragraph)
        size += len(paragraph) + 2
    if current:
        groups.append("\n\n".join(current))
    return [group for group in groups if group.strip()]


def chunk_folder(folder: Path, corpus: str) -> list[Chunk]:
    """Chunk one corpus directory. Ids look like ``runbook:<file>#<n>``."""
    prefix = _CORPORA[corpus]
    chunks: list[Chunk] = []
    if not folder.is_dir():
        return chunks
    for path in sorted(folder.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        sections = re.split(r"(?m)(?=^## )", raw)
        pieces: list[str] = []
        for section in sections:
            pieces.extend(_pieces(section))
        for index, text in enumerate(pieces):
            chunks.append(
                Chunk(
                    chunk_id=f"{prefix}:{path.name}#{index}",
                    corpus=corpus,
                    source=f"{folder.name}/{path.name}",
                    text=text,
                )
            )
    return chunks


def chunk_tree(root: Path) -> list[Chunk]:
    """Chunk runbooks, post-mortems, and catalog cards under ``root``."""
    chunks: list[Chunk] = []
    for corpus in _CORPORA:
        chunks.extend(chunk_folder(root / corpus, corpus))
    return chunks


def write_catalog(dest: Path, meta_path: Path = GREEN_META) -> int:
    """Write one markdown card per green graph node. Returns the count."""
    import duckdb

    if not meta_path.is_file():
        raise FileNotFoundError(f"green meta.duckdb is missing: {meta_path}")
    connection = duckdb.connect(str(meta_path), read_only=True)
    try:
        nodes = connection.execute(
            'select unique_id, resource_type, name, "schema", owner, description '
            "from nodes order by unique_id"
        ).fetchall()
        columns = connection.execute(
            'select unique_id, "column", data_type, description, pii_tag '
            'from columns order by unique_id, "column"'
        ).fetchall()
        tests = connection.execute(
            'select attached_node, "column", test_type, severity '
            "from tests order by attached_node, test_type, \"column\""
        ).fetchall()
    finally:
        connection.close()

    by_column: dict[str, list] = {}
    for row in columns:
        by_column.setdefault(row[0], []).append(row)
    by_test: dict[str, list] = {}
    for row in tests:
        by_test.setdefault(row[0], []).append(row)

    dest.mkdir(parents=True, exist_ok=True)
    for old in dest.glob("*.md"):
        old.unlink()
    for unique_id, resource_type, name, schema, owner, description in nodes:
        lines = [
            f"# {unique_id}",
            "",
            f"- type: {resource_type}",
            f"- name: {name}",
            f"- schema: {schema or ''}",
            f"- owner: {owner or 'unassigned'}",
            "",
            "## Description",
            "",
            (description or "").strip() or "(none)",
            "",
            "## Columns",
            "",
        ]
        node_columns = by_column.get(unique_id) or []
        if not node_columns:
            lines.append("- (none)")
        for _node, column, data_type, column_description, pii in node_columns:
            pii_text = f" pii:{pii}" if pii else ""
            lines.append(f"- {column} ({data_type or 'unknown'}){pii_text}")
            if isinstance(column_description, str) and column_description.strip():
                lines.append(f"  {column_description.strip()}")
        lines.extend(["", "## Tests", ""])
        node_tests = by_test.get(unique_id) or []
        if not node_tests:
            lines.append("- (none)")
        for _node, column, test_type, severity in node_tests:
            target = column or "(model)"
            lines.append(f"- {test_type} on {target}, severity {severity}")
        lines.append("")
        (dest / f"{unique_id}.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return len(nodes)


def _require_unique(chunks: list[Chunk]) -> None:
    seen: set[str] = set()
    repeated: list[str] = []
    for chunk in chunks:
        if not chunk.chunk_id or chunk.chunk_id in seen:
            repeated.append(chunk.chunk_id)
        else:
            seen.add(chunk.chunk_id)
    if repeated:
        sample = ", ".join(repeated[:5])
        raise ValueError(f"chunk_id values are missing or repeated: {sample}")


def _write_jsonl(chunks: list[Chunk]) -> None:
    CHUNKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CHUNKS_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        for chunk in chunks:
            handle.write(
                json.dumps(
                    {
                        "chunk_id": chunk.chunk_id,
                        "corpus": chunk.corpus,
                        "source": chunk.source,
                        "text": chunk.text,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )


def _read_jsonl() -> list[Chunk]:
    chunks: list[Chunk] = []
    with CHUNKS_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            chunks.append(
                Chunk(
                    chunk_id=str(record.get("chunk_id") or ""),
                    corpus=str(record.get("corpus") or ""),
                    source=str(record.get("source") or ""),
                    text=str(record.get("text") or ""),
                )
            )
    return chunks


def build_index() -> dict:
    """Regenerate catalog cards, then recreate the Chroma collection."""
    started = time.perf_counter()
    catalog_count = write_catalog(KNOWLEDGE_DIR / "catalog")
    chunks = chunk_tree(KNOWLEDGE_DIR)
    _require_unique(chunks)
    if not chunks:
        raise RuntimeError("the knowledge corpus produced no chunks")
    _write_jsonl(chunks)

    import chromadb

    from triage.llm import get_embeddings

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    existing = {collection.name for collection in client.list_collections()}
    if COLLECTION_NAME in existing:
        client.delete_collection(COLLECTION_NAME)
    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata=COLLECTION_METADATA,
    )
    embeddings = get_embeddings()
    batch_size = 64
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        vectors = embeddings.embed_documents([chunk.text for chunk in batch])
        collection.add(
            ids=[chunk.chunk_id for chunk in batch],
            documents=[chunk.text for chunk in batch],
            embeddings=vectors,
            metadatas=[
                {
                    "chunk_id": chunk.chunk_id,
                    "corpus": chunk.corpus,
                    "source": chunk.source,
                }
                for chunk in batch
            ],
        )
    stored = collection.count()
    if stored != len(chunks):
        raise RuntimeError(
            f"Chroma holds {stored} documents after indexing {len(chunks)} chunks. "
            f"run: {BUILD_COMMAND}"
        )
    load_index.cache_clear()
    by_corpus: dict[str, int] = {}
    for chunk in chunks:
        by_corpus[chunk.corpus] = by_corpus.get(chunk.corpus, 0) + 1
    return {
        "chunks": len(chunks),
        "catalog_nodes": catalog_count,
        "by_corpus": dict(sorted(by_corpus.items())),
        "chroma_documents": stored,
        "seconds": round(time.perf_counter() - started, 3),
    }


@lru_cache(maxsize=1)
def load_index():
    """Open Chroma and the chunk list. Cached once per process."""
    if not CHUNKS_PATH.is_file() or not CHROMA_DIR.is_dir():
        raise IndexNotReady(MISSING_INDEX)
    import chromadb

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    names = {collection.name for collection in client.list_collections()}
    if COLLECTION_NAME not in names:
        raise IndexNotReady(MISSING_INDEX)
    chunks = _read_jsonl()
    if not chunks:
        raise IndexNotReady(MISSING_INDEX)
    return client.get_collection(COLLECTION_NAME), chunks


def rrf(ranked_lists: list[list[Chunk]], k: int = RRF_K) -> list[tuple[Chunk, float]]:
    """Fuse ranked lists. score(d) = sum over lists of 1 / (k + rank(d)).

    Rank starts at 1. A chunk missing from a list adds nothing for that
    list. The same chunk_id is kept once; a repeat in one list counts at
    its first rank only. Equal scores break ties by chunk_id.
    """
    scores: dict[str, float] = {}
    chosen: dict[str, Chunk] = {}
    for ranked in ranked_lists:
        seen: set[str] = set()
        for rank, chunk in enumerate(ranked, start=1):
            if chunk.chunk_id in seen:
                continue
            seen.add(chunk.chunk_id)
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + 1.0 / (k + rank)
            chosen.setdefault(chunk.chunk_id, chunk)
    order = sorted(scores, key=lambda chunk_id: (-scores[chunk_id], chunk_id))
    return [(chosen[chunk_id], scores[chunk_id]) for chunk_id in order]


def _bm25(chunks: list[Chunk], query: str, corpus: str, k: int) -> list[Chunk]:
    subset = [chunk for chunk in chunks if chunk.corpus == corpus]
    if not subset or k < 1:
        return []
    from rank_bm25 import BM25Okapi

    tokenised = [_tokens(chunk.text) or ["empty"] for chunk in subset]
    scores = BM25Okapi(tokenised).get_scores(_tokens(query))
    order = sorted(
        range(len(subset)),
        key=lambda index: (-float(scores[index]), subset[index].chunk_id),
    )
    return [subset[index] for index in order[:k]]


def _dense(collection, chunks: list[Chunk], query: str, corpus: str, k: int) -> list[Chunk]:
    if k < 1:
        return []
    matched = [chunk for chunk in chunks if chunk.corpus == corpus]
    if not matched:
        return []
    n_results = min(k, len(matched))
    from triage.llm import get_embeddings

    vector = get_embeddings().embed_query(query)
    result = collection.query(
        query_embeddings=[vector],
        n_results=n_results,
        where={"corpus": corpus},
        include=["metadatas"],
    )
    by_id = {chunk.chunk_id: chunk for chunk in matched}
    ordered: list[Chunk] = []
    for chunk_id in (result.get("ids") or [[]])[0]:
        found = by_id.get(chunk_id)
        if found is not None:
            ordered.append(found)
    return ordered


def retrieve(query: str, corpus: str, top_k: int = 4) -> list[tuple[Chunk, float]]:
    """Return the fused top chunks for one corpus."""
    if corpus not in _CORPORA:
        raise ValueError(f"unknown corpus {corpus!r}")
    collection, chunks = load_index()
    per_list = max(PER_QUERY_K, top_k)
    dense = _dense(collection, chunks, query, corpus, per_list)
    sparse = _bm25(chunks, query, corpus, per_list)
    fused = rrf([dense, sparse], k=RRF_K)
    return fused[:top_k]


def search_corpus(query: str, corpus: str, top_k: int = 4) -> SearchKnowledgeResult:
    """Search one corpus and wrap each passage as untrusted text."""
    found = retrieve(query, corpus, top_k)
    hits = [
        Hit(
            chunk_id=chunk.chunk_id,
            source=chunk.source,
            text=as_untrusted(chunk.text) or "",
            score=round(score, 6),
        )
        for chunk, score in found
    ]
    if hits:
        summary = f"{len(hits)} {corpus} hits"
    else:
        summary = f"no {corpus} hits"
    return SearchKnowledgeResult(status="ok", hits=hits, summary=summary)


def _print_summary(summary: dict) -> None:
    print(f"chunks: {summary['chunks']}")
    print(f"catalog nodes: {summary['catalog_nodes']}")
    for corpus, count in summary["by_corpus"].items():
        print(f"  {corpus}: {count}")
    print(f"chroma documents: {summary['chroma_documents']}")
    print(f"build time: {summary['seconds']:.1f}s")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the knowledge index.")
    parser.add_argument(
        "--build",
        action="store_true",
        help="Regenerate catalog cards and recreate the Chroma collection.",
    )
    args = parser.parse_args(argv)
    if not args.build:
        parser.error(f"pass --build. run: {BUILD_COMMAND}")
    _print_summary(build_index())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
