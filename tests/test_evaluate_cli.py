"""Protect evaluation CLI option names without calling an LLM or using real gold."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.common import ROOT, read_json, read_jsonl, write_jsonl
from src.pipeline import Pipeline
from tests.fixtures import CONFIG


class EvaluationCliTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        question_id = "cli_fixture_not_experimental_data"
        question = {"question_id": question_id, "question": "Hướng dẫn dùng API",
                    "requested_versions": [], "group_id": "cli_fixture", "split": "dev",
                    "expected_action": "clarify", "gold_claims": [], "acceptable_evidence_sets": [],
                    "review_status": "human_reviewed", "reviewer": "TEST_FIXTURE_NOT_A_REAL_REVIEW",
                    "reviewed_at": "TEST_ONLY", "rationale": "Synthetic fixture for CLI option tests."}
        records = Pipeline(None, None, CONFIG).run_paired(question["question"], [], question_id)
        self.runs = self.folder / "runs.jsonl"
        self.questions = self.folder / "questions.jsonl"
        self.reviews = self.folder / "reviews.jsonl"
        write_jsonl(self.runs, records)
        write_jsonl(self.questions, [question])
        write_jsonl(self.reviews, [])

    def run_cli(self, command, *options):
        result = subprocess.run([sys.executable, "-m", "scripts.evaluate", command, *map(str, options)],
                                cwd=ROOT, capture_output=True, encoding="utf-8", timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_review_template_accepts_runs_and_questions_options(self):
        target = self.folder / "review_template.jsonl"
        self.run_cli("review-template", "--runs", self.runs, "--questions", self.questions, "--out", target)
        reviews = read_jsonl(target)
        self.assertEqual([review["mode"] for review in reviews], list("ABC"))
        self.assertTrue(all(review["system_status"] == "clarify" for review in reviews))

    def test_summarize_accepts_runs_questions_and_reviews_options(self):
        target = self.folder / "metrics.json"
        self.run_cli("summarize", "--runs", self.runs, "--questions", self.questions,
                     "--reviews", self.reviews, "--out", target)
        metrics = read_json(target)
        self.assertTrue(target.with_suffix(".md").is_file())
        self.assertEqual(set(metrics), {"all", "cli_fixture"})
        for mode in "ABC":
            self.assertEqual(metrics["all"][mode]["requests"], 1)
            self.assertEqual(metrics["all"][mode]["action_accuracy"]["value"], 1)


if __name__ == "__main__":
    unittest.main()
