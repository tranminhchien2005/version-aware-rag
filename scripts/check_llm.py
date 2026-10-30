"""One real A/B/C smoke run, not an independent quality experiment."""
import argparse
import json
import os
import sys

from src.common import ROOT, DataError, read_json, redact, utc_now, write_json
from src.runtime import make_pipeline


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["A", "B", "C", "ABC"], default="ABC")
    parser.add_argument("--retry-verification", action="store_true", help="Thử lại riêng verifier trên đúng B đã lưu, không sinh lại B")
    args = parser.parse_args()
    pipeline = make_pipeline(log_path=ROOT / "results/runs/live_smoke_trace.jsonl")
    # This smoke command is capped at one attempt per stage: at most three HTTP
    # generation attempts for A, B and verification. Normal app retry is unchanged.
    os.environ["LLM_MAX_ATTEMPTS"] = "1"
    previous_verifications = []
    try:
        if args.retry_verification:
            saved = read_json(ROOT / "results/live_smoke.json")
            b_record = next((record for record in saved["records"] if record["mode"] == "B"), None)
            if not b_record or b_record["status"] != "answer":
                raise DataError("Không có bản nháp B trả lời để kiểm chứng lại")
            if b_record["llm_calls"][0].get("requested_model_id") != os.environ.get("LLM_MODEL", "").strip():
                raise DataError("Model đã thay đổi; không dùng lại B cho phép so sánh này")
            if b_record["corpus_version"] != read_json(ROOT / "data/index/meta.json")["corpus_version"]:
                raise DataError("Corpus đã thay đổi; không dùng lại B cũ")
            previous_verifications = saved.get("previous_verification_records", []) + [record for record in saved["records"] if record["mode"] == "C"]
            c_record = pipeline.verify_b(b_record)
            c_record["verification_retry_of"] = previous_verifications[-1]["run_id"] if previous_verifications else None
            records = [record for record in saved["records"] if record["mode"] != "C"] + [c_record]
        else:
            question = "tomllib trong Python 3.11 có ghi được file TOML không?"
            records = pipeline.run_paired(question, ["3.11"], "live_smoke_dev") if args.mode == "ABC" else [pipeline.run(question, ["3.11"], args.mode, "live_smoke_dev")]
    finally:
        pipeline.close()
    result = {"kind": "live_api_smoke_test_not_independent_quality_evaluation", "checked_at": utc_now(),
              "notice": "Một câu phát triển để kiểm tra tích hợp thật. Không dùng làm chỉ số chất lượng test.",
              "records": records, "previous_verification_records": previous_verifications}
    write_json(ROOT / "results/live_smoke.json", redact(result))
    print(json.dumps(redact([{"mode": record["mode"], "status": record["status"], "answer": record["answer"],
                             "models": [llm_call.get("model_id") for llm_call in record["llm_calls"]], "usage": record["usage"],
                             "error": record["error"]} for record in records]), ensure_ascii=False, indent=2))
    return 1 if any(record["status"] == "error" for record in records) else 0


if __name__ == "__main__":
    sys.exit(main())
