"""An explicitly synthetic execution demo, NEVER a factual answer or experiment."""
import json

from src.common import ROOT, write_json
from src.pipeline import Pipeline
from tests.fixtures import CONFIG, QueueClient, draft, retriever, verdict


def main():
    client = QueueClient([draft(), draft(), {"verdicts": [verdict()]}])
    pipeline = Pipeline(retriever(), client, CONFIG)
    records = pipeline.run_paired("Câu hỏi giả lập để kiểm tra luồng A/B/C", ["3.11"])
    for record in records:
        record["synthetic"] = True
    output = {"notice": "DỮ LIỆU VÀ LLM GIẢ LẬP. Không phải kết quả RAG/LLM thật hoặc số liệu đồ án.",
              "checks": {"abc_answer": all(record["status"] == "answer" for record in records),
                         "llm_test_double_calls": len(client.calls),
                         "b_c_share_draft": records[1]["draft_claims"] == records[2]["draft_claims"],
                         "c_includes_b_token_usage": records[2]["usage"]["total_tokens"] == 2 * records[1]["usage"]["total_tokens"]},
              "records": records}
    assert all(output["checks"][k] for k in ("abc_answer", "b_c_share_draft", "c_includes_b_token_usage"))
    assert len(client.calls) == 3
    write_json(ROOT / "results/offline_demo.json", output)
    print(output["notice"])
    print(json.dumps(output["checks"], ensure_ascii=False, indent=2))
    print("Đã lưu results/offline_demo.json")


if __name__ == "__main__":
    main()
