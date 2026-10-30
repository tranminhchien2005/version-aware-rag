"""Suggest evidence to inspect; never promote AI proposals to reviewed gold."""
import argparse

from src.common import ROOT, DataError, load_config, read_jsonl, write_jsonl
from src.runtime import make_retriever
from src.version_policy import prepare


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="data/dev_evidence_candidates.jsonl")
    args = parser.parse_args()
    target = ROOT / args.out
    if target.exists():
        raise DataError("File gợi ý đã có; chọn --out khác để giữ bản đang rà soát")
    retriever = make_retriever(load_config())
    rows = []
    for question in read_jsonl(ROOT / "data/dev.jsonl"):
        request = prepare(question["question"], question["requested_versions"], "B")
        candidates = {}
        if request["status"] == "ready":
            for mode in "AB":
                for evidence_item in retriever.search(question["question"], request["versions"], mode):
                    candidates[evidence_item["chunk_id"]] = {k: evidence_item[k] for k in ("chunk_id", "source_version", "section", "text", "url", "score", "evidence_role")}
        rows.append({"question_id": question["question_id"], "question": question["question"],
                     "notice": "Gợi ý truy xuất, chưa xác nhận đủ/đúng. Không chép thẳng thành gold.",
                     "review_status": "needs_human_review", "corpus_version": retriever.corpus_version,
                     "evidence_candidates": list(candidates.values())})
    write_jsonl(target, rows)
    print("Đã tạo gợi ý nguồn cho {} câu phát triển; cần người mở nguồn và rà soát.".format(len(rows)))


if __name__ == "__main__":
    main()
