"""Package source/data for handover, excluding secrets, runtimes and caches."""
import os
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from src.common import ROOT, DataError, load_environment


def main():
    load_environment()
    target = ROOT.parent / "rag_phien_ban_ban_giao.zip"
    allowed_roots = {"src", "scripts", "tests", "notes", "data", "results", ".streamlit"}
    allowed_files = {"README.md", "config.json", "requirements.txt", "requirements.lock.txt", "setup.ps1", "run_app.cmd", "app.py", ".gitignore", ".env.example"}
    secrets = [os.environ.get(k, "").encode("utf-8") for k in ("GEMINI_API_KEY", "GOOGLE_API_KEY") if os.environ.get(k)]
    selected = []
    for folder, directories, names in os.walk(ROOT):
        relative = Path(folder).relative_to(ROOT)
        directories[:] = [d for d in directories if d not in {".venv", ".cache", ".git", "__pycache__"}
                          and not (relative == Path("results") and d in {"runs", "frozen"})
                          and (relative != Path(".") or d in allowed_roots)]
        for name in names:
            path = Path(folder) / name
            rel = path.relative_to(ROOT)
            if relative == Path(".") and name not in allowed_files:
                continue
            if name == "secrets.toml" or name == ".env" or name.endswith((".pyc", ".pyo", ".tmp")):
                continue
            if any(secret in path.read_bytes() for secret in secrets):
                raise DataError("Phát hiện khóa trong file được đóng gói; kiểm tra tại máy trước khi bàn giao")
            selected.append((path, ROOT.name + "/" + rel.as_posix()))
    with ZipFile(target, "w", compression=ZIP_DEFLATED) as archive:
        for path, name in selected:
            archive.write(path, name)
    with ZipFile(target) as archive:
        if archive.testzip() is not None or any(name.endswith("/.env") or "/.venv/" in name or "/.cache/" in name for name in archive.namelist()):
            raise DataError("Gói bàn giao không hợp lệ")
    print("Đã tạo {} ({} file, {} byte), không gồm .env, môi trường hoặc cache.".format(target, len(selected), target.stat().st_size))


if __name__ == "__main__":
    main()
