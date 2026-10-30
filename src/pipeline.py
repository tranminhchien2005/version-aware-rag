"""One orchestration path; C is a transformation of the exact B record."""
from __future__ import annotations

import copy
import time
import uuid

from . import generate, verify
from .common import DataError, add_usage, append_jsonl, digest, empty_usage, redact, utc_now
from .llm_client import LLMError
from .version_policy import prepare

MESSAGES = {"insufficient_evidence": "Chưa đủ bằng chứng trong kho để xác nhận câu trả lời.",
            "error": "Không hoàn thành được yêu cầu do lỗi dữ liệu hoặc dịch vụ."}


class Pipeline:
    def __init__(self, retriever, client, config, log_path=None):
        self._retriever, self._client = retriever, client
        self.config, self.log_path = config, log_path

    def _get_retriever(self):
        if callable(self._retriever):
            self._retriever = self._retriever()
        return self._retriever

    def _get_client(self):
        if callable(self._client):
            self._client = self._client()
        return self._client

    def close(self):
        if not callable(self._client) and hasattr(self._client, "close"):
            self._client.close()

    def _new(self, question, versions, mode, question_id):
        return {"run_id": uuid.uuid4().hex, "created_at": utc_now(), "question_id": question_id,
                "question": question, "requested_versions": versions, "mode": mode,
                "status": "error", "answer": "", "claims": [], "citations": [],
                "retrieved_ids": [], "evidence": [], "draft_claims": [], "verification": [],
                "latency_ms": 0, "stage_ms": {}, "usage": empty_usage(), "llm_calls": [],
                "config": copy.deepcopy(self.config), "config_version": digest(self.config),
                "prompt_versions": {"generate": generate.prompt_version(), "verify": verify.prompt_version()},
                "corpus_version": None, "error": None, "synthetic": False}

    def _call(self, record, purpose, system, payload, schema):
        started = time.perf_counter()
        call = {"purpose": purpose, "system": system, "payload": payload, "schema_sha256": digest(schema)}
        try:
            client = self._get_client()
            call["requested_model_id"] = getattr(client, "model_id", None)
            reply = client.complete(system, payload, schema, purpose)
            call.update(model_id=reply.model_id, response=reply.data, usage=reply.usage)
            record["usage"] = add_usage(record["usage"], reply.usage)
            return reply.data
        except LLMError as exc:
            call.update(error=str(exc), usage=exc.usage)
            record["usage"] = add_usage(record["usage"], exc.usage)
            raise
        finally:
            call["latency_ms"] = (time.perf_counter() - started) * 1000
            record["stage_ms"][purpose] = call["latency_ms"]
            record["llm_calls"].append(call)

    def _set_answer(self, record, claims):
        record["claims"] = copy.deepcopy(claims)
        record["answer"] = generate.render_answer(claims)
        record["citations"] = generate.citations_for(claims, record["evidence"])
        record["status"] = "answer"

    def _set_insufficient_evidence(self, record):
        # Keep the draft and evidence for tracing, but publish no unchecked claims.
        record.update(status="insufficient_evidence", claims=[], citations=[],
                      answer=MESSAGES["insufficient_evidence"])

    def _error(self, record, exc):
        record.update(status="error", claims=[], citations=[], answer=MESSAGES["error"],
                      error={"type": type(exc).__name__, "message": str(exc)})

    def _save(self, record):
        safe = redact(record)
        if self.log_path:
            try:
                append_jsonl(self.log_path, safe)
            except OSError:
                safe.update(status="error", claims=[], citations=[], answer="Không ghi được nhật ký; kiểm tra quyền ghi và dung lượng.",
                            error={"type": "LogError", "message": "Không lưu được JSONL"})
        return safe

    def _draft(self, question, versions, mode, question_id):
        record = self._new(question, versions, mode, question_id)
        started = time.perf_counter()
        try:
            request = prepare(question, versions, mode)
            record["requested_versions"] = request["versions"]
            if request["status"] != "ready":
                record.update(status=request["status"], answer=request["message"])
                return record
            load_started = time.perf_counter()
            retriever = self._get_retriever()
            record["stage_ms"]["load_index"] = (time.perf_counter() - load_started) * 1000
            record["corpus_version"] = retriever.corpus_version
            search_started = time.perf_counter()
            evidence = retriever.search(question, request["versions"], mode)
            record["stage_ms"]["retrieve"] = (time.perf_counter() - search_started) * 1000
            record["evidence"] = evidence
            record["retrieved_ids"] = [e["chunk_id"] for e in evidence]
            if not evidence:
                self._set_insufficient_evidence(record)
                return record
            data = self._call(record, "generate", generate.SYSTEM,
                              generate.payload_for(question, request["versions"], evidence), generate.SCHEMA)
            draft = generate.validate_draft(data, evidence, request["versions"])
            record["draft_claims"] = copy.deepcopy(draft["claims"])
            if draft["status"] == "answer":
                self._set_answer(record, draft["claims"])
            else:
                self._set_insufficient_evidence(record)
        except Exception as exc:
            self._error(record, exc)
        finally:
            record["latency_ms"] = (time.perf_counter() - started) * 1000
        return record

    def verify_b(self, b_record):
        """No new retrieval or generation here. B is never mutated."""
        if b_record.get("mode") != "B" or b_record.get("config_version") != digest(self.config):
            raise DataError("C phải nhận kết quả B cùng cấu hình")
        c_record = copy.deepcopy(b_record)
        c_record.update(
            run_id=uuid.uuid4().hex, created_at=utc_now(), mode="C", paired_b_run_id=b_record["run_id"],
            b_draft_sha256=digest({"claims": b_record["draft_claims"], "evidence": b_record["evidence"]}))
        started = time.perf_counter()
        try:
            if b_record["status"] == "answer":
                rules = verify.rule_check(b_record["draft_claims"], b_record["evidence"])
                payload = {"claims": b_record["draft_claims"], "requested_versions": b_record["requested_versions"],
                           "evidence": generate.evidence_for_prompt(b_record["evidence"])}
                data = self._call(c_record, "verify", verify.SYSTEM, payload, verify.SCHEMA)
                c_record["verification"] = verify.validate_verdicts(data, b_record["draft_claims"], b_record["evidence"], rules)
                if any(verdict["label"] != "supported" for verdict in c_record["verification"]):
                    self._set_insufficient_evidence(c_record)
        except Exception as exc:
            self._error(c_record, exc)
        c_record["verification_ms"] = (time.perf_counter() - started) * 1000
        c_record["latency_ms"] = b_record["latency_ms"] + c_record["verification_ms"]
        c_record["incremental_usage"] = {
            usage_field: c_record["usage"][usage_field] - b_record["usage"][usage_field]
            for usage_field in empty_usage() if usage_field != "usage_complete"
        }
        c_record["incremental_usage"]["usage_complete"] = all(
            call.get("usage", {}).get("usage_complete", True)
            for call in c_record["llm_calls"] if call["purpose"] == "verify")
        return self._save(c_record)

    def run(self, question, requested_versions, mode="B", question_id=None):
        if mode == "C":
            return self.verify_b(self._draft(question, requested_versions, "B", question_id))
        return self._save(self._draft(question, requested_versions, mode, question_id))

    def run_paired(self, question, requested_versions, question_id=None, order="AB"):
        records = {}
        for mode in order:
            records[mode] = self.run(question, requested_versions, mode, question_id)
        records["C"] = self.verify_b(records["B"])
        return [records[mode] for mode in "ABC"]
