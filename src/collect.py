"""Download version-pinned Python pages; preserve original bytes and provenance."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from .common import ROOT, DataError, digest, file_hash, read_json, utc_now, write_json
from .version_policy import valid_source_url


def inspect_html(content, version):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(content, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    if not re.search(r"Python\s+" + re.escape(version) + r"(?:\.|\s)", title):
        raise DataError("Tiêu đề HTML không xác nhận đúng phiên bản Python")
    main = soup.select_one('div.body[role="main"]') or soup.select_one("main")
    if main is None or len(main.get_text(strip=True)) < 80:
        raise DataError("Không thấy nội dung chính hợp lệ")
    return title


def validate_response(response, version):
    response.raise_for_status()
    if not valid_source_url(response.url, version):
        raise DataError("Trang đã chuyển hướng sang miền/phiên bản khác")
    if "text/html" not in response.headers.get("Content-Type", "").lower():
        raise DataError("Nguồn không phải HTML")
    return inspect_html(response.content, version)


def collect(sources, root=ROOT, refresh=False, session=None):
    import requests
    root = Path(root)
    manifest_path = root / "data/manifest.json"
    previous_manifest = read_json(manifest_path) if manifest_path.exists() else []
    manifest_by_source = {source_entry["source_id"]: source_entry for source_entry in previous_manifest}
    session = session or requests.Session()
    errors, seen_source_ids = [], set()
    for source_spec in sources:
        source_id, version, url = source_spec["source_id"], source_spec["source_version"], source_spec["url"]
        if not re.fullmatch(r"[A-Za-z0-9_\-]+", source_id) or source_id in seen_source_ids:
            raise DataError("source_id trùng hoặc không hợp lệ")
        seen_source_ids.add(source_id)
        if not valid_source_url(url, version) or version not in ("3.10", "3.11"):
            raise DataError("Chỉ chấp nhận docs.python.org/3.10/ hoặc /3.11/")
        previous_source = manifest_by_source.get(source_id)
        if previous_source and not refresh:
            if previous_source["url"] != url or previous_source["source_version"] != version or previous_source["module"] != source_spec["module"]:
                raise DataError("source_id đã được dùng với nguồn khác")
            if file_hash(root / previous_source["local_path"]) != previous_source["sha256"]:
                raise DataError("HTML đã đổi; khôi phục bản gốc hoặc thu thập lại có chủ đích")
            continue
        try:
            response = session.get(url, timeout=(10, 40), headers={"User-Agent": "VersionRAG-Student/1.0 (educational snapshot)"})
            title = validate_response(response, version)
            source_sha256 = digest(response.content)
            local_path = Path("data/raw") / (source_id + "_" + source_sha256[:12] + ".html")
            (root / local_path).parent.mkdir(parents=True, exist_ok=True)
            (root / local_path).write_bytes(response.content)
            manifest_by_source[source_id] = dict(source_spec, final_url=response.url, title=title, retrieved_at=utc_now(),
                               sha256=source_sha256, local_path=local_path.as_posix())
        except Exception as exc:
            errors.append({"source_id": source_id, "url": url, "error_type": type(exc).__name__, "message": str(exc), "at": utc_now()})
    write_json(root / "results/collect_errors.json", errors)
    if errors:
        # No partial manifest: cached original files are kept, but no failed page
        # or mixed new/old snapshot is silently published as a new corpus.
        raise DataError("{} trang lỗi; xem results/collect_errors.json. Manifest cũ được giữ nguyên.".format(len(errors)))
    result = sorted(manifest_by_source.values(), key=lambda source_entry: source_entry["source_id"])
    write_json(manifest_path, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", default="data/sources.json")
    parser.add_argument("--refresh", action="store_true", help="Tải snapshot mới có chủ đích; không dùng giữa thực nghiệm")
    args = parser.parse_args()
    pages = collect(read_json(ROOT / args.sources), refresh=args.refresh)
    print("Đã lưu manifest: {} trang hợp lệ".format(len(pages)))


if __name__ == "__main__":
    main()
