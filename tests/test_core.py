import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np

from src.common import DataError, empty_usage, read_jsonl
from src.generate import validate_draft
from src.llm_client import LLMError
from src.pipeline import Pipeline
from src.retrieve import Retriever
from src.version_policy import eligible, prepare, valid_source_url, validate_chunk
from src.verify import rule_check, validate_verdicts
from tests.fixtures import CONFIG, FakeEmbedder, QueueClient, chunk, draft, retriever, verdict


class PolicyTests(unittest.TestCase):
    def test_missing_version_identical_for_all_modes(self):
        for mode in "ABC":
            self.assertEqual(prepare("Dùng API thế nào?", [], mode)["status"], "clarify")

    def test_infers_explicit_version_and_patch(self):
        self.assertEqual(prepare("Python 3.11.4 dùng thế nào?", [], "A")["versions"], ["3.11"])

    def test_conflicting_version(self):
        self.assertEqual(prepare("Python 3.10", ["3.11"], "B")["status"], "clarify")

    def test_out_of_scope(self):
        self.assertEqual(prepare("Python 3.12", [], "C")["status"], "out_of_scope")

    def test_decimals_are_not_python_versions(self):
        request = prepare("Python 3.11: math.sqrt(2.0) và số 3.14", ["3.11"], "B")
        self.assertEqual(request["status"], "ready")
        self.assertEqual(request["versions"], ["3.11"])

    def test_version_without_space(self):
        self.assertEqual(prepare("Python3.12 dùng thế nào?", [], "B")["status"], "out_of_scope")

    def test_comparison(self):
        self.assertEqual(prepare("So sánh Python 3.10 và 3.11", [], "B")["versions"], ["3.10", "3.11"])

    def test_wrong_mode(self):
        with self.assertRaises(DataError):
            prepare("Hello", [], "D")

    def test_ordinary_requires_exact_version(self):
        self.assertFalse(eligible(chunk(), "3.10"))
        self.assertTrue(eligible(chunk(), "3.11"))

    def test_history_requires_review_and_targets(self):
        note = chunk(history=True)
        self.assertTrue(eligible(note, "3.10"))
        note["history_targets"] = ["3.11"]
        self.assertFalse(eligible(note, "3.10"))
        note["review_status"] = "needs_human_review"
        self.assertFalse(eligible(note, "3.11"))
        with self.assertRaises(DataError):
            validate_chunk(note)

    def test_source_url_not_laundered(self):
        self.assertFalse(valid_source_url("https://docs.python.org.attacker.test/3.11/", "3.11"))
        self.assertFalse(valid_source_url("https://docs.python.org/3/library/re.html", "3.11"))
        self.assertFalse(valid_source_url("https://docs.python.org/3.10/library/re.html", "3.11"))


class RetrievalTests(unittest.TestCase):
    def test_filter_before_topk(self):
        docs = [chunk("wrong{}".format(i), "3.11") for i in range(6)] + [chunk("right", "3.10")]
        vectors = [[1., 0.]] * 6 + [[.6, .8]]
        r = retriever(docs, vectors)
        self.assertEqual([e["chunk_id"] for e in r.search("q", ["3.10"], "B")], ["right"])
        self.assertNotIn("right", [e["chunk_id"] for e in r.search("q", ["3.10"], "A")])

    def test_comparison_limits_and_deduplication(self):
        docs = [chunk("a{}".format(i), "3.10") for i in range(7)] + [chunk("b{}".format(i)) for i in range(7)]
        result = retriever(docs).search("q", ["3.10", "3.11"], "B")
        self.assertEqual(len(result), 10)
        self.assertEqual(sum(e["source_version"] == "3.10" for e in result), 5)
        docs = [chunk("h", history=True)] + docs
        result = retriever(docs).search("q", ["3.10", "3.11"], "B")
        self.assertEqual(len({e["chunk_id"] for e in result}), len(result))
        self.assertEqual(sum(e["chunk_id"] == "h" for e in result), 1)

    def test_alignment_rejects_permutation(self):
        with self.assertRaises(DataError):
            Retriever([chunk("a"), chunk("b")], np.array([[1, 0], [1, 0]]), FakeEmbedder(),
                      {"chunk_ids": ["b", "a"], "shape": [2, 2], "corpus_version": "x"}, CONFIG)

    def test_invalid_vectors(self):
        with self.assertRaises(DataError):
            retriever([chunk()], [[float("nan"), 0]])
        with self.assertRaises(DataError):
            retriever([chunk()], [[0, 0]])

    def test_context_budget_identical(self):
        r = retriever()
        r.config = dict(CONFIG, context_tokens_single=1)
        self.assertEqual(r.search("q", ["3.11"], "A"), [])
        self.assertEqual(r.search("q", ["3.11"], "B"), [])

    def test_oversized_candidate_does_not_consume_later_candidates_budget(self):
        oversized = dict(chunk("oversized"), text="Oversized evidence. " * 1000)
        r = retriever([oversized, chunk("fits")])
        r.config = dict(CONFIG, context_tokens_single=100)
        for mode in "ABC":
            with self.subTest(mode=mode):
                self.assertEqual([item["chunk_id"] for item in r.search("q", ["3.11"], mode)], ["fits"])


class GenerationTests(unittest.TestCase):
    def test_unknown_citation_is_error(self):
        with self.assertRaises(DataError):
            validate_draft(draft("invented"), [chunk()], ["3.11"])

    def test_extra_url_field_is_error(self):
        data = draft()
        data["claims"][0]["url"] = "https://attacker.test"
        with self.assertRaises(DataError):
            validate_draft(data, [chunk()], ["3.11"])

    def test_empty_answer_invalid(self):
        with self.assertRaises(DataError):
            validate_draft({"status": "answer", "claims": []}, [], ["3.11"])

    def test_wrong_claim_version_invalid(self):
        with self.assertRaises(DataError):
            validate_draft(draft(version="3.10"), [chunk()], ["3.11"])


class VerifierTests(unittest.TestCase):
    def setUp(self):
        self.claims = validate_draft(draft(), [chunk()], ["3.11"])["claims"]

    def test_missing_and_duplicate_verdict(self):
        for data in ({"verdicts": []}, {"verdicts": [verdict(), verdict()]}):
            with self.assertRaises(DataError):
                validate_verdicts(data, self.claims, [chunk()], {})

    def test_invalid_evidence(self):
        with self.assertRaises(DataError):
            validate_verdicts({"verdicts": [verdict(eid="invented")]}, self.claims, [chunk()], {})

    def test_invalid_label(self):
        with self.assertRaises(DataError):
            validate_verdicts({"verdicts": [verdict(label="probably")]}, self.claims, [chunk()], {})

    def test_rule_overrides_false_supported(self):
        self.claims[0]["applies_to"] = ["3.10"]
        rules = rule_check(self.claims, [chunk()])
        result = validate_verdicts({"verdicts": [verdict()]}, self.claims, [chunk()], rules)
        self.assertEqual(result[0]["label"], "contradicted")

    def test_history_exception(self):
        self.claims[0]["applies_to"] = ["3.10"]
        self.assertEqual(rule_check(self.claims, [chunk(history=True)]), {})

    def test_supported_must_cover_both_versions(self):
        self.claims[0].update(applies_to=["3.10", "3.11"], evidence_ids=["d310", "d311"])
        data = validate_verdicts({"verdicts": [verdict()]}, self.claims, [chunk("d310", "3.10"), chunk()], {})
        self.assertEqual(data[0]["label"], "insufficient")


class PipelineTests(unittest.TestCase):
    def test_paired_ba_loads_resources_once_and_verifies_without_another_search(self):
        r = retriever()
        r.search = Mock(wraps=r.search)
        client = QueueClient([draft(), draft(), {"verdicts": [verdict()]}])
        retriever_factory, client_factory = Mock(return_value=r), Mock(return_value=client)
        a, b, c = Pipeline(retriever_factory, client_factory, CONFIG).run_paired("q", ["3.11"], order="BA")
        retriever_factory.assert_called_once_with()
        client_factory.assert_called_once_with()
        self.assertEqual(r.search.call_count, 2)
        self.assertEqual([record["mode"] for record in (a, b, c)], list("ABC"))
        self.assertEqual(client.calls[2]["payload"]["evidence"], client.calls[0]["payload"]["evidence"])
        self.assertEqual(client.calls[2]["payload"]["claims"], b["draft_claims"])
        self.assertEqual(b["evidence"], c["evidence"])

    def test_paired_reuses_b_exactly_and_accounts_cost(self):
        client = QueueClient([draft(), draft(), {"verdicts": [verdict()]}])
        pipe = Pipeline(retriever(), client, CONFIG)
        a, b, c = pipe.run_paired("q", ["3.11"])
        self.assertEqual([x["status"] for x in (a, b, c)], ["answer"] * 3)
        self.assertEqual([x["purpose"] for x in client.calls], ["generate", "generate", "verify"])
        self.assertEqual(client.calls[0]["system"], client.calls[1]["system"])
        self.assertEqual(client.calls[2]["payload"]["claims"], b["draft_claims"])
        self.assertEqual(b["evidence"], c["evidence"])
        self.assertEqual(c["paired_b_run_id"], b["run_id"])
        self.assertEqual(c["usage"]["calls"], 2)
        self.assertEqual(c["usage"]["total_tokens"], b["usage"]["total_tokens"] + 18)
        self.assertGreaterEqual(c["latency_ms"], b["latency_ms"])
        self.assertEqual(b["verification"], [])

    def test_c_abstains_and_keeps_draft(self):
        client = QueueClient([draft(), {"verdicts": [verdict(label="insufficient")]}])
        c = Pipeline(retriever(), client, CONFIG).run("q", ["3.11"], "C")
        self.assertEqual(c["status"], "insufficient_evidence")
        self.assertEqual(c["claims"], [])
        self.assertEqual(c["citations"], [])
        self.assertEqual(len(c["draft_claims"]), 1)

    def test_malformed_verifier_error_not_abstention(self):
        client = QueueClient([draft(), {"verdicts": []}])
        c = Pipeline(retriever(), client, CONFIG).run("q", ["3.11"], "C")
        self.assertEqual(c["status"], "error")
        self.assertEqual(c["usage"]["calls"], 2)

    def test_api_error_is_error(self):
        usage = dict(empty_usage(), calls=2, usage_complete=False)
        client = QueueClient([LLMError("Synthetic timeout", usage)])
        b = Pipeline(retriever(), client, CONFIG).run("q", ["3.11"], "B")
        self.assertEqual(b["status"], "error")
        self.assertEqual(b["usage"]["calls"], 2)
        self.assertFalse(b["usage"]["usage_complete"])

    def test_b_nonanswer_does_not_call_verifier(self):
        client = QueueClient([{"status": "insufficient_evidence", "claims": []}])
        c = Pipeline(retriever(), client, CONFIG).run("q", ["3.11"], "C")
        self.assertEqual(c["status"], "insufficient_evidence")
        self.assertEqual(len(client.calls), 1)

    def test_no_evidence_not_nonexistence(self):
        client = QueueClient([])
        c = Pipeline(retriever(), client, CONFIG).run("q", ["3.10"], "C")
        self.assertEqual(c["status"], "insufficient_evidence")
        self.assertEqual(len(client.calls), 0)
        self.assertNotIn("không tồn tại", c["answer"])

    def test_clarification_without_loading_anything(self):
        def forbidden():
            raise AssertionError("Must not initialize")
        pipe = Pipeline(forbidden, forbidden, CONFIG)
        for mode in "ABC":
            self.assertEqual(pipe.run("q", [], mode)["status"], "clarify")

    def test_citations_from_metadata(self):
        b = Pipeline(retriever(), QueueClient([draft()]), CONFIG).run("q", ["3.11"], "B")
        self.assertEqual(b["citations"][0]["url"], chunk()["url"])

    def test_log_redacts_key(self):
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"GEMINI_API_KEY": "synthetic_secret_key"}):
            path = Path(td) / "log.jsonl"
            pipe = Pipeline(None, None, CONFIG, path)
            record = pipe.run("synthetic_secret_key", [], "B")
            self.assertNotIn("synthetic_secret_key", path.read_text(encoding="utf-8"))
            self.assertNotIn("synthetic_secret_key", json.dumps(record))
            self.assertEqual(len(read_jsonl(path)), 1)


if __name__ == "__main__":
    unittest.main()
