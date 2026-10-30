"""Prepare history-note review forms without marking anything as human-reviewed."""
import argparse

from src.common import ROOT, DataError, read_jsonl, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="data/history_review_draft.json")
    args = parser.parse_args()
    target = ROOT / args.out
    if target.exists():
        raise DataError("File đã tồn tại, không ghi đè bản đang rà soát")
    candidates = read_jsonl(ROOT / "data/history_candidates.jsonl")
    write_json(target, candidates)
    print("Đã tạo {} mục cần người đọc nguồn; chưa mục nào được duyệt.".format(len(candidates)))


if __name__ == "__main__":
    main()
