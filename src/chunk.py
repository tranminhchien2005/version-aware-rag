"""Semantic units, code-preserving extraction and tokenizer-bounded chunks."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from .common import ROOT, DataError, digest, file_hash, load_config, read_json, write_json, write_jsonl
from .version_policy import validate_chunk


def extract_units(content, source):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(content, "html.parser")
    main = soup.select_one('div.body[role="main"]') or soup.select_one("main")
    if main is None:
        raise DataError("Không thấy body tài liệu")
    for unwanted in main.select(".headerlink, script, style, nav"):
        unwanted.decompose()
    units = {}
    for tag in main.find_all(["p", "pre", "li", "tr", "dt"]):
        # The outer block already includes these descendants; don't duplicate them.
        if tag.find_parent(["p", "pre", "li", "tr", "dt"]) is not None:
            continue
        owner = tag.find_parent("dl", class_=re.compile(r"\bpy\b")) or tag.find_parent("section") or main
        signature = owner.find("dt", recursive=False) if owner.name == "dl" else None
        heading = owner.find(re.compile(r"^h[1-6]$"), recursive=False)
        anchor = (signature.get("id") if signature else owner.get("id")) or "introduction"
        section = re.sub(r"\s+", " ", signature.get_text("", strip=False)).strip() if signature else (heading.get_text(" ", strip=True) if heading else source["module"])
        unit = units.setdefault(anchor, {"section": section, "anchor": anchor, "blocks": [], "notes": []})
        if tag.name == "pre":
            # Never strip/normalize leading whitespace in code.
            text = "```python\n" + tag.get_text("", strip=False).rstrip("\n") + "\n```"
        elif tag.name == "dt":
            text = re.sub(r"\s+", " ", tag.get_text("", strip=False)).strip()
        elif tag.name == "tr":
            text = " | ".join(cell.get_text(" ", strip=True) for cell in tag.find_all(["th", "td"], recursive=False))
        else:
            # List items can contain complete code examples. Replace <pre> by
            # preserved text in a detached copy before flattening the prose.
            html_fragment = BeautifulSoup(str(tag), "html.parser")
            for pre in html_fragment.find_all("pre"):
                pre.replace_with("\n```python\n" + pre.get_text("", strip=False).rstrip("\n") + "\n```\n")
            text = html_fragment.get_text(" ", strip=True)
        if not text.strip():
            continue
        unit["blocks"].append(text)
        for modified in tag.select(".versionmodified"):
            # A list item may contain prose, code and a tiny version note. Only
            # that note is history evidence, never the whole surrounding example.
            note_block = modified.find_parent("p") or modified.parent
            note = note_block.get_text(" ", strip=True)
            if note not in unit["notes"]:
                unit["notes"].append(note)
    return list(units.values())


def split_exact(text, prefix, count, limit):
    """Split without deleting characters; prefer whole blocks, lines or sentences.

    All slices are exact substrings. If a single sentence/code line is too long,
    use a character boundary and mark the parent mapping for manual inspection.
    """
    remaining, parts = text, []
    if count(prefix) >= limit:
        raise DataError("Tiêu đề/ghi chú dài hơn giới hạn embedding; cần chia lại đơn vị")
    while remaining:
        if count(prefix + remaining) <= limit:
            parts.append(remaining)
            break
        lo, hi = 1, len(remaining)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if count(prefix + remaining[:mid]) <= limit:
                lo = mid
            else:
                hi = mid - 1
        cut = lo
        for pattern in (r"\n\n", r"\n", r"(?<=[.!?])\s+", r"\s+"):
            boundaries = [m.end() for m in re.finditer(pattern, remaining[:cut]) if m.end() >= cut // 2]
            if boundaries:
                cut = boundaries[-1]
                break
        if cut < 1 or count(prefix + remaining[:cut]) > limit:
            raise DataError("Không thể chia đoạn theo tokenizer")
        parts.append(remaining[:cut])
        remaining = remaining[cut:]
    if "".join(parts) != text:
        raise DataError("Chia đoạn làm mất ký tự")
    return parts


def build_chunks(root, embedder, config):
    root = Path(root)
    manifest = read_json(root / "data/manifest.json")
    if not manifest:
        raise DataError("Manifest rỗng")
    reviews = read_json(root / "data/history_reviews.json")
    reviews_by_candidate = {history_review["candidate_id"]: history_review for history_review in reviews}
    if len(reviews_by_candidate) != len(reviews):
        raise DataError("Trùng review lịch sử")
    limit = min(config["chunk_tokens"], embedder.max_seq_length)
    chunks, parents, candidates, used_reviews = [], [], [], set()
    for source in manifest:
        raw_path = root / source["local_path"]
        if file_hash(raw_path) != source["sha256"]:
            raise DataError("HTML không khớp manifest")
        for unit in extract_units(raw_path.read_bytes(), source):
            source_metadata = {k: source[k] for k in ("source_id", "source_version", "module")}
            source_metadata.update(section=unit["section"], url=source["final_url"].split("#")[0] + "#" + unit["anchor"])
            parent_text = "\n\n".join(unit["blocks"])
            parent_id = "p_" + digest([source["sha256"], unit["anchor"], parent_text])[:20]
            parents.append(dict(source_metadata, parent_id=parent_id, text=parent_text))
            # Keep each change note atomic with its subject. Repeating ALL history
            # notes of a long API (e.g. gather) can itself exceed MiniLM's window.
            # The dedicated ordinary note chunks remain searchable in both A/B.
            prefix = unit["section"] + "\n"
            notes_prefix = prefix + ("\n".join(unit["notes"]) + "\n" if unit["notes"] else "")
            if embedder.token_count(notes_prefix) < limit // 2:
                prefix = notes_prefix
            offset = 0
            for part in split_exact(parent_text, prefix, embedder.token_count, limit):
                text = prefix + part
                chunk = dict(source_metadata, chunk_id="ch_" + digest([parent_id, offset, text])[:20],
                             parent_id=parent_id, parent_start=offset, parent_end=offset + len(part),
                             evidence_role="ordinary", history_targets=[], text=text,
                             token_count=embedder.token_count(text), source_sha256=source["sha256"])
                chunks.append(chunk)
                offset += len(part)
            for note in unit["notes"]:
                text = unit["section"] + "\n" + note
                note_tokens = embedder.token_count(text)
                if note_tokens > embedder.max_seq_length:
                    raise DataError("Một ghi chú phiên bản vượt cửa sổ mô hình; cần chọn embedding dài hơn, không cắt ghi chú")
                chunks.append(dict(source_metadata, chunk_id="note_" + digest([parent_id, text])[:20],
                                   parent_id=parent_id, evidence_role="ordinary", history_targets=[], text=text,
                                   source_sha256=source["sha256"], token_count=note_tokens, atomic_version_note=True))
                candidate_id = "hist_" + digest([source["sha256"], unit["anchor"], text])[:20]
                candidate = dict(source_metadata, candidate_id=candidate_id, text=text, source_sha256=source["sha256"],
                                 history_targets=[], review_status="needs_human_review", reviewer="", reviewed_at="")
                candidates.append(candidate)
                review = reviews_by_candidate.get(candidate_id)
                if not review:
                    continue
                used_reviews.add(candidate_id)
                if review.get("review_status") != "human_reviewed":
                    continue
                if review.get("text") != text or review.get("source_sha256") != source["sha256"]:
                    raise DataError("Ghi chú đã đổi sau rà soát: " + candidate_id)
                # This is the same note text already checked above, before any
                # review is applied; reuse its validated token count.
                history = dict(source_metadata, chunk_id=candidate_id, parent_id=parent_id, evidence_role="history_note", text=text,
                               source_sha256=source["sha256"], token_count=note_tokens,
                               **{k: review.get(k) for k in ("history_targets", "review_status", "reviewer", "reviewed_at")})
                validate_chunk(history)
                chunks.append(history)
    if set(reviews_by_candidate) - used_reviews:
        raise DataError("Review tham chiếu ghi chú không còn trong snapshot; rà soát lại")
    if not chunks or len({c["chunk_id"] for c in chunks}) != len(chunks):
        raise DataError("Corpus rỗng hoặc trùng chunk_id")
    for chunk in chunks:
        validate_chunk(chunk)
    write_jsonl(root / "data/chunks.jsonl", chunks)
    write_jsonl(root / "data/parents.jsonl", parents)
    write_jsonl(root / "data/history_candidates.jsonl", candidates)
    write_json(root / "data/chunk_meta.json", {"chunks_sha256": file_hash(root / "data/chunks.jsonl"),
               "manifest_sha256": file_hash(root / "data/manifest.json"), "embedding": embedder.identity,
               "chunk_limit": limit, "history_reviews_sha256": file_hash(root / "data/history_reviews.json"),
               "chunk_count": len(chunks), "history_count": sum(c["evidence_role"] == "history_note" for c in chunks)})
    return chunks


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    from .embedding import SentenceEmbedder
    config = load_config()
    chunks = build_chunks(ROOT, SentenceEmbedder(config, allow_download=True), config)
    print("Đã tạo {} chunks; xem data/history_candidates.jsonl để rà soát.".format(len(chunks)))


if __name__ == "__main__":
    main()
