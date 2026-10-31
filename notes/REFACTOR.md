# Rà soát và refactor ngày 22/10/2026

Mục tiêu: làm rõ mã nguồn và bỏ phần dư thừa, giữ nguyên cách chạy A/B/C, dữ liệu và kết quả thực nghiệm đang có. Đây là kiểm tra refactor, không phải đánh giá chất lượng RAG.

Cập nhật bổ sung cùng ngày: đã làm rõ tên biến trong 16 file và bổ sung hai kiểm thử CLI; lượt cuối đạt 70/70 kiểm thử. Chi tiết nằm trong phần bổ sung tên biến bên dưới và `results/naming_checks.json`. Các số liệu 64/68 ca ở lượt refactor đầu được giữ lại theo đúng thời điểm chạy.

## Khảo sát và bảo toàn công việc hiện có

- Đã đọc README, cấu hình, các điểm chạy, toàn bộ module trong `src/`, `scripts/` và các kiểm thử. Đã kiểm tra cả import, CLI, decorator cache Streamlit, lời gọi qua factory và các đường dẫn trong tài liệu/setup.
- `git status` xác nhận thư mục không thuộc một Git repository. Không có lịch sử Git để phân biệt thay đổi trước phiên; toàn bộ mã hiện có được dùng làm mốc, không reset hoặc khôi phục từ ZIP cũ.
- Bản sao mã trước khi sửa nằm tại `D:\LLM\tmp\refactor_20261022\before`. Bản sao không chứa `.env`, cache model hoặc dữ liệu ứng dụng riêng.
- Đã đối chiếu SHA256 của 29 file có sẵn trong `data/`, `results/`, cùng `config.json` và `.env`: không file nào bị đổi hoặc mất. Kết quả kiểm tra refactor mới được lưu riêng, không ghi đè các kết quả cũ.

Luồng chính vẫn là: UI/CLI → `runtime.make_pipeline` → chính sách phiên bản → nạp retriever khi cần → truy xuất → sinh A/B → C nhận đúng bản nháp/bằng chứng B → lưu log. `collect` → `chunk` → `retrieve` là các bước chuẩn bị dữ liệu. `scripts.evaluate` điều phối đóng băng/chạy/chấm; `src.evaluation` kiểm tra dữ liệu và tính chỉ số.

## Các thay đổi chính

1. Tách `generate.evidence_for_prompt` để việc sinh câu trả lời, kiểm chứng và tính ngân sách dùng cùng bộ trường bằng chứng. Luồng kiểm chứng không còn phải dựng payload câu hỏi giả chỉ để lấy trường `evidence`.
2. Trong truy xuất, giữ danh sách bằng chứng đã chuẩn hóa của các đoạn được chấp nhận; không dựng lại metadata của toàn bộ danh sách ở mỗi vòng. Thứ tự, cách lọc trước top-k, xử lý đoạn vượt ngân sách và cách đếm token giữ nguyên.
3. Trong chia đoạn, đếm token một lần cho mỗi ghi chú rồi dùng lại. Giới hạn embedding vẫn được kiểm tra trước khi thêm ghi chú; dữ liệu review vẫn phải khớp nội dung và SHA256 nguồn.
4. Gom thao tác chuyển sang `insufficient_evidence` tại một hàm của Pipeline. Hàm giữ bản nháp/bằng chứng để truy vết và xóa claim/citation công bố theo hành vi cũ.
5. Dọn import không dùng, hằng số không có người dùng và một biến trung gian dư thừa. Dùng `dict` giữ thứ tự chèn thay cho `OrderedDict` tại nơi chỉ cần chèn khóa và đọc danh sách giá trị.
6. Đổi hai tên file có lợi ích rõ ràng, cập nhật import, lệnh trong README/biên bản và `setup.ps1`. Sửa ký tự thừa trước tiêu đề README.

Không thêm cache mới. Cơ chế nạp model/chỉ mục khi cần và khóa cache Streamlit theo cấu hình/hash dữ liệu đã có được giữ nguyên. Chưa đo tốc độ hoặc bộ nhớ trước/sau, nên không khẳng định mức cải thiện hiệu năng.

## Code/file đã loại bỏ và căn cứ

| Vị trí | Phần bỏ | Căn cứ |
|---|---|---|
| `src/common.py` | Import `typing.Any` | Không có annotation hoặc lời gọi sử dụng |
| `src/evaluation.py` | Hằng `SCORE_FIELDS` | Tìm toàn dự án chỉ có định nghĩa; không có import, cấu hình hoặc truy cập động đến tên này |
| `src/chunk.py` | Import/khởi tạo `OrderedDict` | Không dùng API riêng của OrderedDict; thứ tự chèn được giữ bằng dict |
| `src/chunk.py` | Biến `key = anchor` | Chỉ là bí danh dùng một lần; dùng trực tiếp `anchor` |
| `src/chunk.py` | Kiểm tra độ dài lần hai cho cùng ghi chú history | Cùng chuỗi đã được kiểm tra trước đó; vẫn kiểm tra độ dài lần đầu và tính toàn vẹn review |
| `src/chunk.py` | Hai import `validate_chunk` bên trong hàm | Chuyển thành một import cấp module, vẫn gọi validator tại các vị trí cũ |
| `scripts/check_environment.py` | Import `importlib.util` | Chỉ dùng `importlib.metadata`; không gọi API của util |
| `scripts/review_history.py` | Import `pathlib.Path` | Không có người dùng trong script |
| `tests/fixtures.py` | Import `SimpleNamespace`, `digest` | Không được dùng trong dữ liệu/đối tượng giả lập |
| `tests/test_core.py` | Import `copy`, `digest`, `write_json` | Không được dùng trong kiểm thử |
| `tests/test_data_evaluation.py` | Import `copy`, `tempfile`, `Path`, `digest`, `chunk` | Không được dùng trong kiểm thử |
| `tests/test_integration_local.py` | Import `copy`, `digest` | Không được dùng trong kiểm thử |
| `tests/test_llm_transport.py` | Import `json` | Không được dùng trong kiểm thử |
| Hai đường dẫn cũ trong bảng đổi tên | File cũ sau khi chuyển tên | Nội dung chức năng vẫn còn ở đường dẫn mới, mọi tham chiếu đang dùng đã cập nhật |

Giữ lại các hàm `main`, factory nạp lười, tham số khóa cache và file `__init__.py`: chúng có vai trò qua CLI, callback/decorator hoặc cơ chế package. Giữ `purpose` trong giao diện client để không phá hợp đồng với Pipeline và test doubles. Giữ `common.py` vì các tiện ích ngắn hiện được dùng chung; chưa có lợi ích đủ rõ để chia thành nhiều module nhỏ. Không xóa corpus, câu hỏi, log hoặc tài liệu.

## Bảng tên cũ → tên mới

| Tên cũ | Tên mới | Lý do |
|---|---|---|
| `scripts/doctor.py` | `scripts/check_environment.py` | Nêu rõ nhiệm vụ kiểm tra môi trường và cấu hình |
| `tests/helpers.py` | `tests/fixtures.py` | Nêu rõ đây là dữ liệu/đối tượng giả lập dùng trong kiểm thử và demo offline |

Lệnh `python -m scripts.doctor` được thay bằng `python -m scripts.check_environment`. Các điểm chạy ứng dụng, tên file dữ liệu và cấu hình không đổi.

## Bổ sung: đặt tên biến theo nội dung xử lý

Lượt đầu đã đổi hai tên file và dọn code, nhưng còn nhiều biến viết tắt chưa được làm rõ đồng bộ. Lượt bổ sung thay tên biến trong 16 file thuộc `src/`, `scripts/` và `app.py`, gồm 123 ánh xạ theo file/phạm vi và 656 vị trí sử dụng. Các tên file còn lại như `collect.py`, `chunk.py`, `retrieve.py`, `verify.py`, `evaluation.py` và `version_policy.py` phù hợp với trách nhiệm hiện tại nên được giữ.

| Vị trí | Tên cũ | Tên mới | Ý nghĩa |
|---|---|---|---|
| `src/collect.py` | `sid` | `source_id` | Mã nguồn tài liệu |
| `src/collect.py` | `spec` | `source_spec` | Khai báo nguồn cần tải |
| `src/collect.py` | `sha` | `source_sha256` | Mã băm nội dung nguồn |
| `src/collect.py` | `merged` | `manifest_by_source` | Manifest lập chỉ mục theo mã nguồn |
| `src/chunk.py` | `cid` | `candidate_id` | Mã ứng viên ghi chú lịch sử |
| `src/chunk.py` | `raw` | `raw_path` | Đường dẫn HTML gốc |
| `src/chunk.py` | `base` | `source_metadata` | Metadata nguồn dùng cho các đoạn |
| `src/chunk.py` | `copy` | `html_fragment` | Bản sao đoạn HTML đang xử lý |
| `src/retrieve.py` | `q` | `query_vector` | Vector câu hỏi |
| `src/retrieve.py` | `scores` | `similarity_scores` | Điểm tương đồng với các đoạn |
| `src/retrieve.py` | `lists` | `ranked_by_version` | Các chỉ số đoạn đã xếp hạng theo phiên bản |
| `src/retrieve.py` | `selected` | `selected_indices` | Chỉ số các đoạn được chọn |
| `src/pipeline.py`, script liên quan | `b`, `c` | `b_record`, `c_record` | Bản ghi đầu ra của B và C |
| `src/verify.py` | `cid`, `refs` | `claim_id`, `evidence_ids` | Mã nhận định và danh sách mã bằng chứng |
| `src/verify.py` | `indexed`, `expected` | `evidence_by_id`, `claims_by_id` | Bảng tra cứu bằng chứng và nhận định |
| `src/common.py` | `a`, `b` trong `add_usage` | `left_usage`, `right_usage` | Hai bộ số liệu usage cần cộng |
| `src/evaluation.py` | `gold`, `scored` | `questions_by_id`, `reviews_by_run_id` | Bảng tra câu hỏi và phiếu chấm |
| `src/evaluation.py` | `one_n`, `multi_n` | `single_source_total`, `multiple_source_total` | Số lượt đánh giá theo số nguồn cần thiết |
| `scripts/evaluate.py` | `p`, `m` | `command_parser`, `metric` | Parser lệnh và chỉ số đang trình bày |
| `scripts/check_llm.py` | `c` trong danh sách model | `llm_call` | Bản ghi một lượt gọi model |
| UI và script rà soát | `q`, `r`, `e` theo phạm vi | `question`, `record`, `evidence_item` | Câu hỏi, bản ghi chạy và đoạn bằng chứng |

Toàn bộ ánh xạ, bao gồm số vị trí sử dụng, được lưu tại [kết quả kiểm tra tên biến](../results/naming_checks.json). Việc thay tên chỉ áp dụng cho identifier cục bộ/tham số liên quan. Đã đối chiếu AST sau khi chuẩn hóa tên biến: cấu trúc phép toán, thuộc tính, keyword của lời gọi, khóa JSON, prompt, URL và đường dẫn giữ nguyên. Các tham số CLI `--runs`, `--questions`, `--reviews` vẫn được giữ và đã có kiểm thử chạy lệnh thực tế.

Kết quả sau lượt bổ sung:

- 70 kiểm thử đạt, không lỗi/thất bại/bỏ qua; hai ca mới bảo vệ các lệnh `review-template` và `summarize` bằng file tạm.
- Đầu ra đối chiếu chính sách, pipeline A/B/C, truy xuất và corpus có cùng SHA256 với bản trước khi đổi tên: `e20e494dc9f555f6d73b5e3f2b2174b1b596d6ab5dc2b2ba357200b9060285d5`.
- 30 file đã có trong dữ liệu/kết quả cùng cấu hình và `.env` khớp mã băm; kết quả mới lưu riêng tại `results/naming_checks.json`.
- Không gọi API sinh văn bản thật trong lượt đổi tên. Không có phép đo hiệu năng mới.
- Bản mã trước lượt đổi tên nằm tại `D:\LLM\tmp\naming_20261022\before`; bản diff và log kiểm tra nằm trong thư mục `evidence` bên cạnh.

## Sửa riêng vấn đề trong kiểm thử

Kiểm thử Streamlit trước đây dùng cấu hình log mặc định và có thể thêm bản ghi vào `results/runs/application.jsonl`. Kiểm thử đã được chuyển sang log trong `TemporaryDirectory`; đồng thời kiểm tra log tạm chứa đúng ba bản ghi A/B/C. Đây là sửa tác dụng phụ của kiểm thử, không đổi hành vi log khi người dùng chạy ứng dụng. Bộ kiểm thử gốc được chạy trên bản sao để không thêm dòng vào log thật trong lần kiểm tra trước refactor.

## Các kiểm tra đã chạy

| Kiểm tra | Kết quả |
|---|---|
| Bộ kiểm thử trước refactor, chạy trên bản sao | 64 ca đạt, 0 lỗi/thất bại/bỏ qua |
| Nhóm dọn code/đổi tên | 63 ca liên quan đạt; kiểm thử UI chạy trong lượt đầy đủ tiếp theo |
| Bộ kiểm thử cũ sau refactor logic | 64 ca đạt |
| Bộ kiểm thử cuối lượt refactor đầu | 68 ca đạt, 0 lỗi/thất bại/bỏ qua |
| Bộ kiểm thử sau lượt bổ sung tên biến | 70 ca đạt, 0 lỗi/thất bại/bỏ qua |
| Đối chiếu trước/sau | 15 yêu cầu chính sách, 7 tình huống pipeline, 36 lượt tìm kiếm giả lập, 9 lượt tìm kiếm trên chỉ mục thật; đầu ra giữ nguyên sau khi bỏ UUID/thời điểm/thời lượng |
| Dựng lại corpus ở thư mục tạm bằng tokenizer/model đã cache | Cả hai lượt tạo 368 chunk; toàn bộ chunks, parents, ứng viên lịch sử và metadata giống nhau |
| Prompt và schema | Hash của cả phần sinh lẫn kiểm chứng không đổi |
| Import | Import thành công cả 29 module trong src/scripts/tests ngoài các `__init__.py` |
| Điểm chạy CLI | 9 lệnh `--help` chạy thành công; CLI A/B/C thiếu phiên bản đều hỏi lại và không gọi LLM |
| Demo offline, lưu ở thư mục tạm | Ba cấu hình nối được với nhau; C dùng B và cộng usage đúng; toàn bộ LLM/dữ liệu của demo là giả lập |
| Kiểm tra dataset | Đọc được 12 câu dev thuộc 4 group; không tự đánh dấu câu hỏi là đã được người rà soát |
| Phụ thuộc | `pip check`: không có xung đột |
| Streamlit | Server local trên cổng kiểm tra 18512: health và trang chủ HTTP 200; server kiểm tra đã dừng |
| Bảo toàn file hiện có | 29/29 hash khớp, gồm dữ liệu, cấu hình, `.env` và các kết quả/log đã tồn tại |

Bốn ca hồi quy mới bảo vệ: bỏ qua đoạn vượt ngân sách mà vẫn xét đoạn tiếp theo; nạp retriever/client một lần khi chạy thứ tự BA và không tìm kiếm lại cho C; giữ danh tính/nguồn/token của ghi chú đã duyệt; từ chối ghi chú đã duyệt nếu vượt cửa sổ embedding, đồng thời không ghi đè corpus trước đó.

SHA256 của toàn bộ đầu ra đối chiếu trước/sau:

```text
e20e494dc9f555f6d73b5e3f2b2174b1b596d6ab5dc2b2ba357200b9060285d5
```

Kết quả tổng hợp mới: `results/refactor_checks.json`. Log chi tiết và đầu ra đối chiếu: `D:\LLM\tmp\refactor_20261022\evidence`. `results/software_tests.json`, `results/live_smoke.json` và các kết quả bàn giao cũ được giữ nguyên, nên vẫn phản ánh các lượt chạy trước đây.

## Phần chưa xác minh và công việc còn lại

- Browser tích hợp không khả dụng; đã kiểm tra biểu mẫu bằng Streamlit AppTest và server bằng HTTP, chưa kiểm tra ảnh chụp giao diện trên Browser.
- Không gọi API sinh/kiểm chứng thật trong lượt refactor này. Kiểm thử phần mềm dùng test doubles cho LLM; kiểm tra truy xuất/chia đoạn dùng dữ liệu và embedding thật ở chế độ offline. Kết quả Gemini thật trước đây được giữ nguyên.
- Chưa đo tốc độ, bộ nhớ hoặc chi phí API trước/sau. Không nâng hạng chất lượng A/B/C từ các kiểm tra này.
- Chưa chạy trên Linux; đã kiểm tra chính xác chữ hoa/chữ thường của các đường dẫn import nội bộ trên mã nguồn.
- Bộ dev vẫn cần người rà soát và tập test độc lập vẫn cần được chuẩn bị trước khi thực nghiệm chất lượng.
- Gói ZIP bàn giao cũ chưa được tạo lại; mã đang chạy và báo cáo mới nằm trong thư mục dự án.

## Chạy dự án sau refactor

PowerShell:

```powershell
cd D:\LLM\rag_phien_ban
.\.venv\Scripts\python.exe -m scripts.check_environment
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Cũng có thể mở `run_app.cmd`. Lệnh hỏi qua CLI giữ nguyên:

```powershell
.\.venv\Scripts\python.exe -m scripts.ask "tomllib trong Python 3.11 có ghi TOML không?" --versions 3.11 --compare
```

Chạy kiểm thử không gọi API sinh văn bản:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
