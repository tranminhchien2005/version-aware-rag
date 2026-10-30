"""Read-only checks of real corpus/index; does not call a generative LLM."""
import json

from src.common import ROOT, DataError, file_hash, load_config, read_json, read_jsonl, utc_now, write_json
from src.runtime import make_retriever


def main():
    manifest = read_json(ROOT / "data/manifest.json")
    chunks = read_jsonl(ROOT / "data/chunks.jsonl")
    for page in manifest:
        if file_hash(ROOT / page["local_path"]) != page["sha256"]:
            raise DataError("HTML không khớp manifest")
    config = load_config()
    retriever = make_retriever(config)
    results = []
    cases = [("tomllib trong Python 3.11 có ghi TOML không?", ["3.11"]),
             ("asyncio.create_task trong Python 3.10 dùng thế nào?", ["3.10"]),
             ("So sánh TaskGroup trong Python 3.10 và 3.11", ["3.10", "3.11"])]
    for question, versions in cases:
        for mode in "AB":
            evidence = retriever.search(question, versions, mode)
            if len(evidence) > 5 * len(versions):
                raise DataError("Vượt giới hạn số đoạn")
            if mode == "B":
                from src.version_policy import eligible
                if any(not any(eligible(evidence_item, version) for version in versions) for evidence_item in evidence):
                    raise DataError("Nguồn sai phiên bản đi qua bộ lọc")
            results.append({"question": question, "versions": versions, "mode": mode,
                            "evidence": [{k: evidence_item[k] for k in ("chunk_id", "source_version", "section", "score", "url")} for evidence_item in evidence]})
    max_tokens = max(retriever.embedder.token_count(chunk["text"]) for chunk in chunks)
    if max_tokens > retriever.embedder.max_seq_length:
        raise DataError("Chunk vượt cửa sổ embedding")
    summary = {"checked_at": utc_now(), "kind": "real_corpus_embedding_integration_check",
               "notice": "Kiểm tra dữ liệu và truy xuất thật; chưa đo độ chính xác câu trả lời hoặc LLM kiểm chứng.",
               "pages": len(manifest), "chunks": len(chunks), "history_notes": sum(chunk["evidence_role"] == "history_note" for chunk in chunks),
               "embedding": retriever.embedder.identity, "largest_chunk_tokens": max_tokens,
               "corpus_version": retriever.corpus_version, "retrieval_cases": results}
    write_json(ROOT / "results/data_checks.json", summary)
    print(json.dumps({k: version for k, version in summary.items() if k != "retrieval_cases"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
