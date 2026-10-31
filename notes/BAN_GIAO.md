# Biên bản triển khai và kiểm tra

Ngày cập nhật: 21/10/2026. Dự án: `D:\LLM\rag_phien_ban`.

Các lượt rà soát sau bàn giao ngày 22/10/2026, gồm bổ sung tên biến, đã hoàn thành với 70 kiểm thử đạt; xem [báo cáo refactor](REFACTOR.md). Các kết quả và số liệu bên dưới là biên bản của lượt bàn giao ban đầu.

## Phạm vi và phần đã triển khai

| Chặng | File chính | Mục đích |
|---|---|---|
| Dựng dự án | config.json, requirements.txt, .env.example, setup.ps1 | Môi trường và cấu hình khóa cục bộ |
| Thu thập | src/collect.py, data/sources.json | Kiểm tra nguồn 3.10/3.11 và lưu HTML/manifest |
| Chia đoạn | src/chunk.py, scripts/review_history.py | Đơn vị ngữ nghĩa, giữ code, ứng viên ghi chú lịch sử |
| Truy xuất | src/embedding.py, src/retrieve.py | Tokenizer thật, vector chuẩn hóa, mapping ID và lọc trước top-k |
| A và B | src/generate.py, src/version_policy.py | Prompt chung, schema claim, chính sách phiên bản |
| C | src/verify.py, src/pipeline.py | Kiểm chứng đúng bản nháp B, lưu quyết định và tính đủ chi phí |
| Giao diện | app.py, run_app.cmd, scripts/ask.py | Tra cứu tiếng Việt qua UI hoặc CLI |
| Đánh giá | src/evaluation.py, scripts/evaluate.py | Đóng băng, chạy cặp, chấm thủ công, tử số/mẫu số |
| Học và báo cáo | README.md và notes | Hướng dẫn PowerShell, giải thích mã, chấm điểm, khung báo cáo |

## Kiểm tra đã thực hiện trước khi cài môi trường đầy đủ

Đã chạy kiểm thử lõi ban đầu trên Python 3.8.10, sau đó cài Python **3.11.17** riêng trong workspace và môi trường đầy đủ tại `.venv`. Demo xác nhận C dùng lại bản nháp B và cộng usage của B; demo dùng dữ liệu và LLM giả lập, không đo chất lượng trả lời kỹ thuật.

Các ca kiểm thử kiểm tra lọc trước top-k, ordinary/history_note, so sánh hai bản, mâu thuẫn đầu vào, thiếu bằng chứng, mapping vector, dẫn nguồn lạ, verifier thiếu/trùng verdict, lỗi schema/API, retry giới hạn, dấu hiệu usage thiếu, rò rỉ group dev/test và các chỉ số tính tay. Lượt cuối: **64 ca, 0 lỗi, 0 thất bại, 0 skip**; xem `results/software_tests.json` và `results/test-output.txt`.

## Kiểm tra tích hợp hiện tại

| Kiểm tra | Kết quả đã quan sát |
|---|---|
| Cài phụ thuộc | 87 package; pip check không phát hiện xung đột; requirements.lock.txt lưu phiên bản thật |
| Thu thập | 3 trang thật, HTTP/URL/phiên bản và SHA256 hợp lệ |
| Trích nội dung | 80 đơn vị nội dung; đã sửa việc gộp ghi chú với ví dụ trong list và giữ tên API liền nhau |
| Chia đoạn | 368 chunk; dài nhất 100 token; giới hạn model 128 token |
| Embedding | MiniLM đa ngôn ngữ, vector 384 chiều; revision được cố định trong config |
| Chỉ mục | Đã tạo vectors.npy và mapping ID; kiểm tra hash và chuẩn hóa vector |
| Tìm kiếm | 6 lượt A/B trên 3 tình huống; B không có nguồn ngoài chính sách phiên bản |
| SDK | Google GenAI 2.32.0 chấp nhận cấu hình client/schema; tắt automatic continuation để giữ giới hạn lượt gọi |
| Giao diện | Streamlit 1.66.0; AppTest kiểm tra nhập câu hỏi, chọn so sánh và nhánh hỏi lại |
| Server local | Đã khởi động tại 127.0.0.1:8501; health và trang chủ trả HTTP 200 |
| Browser | Không có Browser kết nối trong phiên, chưa kiểm tra giao diện bằng ảnh chụp Browser |

Chi tiết dữ liệu và các lượt tìm kiếm nằm trong `results/data_checks.json`. Các bước này không đo độ chính xác của câu trả lời LLM.

## Kết quả gọi Gemini thật

Đã dùng khóa cấu hình cục bộ, không hiển thị hoặc đóng gói khóa. Model của lượt thành công mới nhất là `gemini-3.5-flash-lite`. Đã chạy mới A/B/C cùng model này, thay vì dùng lại bản nháp B từ model trước.

Đã chạy câu phát triển “tomllib trong Python 3.11 có ghi được file TOML không?”. Ban đầu A/B trả insufficient_evidence vì ngân sách 1.000 token loại đoạn xếp thứ 5, chứa câu phủ định; toàn bộ năm đoạn dài 1.057 token. Đã tăng ngân sách chung lên 1.500 token cho một phiên bản và 3.000 khi so sánh, giữ giới hạn 5/10 đoạn và cùng cách xếp hạng/prompt giữa A/B.

Sau điều chỉnh và với cấu hình model hiện tại, cả A, B và C đều trả `answer` có nguồn xác nhận tomllib trong Python 3.11 không hỗ trợ ghi TOML. C dùng nguyên bản nháp/bằng chứng B và nhận verdict `supported`. Đã đối chiếu paired_b_run_id, nội dung claim, bằng chứng và mã băm bản nháp để xác nhận B/C dùng cùng dữ liệu.

Log thật ở `results/live_smoke.json`; trace ở `results/runs/live_smoke_trace.jsonl` giữ cả các lượt lỗi trước đó. Lượt mới không có lỗi API/schema, usage đầy đủ: A 1.227 token, B 1.227 token, C 2.459 token đã gồm bước B và kiểm chứng. C ghi hai lượt gọi logic (sinh B và kiểm chứng); khi chạy cặp thực tế chỉ phát sinh thêm một request kiểm chứng so với B. Đây là kiểm tra tích hợp một câu phát triển, chưa phải thực nghiệm chất lượng.

Luồng sinh và kiểm chứng thật đã chạy thành công trên câu thử này. Có thể dùng `scripts.check_llm --retry-verification` trong giai đoạn phát triển để kiểm chứng đúng B đã lưu khi model/corpus không đổi. Trong đánh giá test độc lập, giữ nguyên chính sách retry đã đóng băng và báo lỗi dịch vụ, không thử lại có chọn lọc để bỏ các kết quả lỗi. Các lỗi quyền/quá tải trước đây không được xóa khỏi trace hoặc coi là lượt thành công.

## Dữ liệu và kết quả chưa có

12 câu dev là đề xuất AI, chưa được người rà soát, chưa phải gold. Tập test còn trống. Không có kết quả so sánh chất lượng A/B/C hoặc chi phí API thực tế. Mọi bảng báo cáo đang ghi Chưa chạy/Chưa đo.

Cần người học mở nguồn và duyệt history_note, rà soát câu hỏi/đáp án, gắn ID bằng chứng và chuẩn bị test độc lập. Đã tạo 67 ghi chú và nguồn gợi ý cho 12 câu để hỗ trợ rà soát; chưa tự coi chúng là gold. Sinh và kiểm chứng thật đã hoạt động trên câu phát triển, chưa đánh giá chất lượng trên tập test độc lập. Không gửi khóa vào cuộc trò chuyện.

## Lệnh tiếp theo

Lệnh dùng PowerShell, chạy từ `D:\LLM\rag_phien_ban`. Các bước đầy đủ, sản phẩm từng bước và cách xử lý lỗi ở README.md.

```powershell
.\.venv\Scripts\python.exe -m scripts.check_environment
.\.venv\Scripts\python.exe -m scripts.test_project
.\.venv\Scripts\python.exe -m scripts.check_data
.\.venv\Scripts\python.exe -m scripts.check_llm
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Corpus/chỉ mục đã có sẵn nên không cần dựng lại để mở giao diện. Gói ZIP bàn giao gồm mã nguồn, dữ liệu và chỉ mục, hướng dẫn, lockfile và kết quả kiểm tra; không gồm `.env`, môi trường Python, cache model hoặc log ứng dụng riêng. Khi chuyển máy, cài lại môi trường và tải model theo README.
