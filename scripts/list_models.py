"""List Gemini model IDs available to the configured key without generating text."""
import json
import os
import sys

from src.common import ROOT, load_environment, redact, utc_now, write_json


def main():
    load_environment()
    from google import genai
    from google.genai import types
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        print("Chưa có GEMINI_API_KEY trong cấu hình trên máy.")
        return 1
    client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=30000, retry_options=types.HttpRetryOptions(attempts=1)))
    try:
        models = [{"name": m.name, "display_name": m.display_name,
                   "supported_actions": getattr(m, "supported_actions", None)} for m in client.models.list()]
    except Exception as exc:
        print("Không đọc được danh sách model: {} (mã {}).".format(type(exc).__name__, getattr(exc, "code", None)))
        return 1
    finally:
        client.close()
    write_json(ROOT / "results/available_models.json", redact({"checked_at": utc_now(), "models": models}))
    print(json.dumps(redact({"configured_model": os.environ.get("LLM_MODEL", ""), "models": models}), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
