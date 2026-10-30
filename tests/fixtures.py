"""Synthetic inputs and test doubles; never factual Python evidence."""
import copy

import numpy as np

from src.llm_client import LLMReply
from src.retrieve import Retriever

CONFIG = {"embedding_model": "SYNTHETIC_TEST_ONLY", "embedding_revision": None, "embedding_device": "cpu",
          "chunk_tokens": 100, "context_tokens_single": 10000, "context_tokens_compare": 20000,
          "top_k": 5, "llm_max_output_tokens": 100, "llm_temperature": None,
          "supported_versions": ["3.10", "3.11"]}


def chunk(cid="d311", version="3.11", history=False):
    result = {"chunk_id": cid, "source_id": "synthetic_fixture", "source_version": version,
              "module": "synthetic", "section": "Synthetic fixture, not real Python documentation",
              "url": "https://docs.python.org/" + version + "/library/asyncio-task.html",
              "evidence_role": "history_note" if history else "ordinary", "history_targets": [],
              "text": "SYNTHETIC TEST DATA ONLY. Example property for testing control flow."}
    if history:
        result.update(history_targets=["3.10", "3.11"], review_status="human_reviewed",
                      reviewer="TEST_FIXTURE_NOT_A_REAL_REVIEW", reviewed_at="TEST_ONLY")
    return result


class FakeEmbedder:
    """Not an embedding model; fixed vectors allow deterministic ranking tests."""
    max_seq_length = 128
    identity = {"name": "SYNTHETIC_TEST_ONLY"}

    def token_count(self, text):
        return len(text.split()) + 2

    def encode(self, texts):
        return np.asarray([[1., 0.] for _ in texts], dtype=np.float32)


def retriever(chunks=None, vectors=None):
    chunks = chunks if chunks is not None else [chunk()]
    vectors = np.array(vectors if vectors is not None else [[1., 0.] for c in chunks])
    meta = {"chunk_ids": [c["chunk_id"] for c in chunks], "shape": list(vectors.shape), "corpus_version": "synthetic"}
    return Retriever(chunks, vectors, FakeEmbedder(), meta, CONFIG)


def draft(cid="d311", version="3.11"):
    return {"status": "answer", "claims": [{"text": "Nhận định giả lập để kiểm thử luồng chương trình.",
             "applies_to": [version], "evidence_ids": [cid]}]}


def verdict(cid="c1", label="supported", eid="d311"):
    return {"claim_id": cid, "label": label, "evidence_ids": [eid], "reason": "Synthetic verdict for control-flow testing only."}


class QueueClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, system, payload, schema, purpose):
        self.calls.append({"purpose": purpose, "system": system, "payload": copy.deepcopy(payload)})
        if not self.responses:
            raise AssertionError("Unexpected additional LLM call")
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return LLMReply(copy.deepcopy(value), {"input_tokens": 11, "output_tokens": 7, "thought_tokens": 0,
                         "total_tokens": 18, "calls": 1, "usage_complete": True}, "SYNTHETIC_LLM_TEST_DOUBLE")
