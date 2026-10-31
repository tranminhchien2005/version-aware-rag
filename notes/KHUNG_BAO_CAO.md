# Khung báo cáo đồ án ngành

Tên đề tài: Hệ thống hỏi đáp tài liệu kỹ thuật có nhận biết phiên bản và kiểm chứng nguồn.

Điền nội dung theo mẫu của khoa. Các số liệu dưới đây đang **Chưa chạy/Chưa đo**; chỉ thay bằng số thực lấy từ log sau khi hoàn tất thực nghiệm và chấm thủ công.

## Chương 1 Giới thiệu

Trình bày lỗi nhầm phiên bản trong tài liệu kỹ thuật, đối tượng dùng và mục tiêu hỏi đáp có bằng chứng. Phạm vi là tài liệu Python 3.10 và 3.11, câu hỏi tiếng Việt và tên API giữ nguyên. Bản đầu dùng tomllib và asyncio. Nêu sản phẩm cần nộp và giới hạn về kho tài liệu, số người dùng, độ dài câu hỏi, chi phí API.

Phân biệt ứng dụng sử dụng LLM đã huấn luyện với huấn luyện mô hình. Mục tiêu là triển khai, đánh giá tác động của lọc phiên bản và kiểm chứng trong phạm vi đã chọn; chưa khẳng định tính mới khoa học chỉ từ việc ghép công cụ.

## Chương 2 Cơ sở và nghiên cứu liên quan

Giải thích LLM, hallucination, RAG, chunk, metadata, embedding, cosine, top k, citation, claim và verification. Đọc bài gốc RAG và VersionRAG từ danh mục trong tài liệu hướng dẫn. Với mỗi công trình, ghi bài toán, dữ liệu, phương pháp, đánh giá và phần liên quan/khác với dự án này. Kết quả tác giả báo cáo không phải kết quả của đồ án.

## Chương 3 Phân tích và thiết kế

Mô tả yêu cầu đầu vào/đầu ra, năm trạng thái, schema nguồn/chunk/claim/verdict, quy tắc ordinary/history_note và quy trình người rà soát. Vẽ kiến trúc từ notes/HOC_MA_NGUON.md, bổ sung đường đi dữ liệu chuẩn bị offline và log khi hỏi.

Lập bảng so sánh A/B/C. A/B dùng chung corpus, embedding, model, prompt, schema, ngân sách; B đổi tập ứng viên theo phiên bản. C thêm kiểm chứng toàn bộ claim của đúng B. Mọi cấu hình dùng chung chính sách hỏi lại/phạm vi.

## Chương 4 Cài đặt

Ghi phiên bản Python/thư viện đã chạy thật, model ID, embedding revision/tokenizer, giới hạn đầu vào, độ dài chunk, top k và ngân sách. Giải thích việc lưu HTML, manifest/hash, vector mapping, timeout/retry, cache và xử lý lỗi. Minh họa một lượt có thể truy vết từ run_id; giữ khóa bí mật ngoài ảnh/báo cáo.

Phân biệt kiểm thử đơn vị giả lập, kiểm thử tích hợp có model và thực nghiệm chất lượng. Không dùng ảnh giao diện trả lời tốt thay cho số liệu.

## Chương 5 Thực nghiệm

Mô tả nguồn/ngày snapshot, số trang/chunk, số nhóm API, cách tạo câu hỏi, người rà soát, chia dev/test theo nhóm, số lần lặp, thứ tự chạy và quy trình đóng băng. Ghi rõ ví dụ trong tài liệu hướng dẫn đã dùng cho dev, không dùng làm test độc lập.

| Thông số thực nghiệm | Giá trị thực tế |
|---|---|
| Ngày chụp corpus và SHA256 | Chưa chạy |
| Số trang và số chunk | Chưa đo |
| Số history_note đã được người rà soát | Chưa đo |
| Model ID sinh và kiểm chứng | Chưa chạy |
| Embedding revision và max_seq_length | Chưa chạy |
| Số câu/group dev và test | Chưa chốt |
| Số người và cách rà soát | Chưa thực hiện |
| Số lần lặp, seed, snapshot | Chưa chạy |

| Chỉ số | A | B | C |
|---|---|---|---|
| Độ chính xác trên gold có đáp án | Chưa đo | Chưa đo | Chưa đo |
| Độ đúng khi đã trả lời | Chưa đo | Chưa đo | Chưa đo |
| Độ bao phủ | Chưa đo | Chưa đo | Chưa đo |
| Nhầm phiên bản | Chưa đo | Chưa đo | Chưa đo |
| Dẫn nguồn đúng và đủ | Chưa đo | Chưa đo | Chưa đo |
| Hành động đúng và truy xuất đủ | Chưa đo | Chưa đo | Chưa đo |
| Độ trễ trung vị và p95 | Chưa đo | Chưa đo | Chưa đo |
| Token, lượt gọi, tỷ lệ lỗi | Chưa đo | Chưa đo | Chưa đo |

Giải thích tử số/mẫu số, lỗi dịch vụ, dữ liệu chưa chấm và usage thiếu. Báo theo từng nhóm, kèm trường hợp cải thiện và thất bại. Nếu C giảm sai phiên bản đồng thời giảm bao phủ, nêu cả hai. Không tuyên bố C tốt hơn trước khi có số liệu.

## Chương 6 Kết luận và giới hạn

Đối chiếu từng mục tiêu với kết quả đã làm. Viết kết luận theo cấu trúc: trên tập bao nhiêu câu, những nhóm nào, chỉ số thay đổi ra sao và đánh đổi gì. Chỉ điền số sau thực nghiệm. Nêu giới hạn dữ liệu nhỏ, cùng LLM sinh/kiểm chứng, nhãn thủ công, biến động API và phạm vi hai phiên bản.

Phần phát triển tương lai có thể xét thêm phiên bản/nguồn, chọn lọc kiểm chứng hoặc truy xuất bổ sung. Đó là hướng sau này, không ghi như chức năng đã hoàn thành của bản đầu.

## Hồ sơ nộp và trình diễn

Gói nộp gồm mã nguồn, README, cấu hình mẫu, lockfile đã cài thực tế, dữ liệu được phép chia sẻ, cách dựng lại chỉ mục, câu hỏi/nhãn đã rà soát, log, phiếu chấm, chỉ số, báo cáo, slide và video dự phòng. Chạy lại từ README trong môi trường mới khi có điều kiện.

Chuẩn bị 8–10 slide theo thời lượng của khoa: vấn đề, phạm vi, kiến trúc, dữ liệu, A/B/C, bộ đánh giá, kết quả, một cải thiện và một thất bại, giới hạn. Demo gồm câu có đáp án, câu nhạy phiên bản, câu thiếu phiên bản và câu thiếu bằng chứng. Không hứa A chắc chắn sai ở mọi lượt; dùng log thực nghiệm để giải thích dao động.
