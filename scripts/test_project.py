"""Run software tests and save actual results, separate from RAG quality metrics."""
import io
import platform
import sys
import time
import unittest

from src.common import ROOT, utc_now, write_json


def main():
    buffer = io.StringIO()
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT))
    started = time.perf_counter()
    result = unittest.TextTestRunner(stream=buffer, verbosity=2).run(suite)
    elapsed = time.perf_counter() - started
    text = buffer.getvalue()
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results/test-output.txt").write_text(text, encoding="utf-8")
    write_json(ROOT / "results/software_tests.json", {
        "kind": "software_tests_not_rag_quality_evaluation", "checked_at": utc_now(),
        "python": platform.python_version(), "tests_run": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
        "successful": result.wasSuccessful(), "elapsed_seconds": elapsed,
        "notice": "LLM transport tests use stubs; SDK configuration and local UI tests make no live LLM requests."})
    print(text)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
