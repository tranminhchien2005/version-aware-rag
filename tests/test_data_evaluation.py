import importlib.util
import unittest
from types import SimpleNamespace

from src.chunk import extract_units, split_exact
from src.collect import validate_response
from src.common import DataError
from src.evaluation import ratio, summarize, validate_dataset


class SplitTests(unittest.TestCase):
    def test_preserves_every_character_and_code_indent(self):
        text = "Negative condition must not be dropped.\n\n```python\ndef f():\n    return 42\n```\nLast sentence."
        parts = split_exact(text, "subject\n", len, 55)
        self.assertEqual("".join(parts), text)
        self.assertTrue(all(len("subject\n" + x) <= 55 for x in parts))
        self.assertIn("    return 42", "".join(parts))

    def test_rejects_prefix_that_leaves_no_room(self):
        with self.assertRaises(DataError):
            split_exact("body", "too long", len, 5)


class CollectionTests(unittest.TestCase):
    def test_redirect_to_wrong_version_rejected_before_parsing(self):
        response = SimpleNamespace(url="https://docs.python.org/3.12/library/re.html", raise_for_status=lambda: None)
        with self.assertRaises(DataError):
            validate_response(response, "3.11")

    def test_non_html_rejected(self):
        response = SimpleNamespace(url="https://docs.python.org/3.11/library/re.html", raise_for_status=lambda: None,
                                   headers={"Content-Type": "application/json"})
        with self.assertRaises(DataError):
            validate_response(response, "3.11")

    def test_http_failure_rejected(self):
        def fail():
            raise RuntimeError("synthetic HTTP 404")
        with self.assertRaises(RuntimeError):
            validate_response(SimpleNamespace(raise_for_status=fail), "3.11")

    @unittest.skipUnless(importlib.util.find_spec("bs4"), "beautifulsoup4 chưa cài; chưa kiểm thử parser HTML thực tế")
    def test_html_keeps_code_signature_and_change_note(self):
        html = b'''<html><head><title>Python 3.11.9 documentation</title></head><body>
        <nav>REMOVE MENU</nav><div class="body" role="main"><section id="synthetic">
        <h1>Synthetic page</h1><dl class="py function"><dt id="synthetic.fn">synthetic.fn(x)</dt><dd>
        <p>Do not use without condition A.</p><pre>def f():\n    return 42\n</pre>
        <div class="versionadded"><p><span class="versionmodified">New in version 3.11.</span></p></div>
        </dd></dl></section></div></body></html>'''
        units = extract_units(html, {"module": "synthetic"})
        text = "\n".join("\n".join(u["blocks"]) for u in units)
        self.assertNotIn("REMOVE MENU", text)
        self.assertIn("    return 42", text)
        self.assertIn("Do not use", text)
        self.assertTrue(any(u["notes"] for u in units))


def question(qid="q1", group="g1", split="dev", action="answer"):
    return {"question_id": qid, "question": "Synthetic " + qid, "group_id": group, "split": split,
            "expected_action": action, "requested_versions": ["3.11"], "gold_claims": ["Synthetic gold"],
            "acceptable_evidence_sets": [["d311"]], "review_status": "human_reviewed",
            "reviewer": "TEST_FIXTURE", "reviewed_at": "TEST_ONLY", "rationale": "Synthetic test"}


class DatasetTests(unittest.TestCase):
    def test_group_leakage(self):
        with self.assertRaises(DataError):
            validate_dataset([question()], [question("q2", split="test")])

    def test_duplicate_question_id(self):
        with self.assertRaises(DataError):
            validate_dataset([question(), question()])

    def test_ai_proposal_cannot_be_gold(self):
        q = question()
        q["review_status"] = "needs_human_review"
        with self.assertRaises(DataError):
            validate_dataset([q])

    def test_unknown_gold_evidence(self):
        with self.assertRaises(DataError):
            validate_dataset([question()], known_ids={"other"})

    def test_unreviewed_other_split_does_not_block_dev_review(self):
        other = question("q2", group="g2", split="test")
        other["review_status"] = "needs_human_review"
        self.assertEqual(validate_dataset([question()], [other])["questions"], 1)


class MetricTests(unittest.TestCase):
    def fixture(self):
        gold = [question("q" + str(i), "g" + str(i)) for i in range(5)]
        gold[3]["expected_action"] = "clarify"
        gold[4]["expected_action"] = "insufficient_evidence"
        statuses = ["answer", "answer", "error", "clarify", "insufficient_evidence"]
        records, scores = [], []
        for i, status in enumerate(statuses):
            record = {"run_id": str(i), "question_id": "q" + str(i), "mode": "A", "status": status,
                      "claims": [{"evidence_ids": ["d311"]}] if status == "answer" else [],
                      "retrieved_ids": ["d311"] if i < 2 else [], "latency_ms": (i + 1) * 10,
                      "usage": {"input_tokens": 1, "output_tokens": 1, "thought_tokens": 0, "total_tokens": 2,
                                "calls": 1, "usage_complete": True}, "synthetic": False}
            records.append(record)
            if i < 2:
                scores.append({"run_id": str(i), "review_status": "human_reviewed", "reviewer": "TEST_FIXTURE",
                               "reviewed_at": "TEST_ONLY", "answer_correct": i == 0, "version_error": i == 1,
                               "citation_links_correct": 1 if i == 0 else 0, "citation_links_total": 1,
                               "claims_supported": 1 if i == 0 else 0, "claims_total": 1,
                               "retrieval_sufficient": None})
        return records, gold, scores

    def test_five_examples_checked_by_hand(self):
        records, gold, scores = self.fixture()
        m = summarize(records, gold, scores)["A"]
        self.assertAlmostEqual(m["accuracy_gold_answerable"]["value"], 1 / 3)
        self.assertEqual(m["accuracy_when_answered"]["value"], .5)
        self.assertEqual(m["coverage_all"]["value"], .4)
        self.assertEqual(m["version_error_rate"]["value"], .5)
        self.assertEqual(m["citation_precision"]["value"], .5)
        self.assertEqual(m["citation_completeness"]["value"], .5)
        self.assertEqual(m["action_accuracy"]["value"], .8)
        self.assertEqual(m["error_rate"]["value"], .2)
        self.assertAlmostEqual(m["retrieval_sufficient"]["value"], 2 / 3)
        self.assertEqual(m["latency_median_ms"], 30)
        self.assertEqual(m["latency_p95_ms"], 50)

    def test_zero_denominator_is_na(self):
        self.assertIsNone(ratio(0, 0)["value"])
        self.assertIsNone(summarize([], [], [])["A"]["coverage_all"]["value"])

    def test_unfinished_reviews_do_not_produce_accuracy(self):
        records, gold, scores = self.fixture()
        m = summarize(records, gold, scores[:1])["A"]
        self.assertIsNone(m["accuracy_when_answered"]["value"])
        self.assertEqual(m["accuracy_when_answered"]["pending_review"], 1)

    def test_reject_false_citation_denominator(self):
        records, gold, scores = self.fixture()
        scores[0]["citation_links_total"] = 0
        with self.assertRaises(DataError):
            summarize(records, gold, scores)

    def test_reject_synthetic_experiment(self):
        records, gold, scores = self.fixture()
        records[0]["synthetic"] = True
        with self.assertRaises(DataError):
            summarize(records, gold, scores)


if __name__ == "__main__":
    unittest.main()
