"""Inspect indexed source text and parent context when reviewing gold labels."""
import argparse
import json

from src.common import ROOT, read_jsonl


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contains", default="")
    parser.add_argument("--id")
    parser.add_argument("--parent", action="store_true")
    args = parser.parse_args()
    chunks = read_jsonl(ROOT / "data/chunks.jsonl")
    parents = {parent["parent_id"]: parent for parent in read_jsonl(ROOT / "data/parents.jsonl")} if args.parent else {}
    for chunk in chunks:
        if args.id and chunk["chunk_id"] != args.id:
            continue
        if args.contains.lower() not in chunk["text"].lower():
            continue
        print(json.dumps(chunk, ensure_ascii=False, indent=2))
        if args.parent and chunk.get("parent_id") in parents:
            print("PARENT CONTEXT (không tự động đưa vào prompt):")
            print(parents[chunk["parent_id"]]["text"])


if __name__ == "__main__":
    main()
