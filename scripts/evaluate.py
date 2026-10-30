"""Freeze -> paired runs -> human scoring template -> numerical report."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import random
import sys
from pathlib import Path

from src.common import ROOT, DataError, append_jsonl, digest, file_hash, load_environment, read_json, read_jsonl, utc_now, write_json, write_jsonl
from src.evaluation import summarize, validate_dataset
from src.generate import prompt_version as generation_version
from src.verify import prompt_version as verification_version


def fingerprint(root=ROOT):
    paths = [root / "config.json", root / "requirements.txt", root / "requirements.lock.txt", root / "app.py"]
    paths += sorted((root / "src").glob("*.py")) + sorted((root / "scripts").glob("*.py"))
    paths += [root / "data" / name for name in ("manifest.json", "chunks.jsonl", "parents.jsonl", "chunk_meta.json", "history_reviews.json", "dev.jsonl", "test.jsonl")]
    paths += [root / "data/index/meta.json", root / "data/index/vectors.npy"]
    manifest = read_json(root / "data/manifest.json")
    paths += [root / page["local_path"] for page in manifest]
    package_versions = {dist.metadata["Name"].lower(): dist.version for dist in importlib.metadata.distributions()
                if dist.metadata.get("Name")}
    return {"files": {path.relative_to(root).as_posix(): file_hash(path) for path in paths},
            "packages": package_versions, "python": sys.version, "model_id": os.environ.get("LLM_MODEL", ""),
            "llm_timeout_seconds": os.environ.get("LLM_TIMEOUT_SECONDS", "60"),
            "llm_max_attempts": os.environ.get("LLM_MAX_ATTEMPTS", "2"),
            "prompts": {"generate": generation_version(), "verify": verification_version()}}


def freeze(args):
    questions = read_jsonl(ROOT / "data" / (args.split + ".jsonl"))
    other_questions = read_jsonl(ROOT / "data" / ("test.jsonl" if args.split == "dev" else "dev.jsonl"))
    if not questions:
        raise DataError("Tập câu hỏi rỗng; chuẩn bị và rà soát trước khi đóng băng")
    known_chunk_ids = {chunk["chunk_id"] for chunk in read_jsonl(ROOT / "data/chunks.jsonl")}
    validate_dataset(questions, other_questions, require_review=True, known_ids=known_chunk_ids)
    if any(question["split"] != args.split for question in questions):
        raise DataError("Nhãn split không khớp tên tập")
    state = fingerprint()
    if not state["model_id"]:
        raise DataError("Cấu hình LLM_MODEL trước khi đóng băng")
    if args.repeats < 1:
        raise DataError("repeats phải ít nhất 1")
    target = Path(args.out)
    if target.exists():
        raise DataError("Thư mục đóng băng đã tồn tại; chọn thư mục mới")
    target.mkdir(parents=True)
    write_jsonl(target / "questions.jsonl", questions)
    write_json(target / "freeze.json", {"created_at": utc_now(), "split": args.split, "state": state,
               "fingerprint": digest(state), "questions_sha256": file_hash(target / "questions.jsonl"),
               "seed": args.seed, "repeats": args.repeats,
               "timing": "Nạp và warm-up embedding trước vòng đo; C = tổng B + kiểm chứng; p95 nearest rank"})
    print("Đã đóng băng: " + str(target))


def run(args):
    from src.runtime import make_pipeline, make_retriever
    from src.common import load_config
    folder = Path(args.frozen)
    snapshot = read_json(folder / "freeze.json")
    if snapshot["fingerprint"] != digest(snapshot["state"]):
        raise DataError("Snapshot có fingerprint không nhất quán")
    if not os.environ.get("GEMINI_API_KEY"):
        raise DataError("Cấu hình API key trên máy trước khi bắt đầu lượt thực nghiệm")
    if fingerprint() != snapshot["state"]:
        raise DataError("Mã, cấu hình, thư viện hoặc dữ liệu đã thay đổi sau đóng băng")
    if file_hash(folder / "questions.jsonl") != snapshot["questions_sha256"]:
        raise DataError("Tập câu hỏi đóng băng đã đổi")
    marker = folder / "RUN_STARTED.json"
    if marker.exists():
        raise DataError("Snapshot này đã bắt đầu chạy. Giữ log hiện có; tạo snapshot và công bố lần chạy mới nếu cần.")
    config = load_config()
    retriever = make_retriever(config)
    retriever.embedder.encode(["warm up"])
    questions = read_jsonl(folder / "questions.jsonl")
    # Exclusive marker also prevents two concurrent runs of the same experiment.
    with marker.open("x", encoding="utf-8") as stream:
        json.dump({"started_at": utc_now()}, stream)
    output = folder / "runs.jsonl"
    pipeline = make_pipeline(retriever_factory=lambda: retriever, log_path=folder / "trace.jsonl")
    randomizer = random.Random(snapshot["seed"])
    completed = 0
    try:
        for repetition in range(snapshot["repeats"]):
            shuffled = list(questions)
            randomizer.shuffle(shuffled)
            for question in shuffled:
                order = randomizer.choice(["AB", "BA"])
                records = pipeline.run_paired(question["question"], question["requested_versions"], question["question_id"], order)
                for record in records:
                    record.update(repetition=repetition + 1, freeze_fingerprint=snapshot["fingerprint"])
                    append_jsonl(output, record)
                completed += 1
                print("{} lượt câu hỏi đã hoàn thành".format(completed), flush=True)
    finally:
        pipeline.close()
        write_json(folder / "RUN_FINISHED.json", {"finished_at": utc_now(), "completed_question_runs": completed,
                   "expected_question_runs": len(questions) * snapshot["repeats"]})


def template(args):
    records = read_jsonl(args.runs)
    questions_by_id = {question["question_id"]: question for question in read_jsonl(args.questions)}
    review_rows = []
    for record in records:
        question = questions_by_id[record["question_id"]]
        review_rows.append({"run_id": record["run_id"], "question_id": record["question_id"], "mode": record["mode"],
                     "question": record["question"], "expected_action": question["expected_action"], "gold_claims": question["gold_claims"],
                     "system_status": record["status"], "system_answer": record["answer"], "claims": record["claims"],
                     "evidence": record["evidence"], "answer_correct": None, "version_error": None,
                     "citation_links_correct": None, "citation_links_total": sum(len(claim["evidence_ids"]) for claim in record["claims"]),
                     "claims_supported": None, "claims_total": len(record["claims"]), "retrieval_sufficient": None,
                     "review_status": "needs_human_review", "reviewer": "", "reviewed_at": "", "notes": ""})
    if Path(args.out).exists():
        raise DataError("Không ghi đè phiếu chấm đã có")
    write_jsonl(args.out, review_rows)
    print("Đã tạo phiếu chấm; xem notes/CHAM_DIEM.md")


def report(args):
    records, questions, reviews = read_jsonl(args.runs), read_jsonl(args.questions), read_jsonl(args.reviews)
    validate_dataset(questions, require_review=True)
    question_ids = {question["question_id"] for question in questions}
    if any(record["question_id"] not in question_ids for record in records):
        raise DataError("Log chứa câu hỏi không có trong gold")
    # Require all A/B/C for every question/repetition; incomplete experiments are
    # visible as errors, not denominators quietly shrinking to successful rows.
    repetitions = {record.get("repetition", 1) for record in records}
    identities = [(record["question_id"], record.get("repetition", 1), record["mode"]) for record in records]
    expected = {(question_id, repetition, mode) for question_id in question_ids for repetition in repetitions for mode in "ABC"}
    if not records or len(set(identities)) != len(identities) or set(identities) != expected:
        raise DataError("Log chưa đủ A/B/C cho mọi câu hoặc có lượt bị trùng")
    run_lookup = {record["run_id"]: record for record in records}
    if len({record.get("freeze_fingerprint") for record in records}) != 1:
        raise DataError("Không gộp kết quả của nhiều snapshot vào cùng phép so sánh")
    finished = Path(args.runs).parent / "RUN_FINISHED.json"
    if finished.exists():
        finish = read_json(finished)
        if finish["completed_question_runs"] != finish["expected_question_runs"]:
            raise DataError("Lượt chạy chưa đủ số lần lặp đã định trước")
    for record in records:
        if record["mode"] == "C":
            b_record = run_lookup.get(record.get("paired_b_run_id"))
            if (not b_record or b_record["mode"] != "B" or b_record["question_id"] != record["question_id"]
                    or b_record["draft_claims"] != record["draft_claims"] or b_record["evidence"] != record["evidence"]
                    or record["latency_ms"] < b_record["latency_ms"] or record["usage"]["calls"] < b_record["usage"]["calls"]):
                raise DataError("Kết quả C không khớp bản nháp, bằng chứng hoặc chi phí của B")
    group_metrics = {"all": summarize(records, questions, reviews)}
    for group in sorted({question["group_id"] for question in questions}):
        group_questions = [question for question in questions if question["group_id"] == group]
        group_question_ids = {question["question_id"] for question in group_questions}
        group_records = [record for record in records if record["question_id"] in group_question_ids]
        run_ids = {record["run_id"] for record in group_records}
        group_metrics[group] = summarize(group_records, group_questions, [review for review in reviews if review["run_id"] in run_ids])
    write_json(args.out, group_metrics)
    lines = ["# Kết quả thực nghiệm", "", "N/A: mẫu số bằng 0 hoặc chưa chấm đủ. Đọc cùng số đếm trong JSON.", "",
             "| Chỉ số | A | B | C |", "|---|---|---|---|"]
    metrics = group_metrics["all"]
    for name in ("accuracy_gold_answerable", "accuracy_when_answered", "coverage_all", "coverage_gold_answerable",
                 "version_error_rate", "citation_precision", "citation_completeness", "action_accuracy", "retrieval_sufficient", "error_rate"):
        metric_cells = []
        for mode in "ABC":
            metric = metrics[mode][name]
            value = "N/A" if metric["value"] is None else "{:.1%}".format(metric["value"])
            metric_cells.append("{} ({}/{})".format(value, metric["numerator"], metric["denominator"]))
        lines.append("| " + " | ".join([name] + metric_cells) + " |")
    Path(args.out).with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Đã tổng hợp từ log và phiếu chấm, không dùng verifier làm giám khảo.")


def main():
    load_environment()
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    command_parser = subcommands.add_parser("validate")
    command_parser.add_argument("--require-review", action="store_true")
    command_parser = subcommands.add_parser("freeze")
    command_parser.add_argument("--split", choices=["dev", "test"], required=True)
    command_parser.add_argument("--out", required=True)
    command_parser.add_argument("--repeats", type=int, default=1)
    command_parser.add_argument("--seed", type=int, default=2026)
    command_parser = subcommands.add_parser("run")
    command_parser.add_argument("--frozen", required=True)
    command_parser = subcommands.add_parser("review-template")
    command_parser.add_argument("--runs", required=True)
    command_parser.add_argument("--questions", required=True)
    command_parser.add_argument("--out", required=True)
    command_parser = subcommands.add_parser("summarize")
    for option in ("runs", "questions", "reviews", "out"):
        command_parser.add_argument("--" + option, required=True)
    args = parser.parse_args()
    if args.command == "validate":
        print(validate_dataset(read_jsonl(ROOT / "data/dev.jsonl"), read_jsonl(ROOT / "data/test.jsonl"), require_review=args.require_review))
    else:
        {"freeze": freeze, "run": run, "review-template": template, "summarize": report}[args.command](args)


if __name__ == "__main__":
    main()
