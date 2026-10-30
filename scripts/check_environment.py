"""Read-only environment checks. Never prints API key values."""
import importlib.metadata
import json
import os
import platform
import sys

from src.common import ROOT, load_environment


def inspect():
    load_environment()
    packages = {}
    for name in ("numpy", "requests", "beautifulsoup4", "sentence-transformers", "google-genai", "streamlit", "python-dotenv"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = "CHUA_CAI"
    return {"python": platform.python_version(), "python_supported": sys.version_info >= (3, 11),
            "packages": packages, "api_key_configured": bool(os.environ.get("GEMINI_API_KEY")),
            "model_id_configured": bool(os.environ.get("LLM_MODEL")),
            "corpus_exists": (ROOT / "data/chunks.jsonl").exists(),
            "index_exists": (ROOT / "data/index/meta.json").exists()}


if __name__ == "__main__":
    print(json.dumps(inspect(), ensure_ascii=False, indent=2))
