"""Local integration tests need installed libraries but never call a live LLM."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.common import DataError, ROOT, file_hash, read_jsonl, write_json, write_jsonl
from src.retrieve import Retriever, build_index
from src.runtime import make_pipeline
from tests.fixtures import CONFIG, FakeEmbedder, chunk


class IndexIntegrityTests(unittest.TestCase):
    def build(self, root):
        write_jsonl(root / "data/chunks.jsonl", [chunk("one"), chunk("two")])
        write_json(root / "data/chunk_meta.json", {"embedding": FakeEmbedder.identity,
                   "chunks_sha256": file_hash(root / "data/chunks.jsonl")})
        build_index(root, FakeEmbedder())

    def test_round_trip_and_changed_chunk_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.build(root)
            loaded = Retriever.load(root, FakeEmbedder(), CONFIG)
            self.assertEqual(len(loaded.chunks), 2)
            write_jsonl(root / "data/chunks.jsonl", [chunk("two"), chunk("one")])
            with self.assertRaises(DataError):
                Retriever.load(root, FakeEmbedder(), CONFIG)

    def test_changed_vector_file_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.build(root)
            with (root / "data/index/vectors.npy").open("ab") as stream:
                stream.write(b"changed")
            with self.assertRaises(DataError):
                Retriever.load(root, FakeEmbedder(), CONFIG)


@unittest.skipUnless(importlib.util.find_spec("streamlit"), "Streamlit chưa được cài")
class StreamlitFormTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.log_path = Path(temporary.name) / "application.jsonl"
        factory = patch("src.runtime.make_pipeline", side_effect=lambda **kwargs:
                        make_pipeline(log_path=self.log_path, **kwargs))
        factory.start()
        self.addCleanup(factory.stop)

    def test_missing_version_form_runs_without_api_or_embedding(self):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
        self.assertEqual(len(app.exception), 0)
        app.text_area[0].input("Hướng dẫn dùng asyncio.TaskGroup")
        app.checkbox[0].check()
        app.button[0].click().run()
        self.assertEqual(len(app.exception), 0)
        rows = app.session_state["records"]
        self.assertEqual([r["mode"] for r in rows], list("ABC"))
        self.assertTrue(all(r["status"] == "clarify" for r in rows))
        self.assertTrue(all(r["usage"]["calls"] == 0 for r in rows))
        self.assertEqual(len(read_jsonl(self.log_path)), 3)


@unittest.skipUnless(importlib.util.find_spec("bs4"), "BeautifulSoup chưa được cài")
class ChunkHistoryTests(unittest.TestCase):
    def prepare_reviewed_note(self, root, text):
        from src.chunk import build_chunks
        raw = root / "data/raw/fixture.html"
        raw.parent.mkdir(parents=True)
        raw.write_text('<main><section id="fixture"><h1>Fixture</h1>'
                       '<div class="versionadded"><p><span class="versionmodified">'
                       + text + '</span></p></div></section></main>', encoding="utf-8")
        write_json(root / "data/manifest.json", [{
            "source_id": "synthetic", "source_version": "3.11", "module": "synthetic",
            "final_url": "https://docs.python.org/3.11/library/asyncio-task.html",
            "local_path": "data/raw/fixture.html", "sha256": file_hash(raw)}])
        write_json(root / "data/history_reviews.json", [])
        embedder = FakeEmbedder()
        embedder.max_seq_length = 4096
        build_chunks(root, embedder, CONFIG)
        candidate = read_jsonl(root / "data/history_candidates.jsonl")[0]
        write_json(root / "data/history_reviews.json", [dict(
            candidate, history_targets=["3.10", "3.11"], review_status="human_reviewed",
            reviewer="TEST_FIXTURE_NOT_A_REAL_REVIEW", reviewed_at="TEST_ONLY")])
        return candidate

    def test_reviewed_note_keeps_identity_provenance_and_token_count(self):
        from src.chunk import build_chunks
        from src.version_policy import eligible
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = self.prepare_reviewed_note(root, "New in version 3.11: synthetic.fn.")
            chunks = build_chunks(root, FakeEmbedder(), CONFIG)
            history = next(item for item in chunks if item["evidence_role"] == "history_note")
            ordinary_note = next(item for item in chunks if item.get("atomic_version_note"))
            self.assertEqual(history["chunk_id"], candidate["candidate_id"])
            self.assertEqual(history["text"], candidate["text"])
            self.assertEqual(history["source_sha256"], candidate["source_sha256"])
            self.assertEqual(history["token_count"], ordinary_note["token_count"])
            self.assertTrue(eligible(history, "3.10"))

    def test_review_does_not_allow_note_over_embedding_window(self):
        from src.chunk import build_chunks
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.prepare_reviewed_note(root, "New in version 3.11: " + "synthetic " * 150)
            previous_chunks = (root / "data/chunks.jsonl").read_bytes()
            with self.assertRaises(DataError):
                build_chunks(root, FakeEmbedder(), CONFIG)
            self.assertEqual((root / "data/chunks.jsonl").read_bytes(), previous_chunks)


@unittest.skipUnless(importlib.util.find_spec("bs4"), "BeautifulSoup chưa được cài")
class HtmlNestedCodeTests(unittest.TestCase):
    def test_code_inside_list_keeps_indentation(self):
        from src.chunk import extract_units
        html = b'<main><section id="unit"><h1>Fixture</h1><ul><li><p>Code:</p><pre>def f():\n    return 1\n</pre></li></ul></section></main>'
        text = "\n".join("\n".join(u["blocks"]) for u in extract_units(html, {"module": "fixture"}))
        self.assertIn("def f():\n    return 1", text)
        self.assertEqual(text.count("return 1"), 1)

    def test_version_note_inside_list_excludes_surrounding_example(self):
        from src.chunk import extract_units
        html = b'<main><section id="unit"><h1>Fixture</h1><ul><li><p>Example:</p><pre>print(42)</pre><div class="versionadded"><p><span class="versionmodified">New in version 3.11:</span> synthetic.fn.</p></div></li></ul></section></main>'
        units = extract_units(html, {"module": "fixture"})
        notes = [n for u in units for n in u["notes"]]
        self.assertEqual(len(notes), 1)
        self.assertNotIn("print", notes[0])
        self.assertIn("synthetic.fn", notes[0])

    def test_inline_signature_preserves_api_name(self):
        from src.chunk import extract_units
        html = b'<main><section id="unit"><dl class="py function"><dt id="f"><span>asyncio.</span><span>sleep</span>(delay)</dt><dd><p>Example.</p></dd></dl></section></main>'
        unit = extract_units(html, {"module": "asyncio"})[0]
        self.assertEqual(unit["section"], "asyncio.sleep(delay)")


if __name__ == "__main__":
    unittest.main()
