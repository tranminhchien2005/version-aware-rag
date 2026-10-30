"""Normalized vector search, filtering BEFORE top-k, strict index alignment."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from .common import ROOT, DataError, digest, file_hash, load_config, read_json, read_jsonl, write_json
from .generate import evidence_for_prompt
from .version_policy import eligible, validate_chunk


def build_index(root, embedder):
    root = Path(root)
    chunks = read_jsonl(root / "data/chunks.jsonl")
    chunk_meta = read_json(root / "data/chunk_meta.json")
    if chunk_meta["embedding"] != embedder.identity or chunk_meta["chunks_sha256"] != file_hash(root / "data/chunks.jsonl"):
        raise DataError("Mô hình/tokenizer hoặc chunks đã đổi; tạo lại chunks trước")
    for chunk in chunks:
        validate_chunk(chunk)
    vectors = np.asarray(embedder.encode([chunk["text"] for chunk in chunks]), dtype=np.float32)
    index_folder = root / "data/index"
    index_folder.mkdir(parents=True, exist_ok=True)
    np.save(index_folder / "vectors.npy", vectors, allow_pickle=False)
    meta = {"chunks_sha256": file_hash(root / "data/chunks.jsonl"),
            "vectors_sha256": file_hash(index_folder / "vectors.npy"), "embedding": embedder.identity,
            "chunk_ids": [chunk["chunk_id"] for chunk in chunks], "shape": list(vectors.shape)}
    meta["corpus_version"] = digest(meta)
    write_json(index_folder / "meta.json", meta)
    return meta


class Retriever:
    def __init__(self, chunks, vectors, embedder, meta, config):
        self.chunks, self.vectors, self.embedder = chunks, np.asarray(vectors), embedder
        self.meta, self.config = meta, config
        chunk_ids = [chunk["chunk_id"] for chunk in chunks]
        if (not chunks or len(set(chunk_ids)) != len(chunk_ids) or chunk_ids != meta["chunk_ids"]
                or self.vectors.ndim != 2 or self.vectors.shape[0] != len(chunks)
                or list(self.vectors.shape) != meta["shape"]):
            raise DataError("Lệch ánh xạ vector và chunk_id; dựng lại chỉ mục")
        if not np.all(np.isfinite(self.vectors)) or not np.allclose(np.linalg.norm(self.vectors, axis=1), 1, atol=1e-4):
            raise DataError("Vector phải hữu hạn và đã chuẩn hóa")
        for chunk in chunks:
            validate_chunk(chunk)
        self.corpus_version = meta["corpus_version"]

    @classmethod
    def load(cls, root, embedder, config):
        root = Path(root)
        meta = read_json(root / "data/index/meta.json")
        for path, key in (("data/chunks.jsonl", "chunks_sha256"), ("data/index/vectors.npy", "vectors_sha256")):
            if file_hash(root / path) != meta[key]:
                raise DataError("Dữ liệu/chỉ mục đã đổi: " + path)
        if meta["embedding"] != embedder.identity:
            raise DataError("Mô hình hoặc tokenizer khác lúc lập chỉ mục")
        if meta["corpus_version"] != digest({k: v for k, v in meta.items() if k != "corpus_version"}):
            raise DataError("Metadata chỉ mục không nhất quán")
        return cls(read_jsonl(root / "data/chunks.jsonl"), np.load(root / "data/index/vectors.npy", allow_pickle=False), embedder, meta, config)

    def search(self, question, versions, mode):
        query_vector = np.asarray(self.embedder.encode([question])[0])
        if (query_vector.shape != self.vectors.shape[1:]
                or not np.all(np.isfinite(query_vector))
                or not np.isclose(np.linalg.norm(query_vector), 1, atol=1e-4)):
            raise DataError("Vector câu hỏi sai số chiều hoặc không chuẩn hóa")
        similarity_scores = self.vectors @ query_vector

        def ranked(indices, top_k):
            return sorted(indices, key=lambda chunk_index: (-float(similarity_scores[chunk_index]), chunk_index))[:top_k]

        if mode == "A":
            selected_indices = ranked(range(len(self.chunks)), 5 * len(versions))
        elif mode in ("B", "C"):
            ranked_by_version = [
                ranked([chunk_index for chunk_index, chunk in enumerate(self.chunks)
                        if eligible(chunk, version)], 5)
                for version in versions
            ]
            # Round-robin gives both versions a fair chance under the shared budget.
            selected_indices = []
            for rank in range(5):
                for version_indices in ranked_by_version:
                    if rank < len(version_indices) and version_indices[rank] not in selected_indices:
                        selected_indices.append(version_indices[rank])
        else:
            raise DataError("Chế độ truy xuất không hợp lệ")
        context_token_limit = self.config["context_tokens_single" if len(versions) == 1 else "context_tokens_compare"]
        evidence = []
        prompt_evidence = []
        for chunk_index in selected_indices:
            item = dict(self.chunks[chunk_index], score=float(similarity_scores[chunk_index]))
            # Budget counts all serialized evidence (incl. metadata), using the same
            # embedding tokenizer for A/B. It is NOT the provider's billing tokenizer.
            prompt_item = evidence_for_prompt([item])[0]
            serialized = json.dumps(prompt_evidence + [prompt_item], ensure_ascii=False)
            if self.embedder.token_count(serialized) <= context_token_limit:
                evidence.append(item)
                prompt_evidence.append(prompt_item)
        return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query")
    parser.add_argument("--version", nargs="+", default=["3.11"])
    parser.add_argument("--mode", choices=["A", "B"], default="B")
    args = parser.parse_args()
    from .embedding import SentenceEmbedder
    config = load_config()
    embedder = SentenceEmbedder(config)
    if args.query:
        from .version_policy import prepare
        prepared = prepare(args.query, args.version, args.mode)
        if prepared["status"] != "ready":
            print(prepared["message"])
            return
        print(json.dumps(Retriever.load(ROOT, embedder, config).search(args.query, prepared["versions"], args.mode), ensure_ascii=False, indent=2))
    else:
        meta = build_index(ROOT, embedder)
        print(json.dumps({"shape": meta["shape"], "embedding": meta["embedding"],
                          "corpus_version": meta["corpus_version"], "metadata": "data/index/meta.json"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
