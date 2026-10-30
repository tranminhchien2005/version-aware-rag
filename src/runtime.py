"""Lazy construction: clarification requests do not load models or require a key."""
from .common import ROOT, DataError, load_config, load_environment
from .llm_client import GeminiClient
from .pipeline import Pipeline


def make_retriever(config, root=ROOT):
    if any(not (root / name).is_file() for name in ("data/chunks.jsonl", "data/index/meta.json", "data/index/vectors.npy")):
        raise DataError("Chưa có corpus/chỉ mục. Chạy src.collect, src.chunk và src.retrieve theo README trước.")
    from .embedding import SentenceEmbedder
    from .retrieve import Retriever
    return Retriever.load(root, SentenceEmbedder(config), config)


def make_pipeline(root=ROOT, retriever_factory=None, log_path=None):
    load_environment(root)
    config = load_config(root)
    return Pipeline(retriever_factory or (lambda: make_retriever(config, root)), lambda: GeminiClient(config), config,
                    log_path=log_path or root / "results/runs/application.jsonl")
