"""Input policy is identical before A, B and C; it is not a gain of B."""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from .common import DataError, VERSIONS

# Exclude version-like strings attached to identifiers and normalize patch versions.
VERSION_RE = re.compile(r"(?<![\w.])(3\.10|3\.11)(?:\.\d+)?(?![\w.])")
EXPLICIT_VERSION_RE = re.compile(
    r"(?:\bpython\s*(?:v(?:ersion)?\s*)?|\bphiên\s+bản\s+|\bversion\s+)(\d+\.\d+)(?:\.\d+)?(?![\w.])", re.IGNORECASE)


def prepare(question, requested_versions, mode):
    if mode not in ("A", "B", "C"):
        raise DataError("mode phải là A, B hoặc C")
    if not isinstance(question, str) or not question.strip():
        return {"status": "clarify", "message": "Bạn muốn hỏi nội dung gì?", "versions": []}
    if len(question) > 6000:
        raise DataError("Câu hỏi quá dài (tối đa 6000 ký tự)")
    if not isinstance(requested_versions, list) or any(not isinstance(v, str) for v in requested_versions):
        raise DataError("requested_versions phải là danh sách chuỗi")
    selected = sorted(set(requested_versions))
    # Technical questions often contain decimals (TOML 1.0, sqrt(2.0)).
    # Recognize unsupported versions only when explicitly marked as versions.
    mentioned = sorted(set(VERSION_RE.findall(question) + EXPLICIT_VERSION_RE.findall(question)))
    if any(v not in VERSIONS for v in selected + mentioned):
        return {"status": "out_of_scope", "message": "Hiện chỉ hỗ trợ tài liệu Python 3.10 và 3.11.", "versions": selected}
    if mentioned and selected and mentioned != selected:
        return {"status": "clarify", "message": "Phiên bản trong câu hỏi khác lựa chọn. Hãy xác nhận lại phiên bản hoặc chọn so sánh hai bản.", "versions": selected}
    versions = selected or mentioned
    if not versions:
        return {"status": "clarify", "message": "Bạn đang hỏi Python 3.10 hay 3.11?", "versions": []}
    return {"status": "ready", "message": "", "versions": versions}


def valid_source_url(url, version):
    try:
        parsed = urlsplit(url)
        return (parsed.scheme == "https" and parsed.hostname == "docs.python.org"
                and parsed.port in (None, 443) and not parsed.username and not parsed.password
                and parsed.path.startswith("/" + version + "/"))
    except (TypeError, ValueError):
        return False


def validate_chunk(chunk):
    required = ("chunk_id", "source_id", "source_version", "module", "section", "url", "evidence_role", "text")
    if any(not isinstance(chunk.get(k), str) or not chunk[k].strip() for k in required):
        raise DataError("Chunk thiếu metadata hoặc text: " + str(chunk.get("chunk_id")))
    version = chunk["source_version"]
    if version not in VERSIONS or not valid_source_url(chunk["url"], version):
        raise DataError("Nguồn chunk không đúng phiên bản/miền")
    targets = chunk.get("history_targets")
    if not isinstance(targets, list) or any(v not in VERSIONS for v in targets):
        raise DataError("history_targets không hợp lệ")
    if chunk["evidence_role"] == "ordinary":
        if targets:
            raise DataError("ordinary không được có history_targets")
    elif chunk["evidence_role"] == "history_note":
        if (not targets or chunk.get("review_status") != "human_reviewed"
                or not chunk.get("reviewer") or not chunk.get("reviewed_at")):
            raise DataError("history_note chưa được người rà soát")
    else:
        raise DataError("evidence_role không hợp lệ")


def eligible(chunk, version):
    if chunk.get("evidence_role") == "ordinary":
        return chunk.get("source_version") == version
    return (chunk.get("evidence_role") == "history_note"
            and chunk.get("review_status") == "human_reviewed"
            and bool(chunk.get("reviewer")) and bool(chunk.get("reviewed_at"))
            and version in chunk.get("history_targets", []))
