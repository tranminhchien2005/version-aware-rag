# Hệ thống hỏi đáp tài liệu kỹ thuật có nhận biết phiên bản và kiểm chứng nguồn

Đồ án RAG hỏi đáp bằng tiếng Việt trên tài liệu Python 3.10 và 3.11. Dự án có ba cấu hình: A tìm trong kho chung, B lọc nguồn theo phiên bản, C kiểm chứng từng nhận định trong đúng bản nháp của B. Tên API và nội dung mã giữ nguyên. Không huấn luyện hay fine-tuning LLM.

## Trạng thái bàn giao

Đã rà soát và refactor ngày 22/10/2026, gồm lượt bổ sung tên biến: 70 kiểm thử đạt, đối chiếu trước/sau giữ nguyên đầu ra truy xuất, pipeline và 368 chunk. Xem [báo cáo refactor](notes/REFACTOR.md), `results/refactor_checks.json` và `results/naming_checks.json`. Các kết quả bàn giao dưới đây được giữ nguyên theo thời điểm chạy ban đầu.

Mã nguồn cho thu thập, chia đoạn, embedding, A/B/C, giao diện, nhật ký, đóng băng và đánh giá đã được triển khai. Xem [biên bản kiểm tra](notes/BAN_GIAO.md) để biết chính xác phần đã chạy.

Đã cài Python **3.11.17** và các thư viện trong `.venv`, kiểm tra phụ thuộc, thu thập **3 trang HTML thật**, tạo **368 chunk** và chỉ mục embedding **384 chiều**. Đã chạy kiểm tra truy xuất A/B trên dữ liệu thật, parser HTML, cấu hình SDK và biểu mẫu Streamlit. Kết quả chi tiết nằm trong `results/data_checks.json`, `results/software_tests.json` và biên bản bàn giao. Mô hình đã nằm trong cache của dự án; việc nạp chỉ mục khi hỏi không cần tải lại model.

**Đã chạy thành công cả A/B/C với Gemini thật (`gemini-3.5-flash-lite`) trên một câu phát triển. C dùng đúng bản nháp và bằng chứng B, đánh giá nhận định là supported rồi trả câu trả lời có nguồn. Chưa có số liệu chất lượng trên test độc lập.** Log mới nhất nằm trong `results/live_smoke.json`; trace giữ cả các lượt lỗi trước đó. Phản hồi LLM trong các kiểm thử phần mềm và `results/offline_demo.json` là giả lập; không dùng làm kết quả thực nghiệm. Khóa được giữ trong `.env` trên máy và không đưa vào gói bàn giao.

`data/dev.jsonl` có 12 câu phát triển do AI đề xuất, tất cả cần người rà soát và gắn bằng chứng. `data/test.jsonl` để trống có chủ đích; không có bộ test độc lập đã gán nhãn. Đề xuất 100 câu, chia 40/60 là kế hoạch mở rộng, không phải kết quả đã hoàn thành.

## 1 Cài môi trường trên Windows

Các lệnh dưới đây dùng **PowerShell**, chạy từ thư mục dự án. Cài Python 3.11 trở lên từ [python.org](https://www.python.org/downloads/windows/) nếu chưa có. Python chạy ứng dụng và hai phiên bản tài liệu được nghiên cứu là hai việc khác nhau.

Trên máy bàn giao, `.venv`, corpus và chỉ mục đã có sẵn: kiểm tra `.env`, chạy `scripts.check_environment`, rồi chuyển đến bước 6. Kết nối Gemini hiện đã sinh và kiểm chứng được câu trả lời. Các lệnh cài dưới đây dành cho môi trường mới. Để tái tạo đúng bộ thư viện đã kiểm tra, ưu tiên `requirements.lock.txt`.

```powershell
cd D:\LLM\rag_phien_ban
py -3.11 --version
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pip freeze | Set-Content -Encoding utf8 requirements.lock.txt
Copy-Item .env.example .env
```

Dùng đường dẫn `.venv\Scripts\python.exe` trực tiếp nên không cần đổi ExecutionPolicy hoặc kích hoạt môi trường. `setup.ps1` tự động hóa việc cài nếu máy cho phép chạy PowerShell script; các lệnh trực tiếp ở trên là đủ. `requirements.txt` chứa khoảng phiên bản; `requirements.lock.txt` là danh sách phiên bản thực tế đã cài và kiểm tra. Các phiên bản chính: Sentence Transformers 5.7.0, Google GenAI 2.32.0, Streamlit 1.66.0, NumPy 2.4.6 và BeautifulSoup 4.15.0.

Mở `.env` bằng trình soạn thảo trên máy. Điền `GEMINI_API_KEY` và `LLM_MODEL` có thật, được tài khoản hỗ trợ. Không gửi khóa trong chat, không đưa vào Git hoặc ảnh chụp. Lấy khóa tại [Google AI Studio](https://aistudio.google.com/apikey). Dự án không tự chọn một model ID có thể đã hết hỗ trợ. Có thể dùng biến môi trường PowerShell thay `.env`; biến môi trường có ưu tiên cao hơn.

```powershell
.\.venv\Scripts\python.exe -m scripts.check_environment
```

`check_environment` chỉ cho biết khóa đã được cấu hình hay chưa, không hiển thị giá trị. Lần chạy embedding đầu cần tải model; máy không cần GPU cho bộ nhỏ. Không đặt `temperature=0` mặc định; chỉ sửa `llm_temperature` khi model đã chọn hỗ trợ.

Để kiểm tra tên model bằng khóa đã cấu hình, dùng `python -m scripts.list_models`. Model ở lượt chạy thành công mới nhất là `gemini-3.5-flash-lite`. Nếu gặp 404, kiểm tra model và thông báo nhà cung cấp; nếu gặp 403, xử lý quyền project với Google; nếu gặp 503, đó là thông báo quá tải dịch vụ. Không tự động thử nhiều model khi bị từ chối quyền. Khi đổi model giữa các lần thử, chạy mới A/B/C để giữ cùng model, không dùng lại bản nháp B tạo bởi model khác.

## 2 Kiểm thử trước khi tải dữ liệu

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m scripts.test_project
.\.venv\Scripts\python.exe -m scripts.demo_offline
```

`scripts.test_project` chạy cùng bộ kiểm thử và lưu kết quả vào `results/software_tests.json`, `results/test-output.txt`. Demo offline dùng test double cho vector và LLM để xác nhận A/B/C nối được với nhau. Nó không trả lời câu hỏi Python thật. Các kiểm thử không gọi API trả phí.

Có thể kiểm tra nhánh hỏi lại bằng CLI mà chưa cần model/API/corpus:

```powershell
.\.venv\Scripts\python.exe -m scripts.ask 'Hướng dẫn dùng asyncio.TaskGroup' --compare
```

Kết quả mong đợi: A/B/C đều `clarify`, không gọi LLM. Nếu thiếu `.venv`, Python 3.8 hiện có chạy được các kiểm thử lõi dùng thư viện đã có; không dùng Python 3.8 để cài/chạy ứng dụng đầy đủ.

## 3 Thu thập bản nhỏ

```powershell
.\.venv\Scripts\python.exe -m src.collect
```

`data/sources.json` chứa ba trang thật: tomllib 3.11, asyncio-task 3.10 và 3.11. Không có trang tomllib 3.10 giả. Bộ thu thập kiểm tra HTTP, Content-Type, URL cuối, phiên bản trong tiêu đề và nội dung chính. HTML nguyên bản lưu dưới `data/raw/`, tên chứa mã băm; manifest lưu nguồn, phiên bản, URL, thời điểm và SHA256. Trang lỗi được ghi trong `results/collect_errors.json` và không được công bố vào manifest mới.

Chạy lại lệnh sẽ dùng snapshot đã có nếu mã băm khớp. `--refresh` chỉ dùng khi chủ đích tạo bản dữ liệu mới; không dùng giữa các lần thực nghiệm đã đóng băng.

## 4 Chia đoạn và rà soát ghi chú lịch sử

```powershell
.\.venv\Scripts\python.exe -m src.chunk
.\.venv\Scripts\python.exe -m scripts.review_history
```

Mô hình mặc định là `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`. Chương trình đọc `model.max_seq_length` và tokenizer thật. Mục/hàm/lớp được giữ thành đơn vị cha; đoạn con chứa chủ thể, chữ ký, mapping về cha. Code giữ xuống dòng và thụt lề. Ghi chú phiên bản có đoạn riêng chứa nguyên ghi chú và chủ thể, không cắt âm thầm. Nếu một ghi chú vượt cả cửa sổ mô hình, chương trình dừng để bạn chọn mô hình dài hơn thay vì mất thông tin.

Revision đã cố định trong config là `e8f8c211226b894fcb81acc59f3b34ba3efd5f42`; giới hạn thực tế là 128 token. Cache nằm trong `.cache/huggingface` của dự án. Bước chia đoạn được phép tải model; bước hỏi/lập chỉ mục chỉ nạp bản đã có để tránh âm thầm đổi model. Nếu Xet bị đứng trên Windows, dự án mặc định dùng HTTPS tiêu chuẩn; không cần HF token để tải model công khai này.

`chunk_tokens=100` là mục tiêu cho đoạn thông thường; ghi chú nguyên khối có thể dài hơn mục tiêu nhưng không vượt `max_seq_length`. Đoạn mã rất dài có thể trải qua nhiều chunk; xem `parents.jsonl` để đọc toàn bộ mã. Không sao chép một chunk giữa dòng rồi coi đó là chương trình hoàn chỉnh.

Đọc `data/history_review_draft.json`, mở URL gốc và đối chiếu chủ thể, nội dung, phiên bản. Chỉ giữ các ghi chú thật sự cần dùng; không duyệt hàng loạt mọi ghi chú. Với một mục đã kiểm tra:

- Giữ nguyên `candidate_id`, `text`, `source_sha256` và URL của nguồn gốc.
- Điền `history_targets`, chẳng hạn `["3.10", "3.11"]` **chỉ khi nguồn hỗ trợ sự kiện lịch sử đó**.
- Đổi `review_status` thành `human_reviewed`, điền `reviewer` và `reviewed_at` thực tế.
- Lưu các mục đã duyệt thành mảng JSON trong `data/history_reviews.json`.

Chạy lại `src.chunk` sau khi duyệt. Không dùng đáp án tập test để gán nhãn lịch sử. Khi chưa có ghi chú được duyệt, B/C có thể trả `insufficient_evidence` cho câu hỏi về tính năng chưa xuất hiện ở bản cũ; đó là hành vi chủ đích.

## 5 Lập chỉ mục và kiểm tra tìm kiếm

```powershell
.\.venv\Scripts\python.exe -m src.retrieve
.\.venv\Scripts\python.exe -m src.retrieve --query 'tomllib trong Python 3.11 có ghi TOML không?' --version 3.11 --mode B
.\.venv\Scripts\python.exe -m scripts.inspect_corpus --contains 'New in version 3.11' --parent
.\.venv\Scripts\python.exe -m scripts.check_data
```

Mỗi vector tương ứng chính xác một `chunk_id`. Metadata chỉ mục lưu mã băm chunks/vector, thứ tự ID, model, revision và tokenizer. Dữ liệu hoặc thứ tự bị thay đổi làm chương trình từ chối dùng chỉ mục cũ. Khi đổi model hoặc chunk, chạy lại cả `src.chunk` và `src.retrieve`.

B lọc tập ứng viên trước top-k. Với so sánh, B lấy tối đa 5 đoạn mỗi phiên bản rồi khử trùng; A lấy tối đa 10 toàn kho. Hai bên có chung ngân sách serialized evidence, được đếm bằng tokenizer embedding. Đây là thước đo ngữ cảnh nhất quán để so sánh, **không phải** số token tính tiền của Gemini. Token thực nhận từ API được ghi riêng trong log. Điểm cosine chỉ dùng xếp hạng, không phải xác suất đúng.

Ngân sách hiện tại là 1.500 token cho một phiên bản và 3.000 token khi so sánh, áp dụng giống nhau cho A/B/C. Đã điều chỉnh trên câu phát triển vì mức 1.000 token cũ loại đoạn xếp thứ 5 dù tổng năm đoạn chỉ dài 1.057 token; đoạn bị loại chứa câu phủ định quyết định đáp án. Đây là điều chỉnh dev, không phải kết quả cải thiện trên test độc lập.

## 6 Chạy A B C và giao diện

```powershell
.\.venv\Scripts\python.exe -m scripts.ask 'tomllib trong Python 3.11 có ghi TOML không?' --versions 3.11 --compare
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Có thể mở `run_app.cmd` để chạy giao diện. Bản bàn giao đã kiểm tra server local và biểu mẫu; Browser tích hợp không khả dụng nên chưa kiểm tra ảnh chụp giao diện trong Browser.

Streamlit sẽ hiển thị URL local của ứng dụng. Giao diện có câu hỏi, phiên bản, A/B/C, nguồn, trích đoạn, điểm truy xuất và verdict. Chọn chạy cả ba để B/C dùng cùng một bản nháp. Nếu bạn tự bấm B rồi C ở hai lượt độc lập, mỗi lượt có thể sinh khác nhau; không dùng cách đó để so sánh thực nghiệm.

C chỉ trả bản nháp khi mọi claim được đánh giá `supported`. Claim bị `contradicted` hoặc `insufficient` làm kết quả thành `insufficient_evidence`. API/JSON/schema lỗi luôn là `error`. JSON hợp lệ và nhãn supported không chứng minh đúng tuyệt đối; cần người chấm bằng nguồn gốc.

Chạy `python -m scripts.check_llm` để thử một câu phát triển qua A/B/C. Lệnh này giới hạn một attempt cho mỗi bước, tối đa ba request sinh/kiểm chứng; SDK automatic continuation được tắt. Nó lưu `results/live_smoke.json`, không phải bảng chất lượng trên test độc lập. Có thể dùng `--mode B` để chỉ kiểm tra một lần sinh khi chẩn đoán kết nối. Nếu chỉ verifier bị lỗi tạm thời, `--retry-verification` gửi một request kiểm chứng lại trên đúng bản nháp/nguồn B đã lưu, không sinh lại B; kết quả kiểm chứng trước được giữ trong `previous_verification_records` và trace. Không dùng việc thử lại có chọn lọc này trong phép đo test đã đóng băng.

Giao diện chỉ cache model/chỉ mục, khóa cache gồm cấu hình và mã băm dữ liệu. Không cache câu trả lời, tránh lẫn câu hỏi, phiên bản hoặc chế độ. `results/runs/application.jsonl` lưu trạng thái, bản nháp, bằng chứng, prompt, verdict, model trả về, thời gian và usage. Không chia sẻ log nếu câu hỏi có thông tin riêng.

## 7 Chuẩn bị dữ liệu đánh giá

```powershell
.\.venv\Scripts\python.exe -m scripts.evaluate validate
```

12 câu dev là đề xuất có nguồn để bạn rà soát, chưa phải gold. Với từng câu có đáp án, mở nguồn, xác nhận `gold_claims`, điền `acceptable_evidence_sets` bằng ID thật từ corpus. Mỗi danh sách con là **một bộ bằng chứng đủ cho toàn bộ đáp án**; nhiều danh sách con là những bộ thay thế. Không tự bịa ID. Với câu không trả lời, ghi `rationale` và hành động mong đợi. Điền thông tin người/ngày rà soát thật.

Đã tạo `data/dev_evidence_candidates.jsonl` với các đoạn gợi ý truy xuất cho 12 câu và `data/history_review_draft.json` với 67 ghi chú chờ rà soát. Đây là gợi ý để mở nguồn kiểm tra, chưa được tự động đưa vào gold hoặc history_note. Khi dựng corpus mới có thể tạo lại bằng `scripts.prepare_dev_review --out <file_mới>` và `scripts.review_history --out <file_mới>`.

Tạo test từ các nhóm API/sự kiện chưa dùng điều chỉnh. Mọi câu diễn đạt lại, câu phiên bản cũ/mới của cùng sự kiện nằm cùng `group_id` và cùng split. Kiểm tra tự động bắt nhóm trùng và câu trùng nguyên văn; vẫn cần người rà soát các cách diễn đạt gần nghĩa. Không đưa gold vào corpus/prompt.

Khi cần mở rộng:

```powershell
.\.venv\Scripts\python.exe -m src.collect --sources data/sources_extended.json
.\.venv\Scripts\python.exe -m src.chunk
.\.venv\Scripts\python.exe -m src.retrieve
```

Danh sách mở rộng tải các trang re, math, builtins ở cả hai phiên bản. Chọn các mục cụ thể và các nhóm câu hỏi có kiểm soát; không tuyên bố đã đánh giá toàn bộ thư viện chỉ vì đã tải trang. Rà lại các ID bằng chứng sau mỗi lần dựng corpus.

## 8 Đóng băng chạy và chấm thủ công

Xem chi tiết mẫu số và hướng dẫn chấm tại [notes/CHAM_DIEM.md](notes/CHAM_DIEM.md).

```powershell
.\.venv\Scripts\python.exe -m scripts.evaluate freeze --split test --out results/frozen/test_v1 --repeats 1 --seed 2026
.\.venv\Scripts\python.exe -m scripts.evaluate run --frozen results/frozen/test_v1
.\.venv\Scripts\python.exe -m scripts.evaluate review-template --runs results/frozen/test_v1/runs.jsonl --questions results/frozen/test_v1/questions.jsonl --out results/frozen/test_v1/reviews.jsonl
```

Trước khi có test, dùng `--split dev --out results/frozen/dev_v1` để tập quy trình. Freeze từ chối tập rỗng, câu chưa được người rà soát hoặc gold thiếu bằng chứng. Nó băm mã nguồn, dữ liệu gốc, câu hỏi, cấu hình, prompt, chỉ mục và ghi phiên bản thư viện/model. Chạy sẽ từ chối nếu những thành phần này thay đổi. Mỗi snapshot chỉ bắt đầu một lần; nếu bị ngắt, giữ log, công bố lần chạy chưa hoàn tất và tạo snapshot/lần chạy mới, không âm thầm ghi đè.

Đọc `reviews.jsonl` cùng log và nguồn, điền các trường chấm, tên/ngày người chấm, chuyển `review_status` sau khi chấm thật. Không sao chép nhãn của verifier vào phiếu chấm. Sau đó:

```powershell
.\.venv\Scripts\python.exe -m scripts.evaluate summarize --runs results/frozen/test_v1/runs.jsonl --questions results/frozen/test_v1/questions.jsonl --reviews results/frozen/test_v1/reviews.jsonl --out results/frozen/test_v1/metrics.json
```

Kết quả gồm JSON theo toàn tập/từng group và bảng Markdown. Nếu mẫu số 0 hoặc chưa chấm đủ, giá trị là `null`/`N/A`, không tự gán 0 hay 100%. Lỗi dịch vụ vẫn ở mẫu số đầu cuối; báo tỷ lệ lỗi riêng. C có chi phí B cộng kiểm chứng dù thí nghiệm tái sử dụng B để tiết kiệm lượt gọi. Nếu usage của yêu cầu lỗi không biết, `usage_complete=false`; số token ghi được là phần quan sát, không coi đó là hóa đơn đầy đủ.

## Cấu trúc mã nguồn

| File | Trách nhiệm |
|---|---|
| `src/collect.py` | Tải và xác minh HTML, manifest |
| `src/chunk.py` | Trích nội dung, chia đoạn, tạo ứng viên history_note |
| `src/embedding.py`, `src/retrieve.py` | Tokenizer, vector, chỉ mục, xếp hạng |
| `src/version_policy.py` | Chuẩn hóa yêu cầu và điều kiện hợp lệ nguồn |
| `src/llm_client.py` | Gemini, timeout, retry giới hạn, usage |
| `src/generate.py` | Prompt chung A/B, schema claim, dựng câu trả lời |
| `src/verify.py` | Kiểm tra quy tắc và schema verdict ngữ nghĩa |
| `src/pipeline.py` | Điều phối A/B/C, tái sử dụng B, log |
| `src/evaluation.py`, `scripts/evaluate.py` | Đóng băng, chạy cặp, phiếu chấm, chỉ số |
| `app.py` | Giao diện tiếng Việt |
| `tests/` | Kiểm thử logic với dữ liệu giả lập |
| `notes/` | Hướng dẫn đọc mã, chấm điểm, khung báo cáo, bàn giao |

## Nguồn đối chiếu kỹ thuật

Đã đọc tài liệu chính thức ngày 20–21/10/2026, kiểm tra cấu hình với SDK Google GenAI 2.32.0 và chạy thành công luồng A/B/C bằng API thật trên một câu phát triển.

- [Google GenAI SDK](https://googleapis.github.io/python-genai/): `models.generate_content`, `response_json_schema`, client và response. Dự án chọn API có tài liệu này; không sao chép máy móc ví dụ `interactions` trong bản hướng dẫn Word.
- [Google structured outputs](https://ai.google.dev/gemini-api/docs/structured-output): schema không thay thế việc kiểm tra nội dung.
- [Sentence Transformers](https://www.sbert.net/examples/sentence_transformer/applications/computing-embeddings/README.html): embedding và giới hạn `max_seq_length`.
- [tomllib 3.11](https://docs.python.org/3.11/library/tomllib.html), [asyncio 3.10](https://docs.python.org/3.10/library/asyncio-task.html), [asyncio 3.11](https://docs.python.org/3.11/library/asyncio-task.html): nguồn bản nhỏ.

Nếu thay SDK, model, tokenizer hoặc cách chia đoạn, kiểm tra lại rồi đóng băng thí nghiệm mới. Không sửa từ lỗi test rồi tiếp tục gọi kết quả cũ là kiểm thử độc lập.
