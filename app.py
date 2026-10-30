"""Vietnamese local UI. Run: python -m streamlit run app.py"""
import json

import streamlit as st

from src.common import ROOT, file_hash, load_config, redact
from src.runtime import make_pipeline, make_retriever

st.set_page_config(page_title="Hỏi đáp tài liệu Python", page_icon="📚", layout="wide")
st.title("Hỏi đáp tài liệu Python")
st.caption("Tra cứu Python 3.10 và 3.11 • Câu trả lời kèm bằng chứng gốc")


@st.cache_resource
def cached_retriever(config_json, chunks_hash, vectors_hash, meta_hash):
    # Every source of index identity is part of the cache key. Answers are not cached.
    return make_retriever(json.loads(config_json))


def get_retriever():
    return cached_retriever(json.dumps(load_config(), sort_keys=True), file_hash(ROOT / "data/chunks.jsonl"),
                            file_hash(ROOT / "data/index/vectors.npy"), file_hash(ROOT / "data/index/meta.json"))


with st.form("question_form"):
    question = st.text_area("Câu hỏi", placeholder="Ví dụ: tomllib trong Python 3.11 có ghi được file TOML không?")
    left, right = st.columns(2)
    selection = left.selectbox("Phiên bản", ["Chưa chọn", "3.10", "3.11", "So sánh 3.10 và 3.11"])
    mode_label = right.selectbox("Cách trả lời", ["B — Lọc phiên bản", "C — Lọc và kiểm chứng", "A — Kho chung"])
    compare = st.checkbox("Chạy cả A, B, C để so sánh trên cùng câu hỏi")
    submitted = st.form_submit_button("Tra cứu", type="primary")

if submitted:
    versions = [] if selection == "Chưa chọn" else (["3.10", "3.11"] if selection.startswith("So sánh") else [selection])
    mode = mode_label[0]
    pipeline = None
    try:
        pipeline = make_pipeline(retriever_factory=get_retriever)
        with st.spinner("Đang tìm bằng chứng và xử lý câu hỏi..."):
            st.session_state["records"] = pipeline.run_paired(question, versions) if compare else [pipeline.run(question, versions, mode)]
    except Exception as exc:
        st.session_state["records"] = []
        st.error("Không khởi tạo được ứng dụng: " + redact(str(exc)))
    finally:
        if pipeline is not None:
            pipeline.close()

labels = {"answer": "Có câu trả lời", "clarify": "Cần làm rõ", "insufficient_evidence": "Chưa đủ bằng chứng",
          "out_of_scope": "Ngoài phạm vi", "error": "Lỗi xử lý"}
for record in st.session_state.get("records", []):
    st.subheader("Cấu hình " + record["mode"])
    st.caption("Câu hỏi: " + record["question"] + " | Phiên bản: " + ", ".join(record["requested_versions"]))
    if record["status"] == "error":
        st.error(labels[record["status"]] + ": " + record["answer"])
        st.info(record["error"]["message"] if record.get("error") else "Kiểm tra cấu hình.")
    else:
        st.write("**" + labels[record["status"]] + "**")
        st.text(record["answer"])
    if record["mode"] == "C" and record["status"] == "answer":
        st.caption("Bộ kiểm chứng đánh giá các nhận định là có căn cứ. Hãy đối chiếu tài liệu gốc khi sử dụng.")
    for source in record["citations"]:
        with st.expander("{} · Python {} · {}".format(source["chunk_id"], source["source_version"], source["section"])):
            st.link_button("Mở tài liệu gốc", source["url"])
            st.text(source["text"])
            if source["evidence_role"] == "history_note":
                st.caption("Ghi chú lịch sử; chỉ dùng cho sự kiện đã được rà soát.")
    with st.expander("Chi tiết truy xuất và kiểm chứng"):
        st.write("Thời gian: {:.0f} ms".format(record["latency_ms"]))
        st.json({"run_id": record["run_id"], "usage": record["usage"], "verification": record["verification"],
                 "retrieval": [{"id": evidence_item["chunk_id"], "score": evidence_item["score"], "version": evidence_item["source_version"], "text": evidence_item["text"], "url": evidence_item["url"]}
                               for evidence_item in record["evidence"]]})
