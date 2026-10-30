"""Dataset validation and transparent metrics from HUMAN scoring, never verifier labels."""
from __future__ import annotations

import math
import statistics

from .common import DataError, STATUSES

def validate_dataset(rows, other_rows=(), require_review=True, known_ids=None):
    question_ids, group_splits, normalized_questions = set(), {}, {}
    rows = list(rows)
    selected_ids = {row.get("question_id") for row in rows}
    for row in rows + list(other_rows):
        for key in ("question_id", "question", "group_id", "split", "expected_action", "review_status"):
            if not isinstance(row.get(key), str) or not row[key].strip():
                raise DataError("Câu hỏi thiếu " + key)
        if row["question_id"] in question_ids:
            raise DataError("Trùng question_id")
        question_ids.add(row["question_id"])
        if row["split"] not in ("dev", "test") or row["expected_action"] not in STATUSES[:-1]:
            raise DataError("split hoặc expected_action không hợp lệ")
        group = row["group_id"]
        if group in group_splits and group_splits[group] != row["split"]:
            raise DataError("Rò rỉ group_id qua dev/test: " + group)
        group_splits[group] = row["split"]
        text = " ".join(row["question"].lower().split())
        if text in normalized_questions and normalized_questions[text] != row["split"]:
            raise DataError("Câu gần trùng chính xác nằm ở hai tập")
        normalized_questions[text] = row["split"]
        versions = row.get("requested_versions")
        if not isinstance(versions, list) or any(not isinstance(version, str) for version in versions):
            raise DataError("Thiếu requested_versions")
        gold = row.get("gold_claims")
        if not isinstance(gold, list) or any(not isinstance(gold_claim, str) or not gold_claim.strip() for gold_claim in gold):
            raise DataError("gold_claims phải là list chuỗi")
        evidence_sets = row.get("acceptable_evidence_sets")
        if (not isinstance(evidence_sets, list) or any(not isinstance(evidence_set, list) or not evidence_set
                or any(not isinstance(evidence_id, str) or not evidence_id for evidence_id in evidence_set) for evidence_set in evidence_sets)):
            raise DataError("acceptable_evidence_sets phải chứa các bộ mã bằng chứng đủ")
        if known_ids is not None and any(evidence_id not in known_ids for evidence_set in evidence_sets for evidence_id in evidence_set):
            raise DataError("Gold có evidence_id ngoài corpus")
        if require_review and row["question_id"] in selected_ids:
            if row["review_status"] != "human_reviewed" or not row.get("reviewer") or not row.get("reviewed_at"):
                raise DataError("Câu hỏi cần người rà soát: " + row["question_id"])
            if row["expected_action"] == "answer" and (not gold or not evidence_sets):
                raise DataError("Câu có đáp án phải có gold_claims và bộ bằng chứng")
            if row["expected_action"] != "answer" and not row.get("rationale"):
                raise DataError("Cần lý do cho hành động không trả lời")
    return {"questions": len(rows), "groups": len({r["group_id"] for r in rows})}


def ratio(numerator, denominator):
    return {"numerator": numerator, "denominator": denominator,
            "value": numerator / denominator if denominator else None}


def pending_ratio(numerator, denominator, pending):
    result = ratio(numerator, denominator)
    result["pending_review"] = pending
    # Do not let unfinished manual scoring look like a real accuracy figure.
    if pending:
        result["value"] = None
    return result


def percentile95(values):
    return sorted(values)[max(0, math.ceil(.95 * len(values)) - 1)] if values else None


def validate_score(score, record):
    if score.get("review_status") != "human_reviewed":
        return False
    if not score.get("reviewer") or not score.get("reviewed_at"):
        raise DataError("Chấm thủ công thiếu tên/ngày người chấm")
    if record["status"] == "answer":
        for field in ("answer_correct", "version_error"):
            if type(score.get(field)) is not bool:
                raise DataError("Điểm " + field + " phải là true/false")
        for field in ("citation_links_correct", "citation_links_total", "claims_supported", "claims_total"):
            if type(score.get(field)) is not int or score[field] < 0:
                raise DataError("Điểm " + field + " phải là số nguyên không âm")
        actual_links = sum(len(claim["evidence_ids"]) for claim in record["claims"])
        if score["citation_links_total"] != actual_links or score["claims_total"] != len(record["claims"]):
            raise DataError("Mẫu số chấm không khớp claim/liên kết thực tế")
        if (score["citation_links_correct"] > actual_links or score["claims_supported"] > score["claims_total"]):
            raise DataError("Tử số không được vượt mẫu số")
    if score.get("retrieval_sufficient") is not None and type(score["retrieval_sufficient"]) is not bool:
        raise DataError("retrieval_sufficient phải là true/false hoặc null")
    return True


def summarize(records, questions, reviews):
    questions_by_id = {question["question_id"]: question for question in questions}
    if len(questions_by_id) != len(questions):
        raise DataError("Trùng gold question_id")
    reviews_by_run_id = {review["run_id"]: review for review in reviews}
    if len(reviews_by_run_id) != len(reviews) or len({record["run_id"] for record in records}) != len(records):
        raise DataError("Trùng run_id")
    if set(reviews_by_run_id) - {record["run_id"] for record in records}:
        raise DataError("Phiếu chấm có run_id không tồn tại")
    if any(record.get("synthetic") for record in records):
        raise DataError("Không dùng log giả lập làm kết quả thực nghiệm")
    if any(record.get("question_id") not in questions_by_id or record.get("mode") not in ("A", "B", "C") or record.get("status") not in STATUSES for record in records):
        raise DataError("Log chứa câu hỏi, mode hoặc trạng thái không hợp lệ")
    results = {}
    for mode in "ABC":
        mode_records = [record for record in records if record["mode"] == mode]
        answered = [record for record in mode_records if record["status"] == "answer"]
        answerable_records = [record for record in mode_records if questions_by_id[record["question_id"]]["expected_action"] == "answer"]
        reviewed_by_run_id, pending_answer_records = {}, []
        for record in mode_records:
            score = reviews_by_run_id.get(record["run_id"], {})
            if validate_score(score, record):
                reviewed_by_run_id[record["run_id"]] = score
            elif record["status"] == "answer":
                pending_answer_records.append(record)
        answer_reviews = [reviewed_by_run_id[record["run_id"]] for record in answered if record["run_id"] in reviewed_by_run_id]
        correct_answers = sum(review["answer_correct"] for review in answer_reviews)
        correct_answerable = sum(
            reviewed_by_run_id[record["run_id"]]["answer_correct"] for record in answerable_records
            if record["status"] == "answer" and record["run_id"] in reviewed_by_run_id)
        pending_answerable = sum(questions_by_id[record["question_id"]]["expected_action"] == "answer" for record in pending_answer_records)
        retrieval_ok, retrieval_total, retrieval_pending = 0, 0, 0
        single_source_correct, single_source_total, multiple_source_correct, multiple_source_total = 0, 0, 0, 0
        for record in answerable_records:
            evidence_sets = questions_by_id[record["question_id"]].get("acceptable_evidence_sets", [])
            if not evidence_sets:
                retrieval_pending += 1
                continue
            retrieval_total += 1
            manual = reviewed_by_run_id.get(record["run_id"], {}).get("retrieval_sufficient")
            ok = manual if manual is not None else any(set(evidence_set) <= set(record["retrieved_ids"]) for evidence_set in evidence_sets)
            retrieval_ok += ok
            if min(map(len, evidence_sets)) == 1:
                single_source_total += 1
                single_source_correct += ok
            else:
                multiple_source_total += 1
                multiple_source_correct += ok
        times = [record["latency_ms"] for record in mode_records]
        usage_complete = all(record["usage"].get("usage_complete", False) for record in mode_records)
        results[mode] = {
            "requests": len(mode_records), "answered": len(answered), "human_scored_answers": len(answer_reviews),
            "accuracy_gold_answerable": pending_ratio(correct_answerable, len(answerable_records), pending_answerable),
            "accuracy_when_answered": pending_ratio(correct_answers, len(answered), len(pending_answer_records)),
            "coverage_all": ratio(len(answered), len(mode_records)),
            "coverage_gold_answerable": ratio(sum(record["status"] == "answer" for record in answerable_records), len(answerable_records)),
            "version_error_rate": pending_ratio(
                sum(review["version_error"] for review in answer_reviews), len(answered), len(pending_answer_records)),
            "citation_precision": pending_ratio(
                sum(review["citation_links_correct"] for review in answer_reviews),
                sum(len(claim["evidence_ids"]) for record in answered for claim in record["claims"]),
                len(pending_answer_records)),
            "citation_completeness": pending_ratio(
                sum(review["claims_supported"] for review in answer_reviews),
                sum(len(record["claims"]) for record in answered), len(pending_answer_records)),
            "action_accuracy": ratio(
                sum(record["status"] == questions_by_id[record["question_id"]]["expected_action"]
                    for record in mode_records), len(mode_records)),
            "retrieval_sufficient": pending_ratio(retrieval_ok, retrieval_total, retrieval_pending),
            "retrieval_single_source": ratio(single_source_correct, single_source_total),
            "retrieval_multiple_sources": ratio(multiple_source_correct, multiple_source_total),
            "error_rate": ratio(sum(record["status"] == "error" for record in mode_records), len(mode_records)),
            "latency_median_ms": statistics.median(times) if times else None,
            "latency_p95_ms": percentile95(times), "usage_complete": usage_complete,
            "recorded_tokens": {k: sum(record["usage"].get(k, 0) for record in mode_records)
                                for k in ("input_tokens", "output_tokens", "thought_tokens", "total_tokens", "calls")},
            "cost": "Chưa đo: cần đơn giá theo model, thời điểm, loại token và usage đầy đủ"}
    return results
