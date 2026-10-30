"""Command-line equivalent of the UI; --compare shares the exact B draft."""
import argparse
import json

from src.runtime import make_pipeline


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question")
    parser.add_argument("--versions", nargs="*", default=[])
    parser.add_argument("--mode", choices=["A", "B", "C"], default="B")
    parser.add_argument("--compare", action="store_true")
    args = parser.parse_args()
    pipeline = make_pipeline()
    try:
        result = pipeline.run_paired(args.question, args.versions) if args.compare else pipeline.run(args.question, args.versions, args.mode)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        pipeline.close()


if __name__ == "__main__":
    main()
