"""Actual model tokenizer determines every index input length."""
from __future__ import annotations

import os

from .common import ROOT, DataError, digest


class SentenceEmbedder:
    def __init__(self, config, allow_download=False):
        os.environ.setdefault("HF_HOME", str(ROOT / ".cache/huggingface"))
        # Standard HTTPS avoids the optional native Xet transfer backend hanging
        # on some Windows setups. Existing user choices still take precedence.
        os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
        os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "60")
        from sentence_transformers import SentenceTransformer
        self.name = config["embedding_model"]
        try:
            self.model = SentenceTransformer(self.name, revision=config.get("embedding_revision"),
                                             device=config.get("embedding_device", "cpu"), trust_remote_code=False,
                                             local_files_only=not allow_download)
        except OSError as exc:
            if not allow_download:
                raise DataError("Chưa có đủ model embedding trong cache. Chạy src.chunk khi có mạng để tải model.") from exc
            raise
        self.tokenizer = self.model.tokenizer
        self.max_seq_length = int(self.model.max_seq_length)
        self.revision = getattr(self.model[0].auto_model.config, "_commit_hash", None) or config.get("embedding_revision")
        tokenizer_hash = digest(self.tokenizer.backend_tokenizer.to_str()) if getattr(self.tokenizer, "is_fast", False) else digest(self.tokenizer.get_vocab())
        self.identity = {"name": self.name, "revision": self.revision,
                         "max_seq_length": self.max_seq_length, "tokenizer_sha256": tokenizer_hash}

    def token_count(self, text):
        return len(self.tokenizer.encode(text, add_special_tokens=True, truncation=False, verbose=False))

    def encode(self, texts):
        if any(self.token_count(text) > self.max_seq_length for text in texts):
            raise DataError("Đầu vào vượt max_seq_length; không cho phép cắt âm thầm")
        return self.model.encode(texts, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
