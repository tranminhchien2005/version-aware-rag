"""Small, dependency-free helpers shared by the application and tests."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = ("3.10", "3.11")
STATUSES = ("answer", "clarify", "insufficient_evidence", "out_of_scope", "error")


class DataError(ValueError):
    """Invalid input, data or model output, not missing semantic evidence."""


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    if not isinstance(value, bytes):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def file_hash(path):
    return digest(Path(path).read_bytes())


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def read_jsonl(path):
    rows = []
    for line_no, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        if line.strip():
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise DataError("{}:{}: JSON không hợp lệ".format(path, line_no)) from exc
            if not isinstance(row, dict):
                raise DataError("{}:{}: mỗi dòng phải là object".format(path, line_no))
            rows.append(row)
    return rows


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    temporary.replace(path)


def append_jsonl(path, row):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(redact(row), ensure_ascii=False) + "\n")


def redact(value):
    """Redact configured keys even if an exception/provider echoed one."""
    secrets = [os.environ.get(name, "") for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY")]
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                value = value.replace(secret, "[REDACTED]")
        return value
    if isinstance(value, list):
        return [redact(x) for x in value]
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if k.lower() in {"api_key", "authorization"} else redact(v)) for k, v in value.items()}
    return value


def load_config(root=ROOT):
    config = read_json(Path(root) / "config.json")
    if config.get("supported_versions") != list(VERSIONS):
        raise DataError("Bản này chỉ hỗ trợ Python 3.10 và 3.11")
    if config.get("top_k") != 5:
        raise DataError("Thực nghiệm ban đầu cố định top_k=5")
    for name in ("chunk_tokens", "context_tokens_single", "context_tokens_compare", "llm_max_output_tokens"):
        if type(config.get(name)) is not int or config[name] <= 0:
            raise DataError("Cấu hình không hợp lệ: " + name)
    return config


def load_environment(root=ROOT):
    # Lazy optional import keeps offline core tests independent of live libraries.
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(Path(root) / ".env", override=False)


def empty_usage():
    return {"input_tokens": 0, "output_tokens": 0, "thought_tokens": 0,
            "total_tokens": 0, "calls": 0, "usage_complete": True}


def add_usage(left_usage, right_usage):
    result = {k: left_usage.get(k, 0) + right_usage.get(k, 0) for k in empty_usage() if k != "usage_complete"}
    result["usage_complete"] = left_usage.get("usage_complete", True) and right_usage.get("usage_complete", True)
    return result
