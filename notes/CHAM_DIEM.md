# Hướng dẫn chuẩn bị đáp án và chấm thực nghiệm

Mục đích là đo chất lượng của ba cấu hình trên cùng câu hỏi và cùng kho dữ liệu. Người chấm đọc câu hỏi, đáp án chuẩn và bằng chứng gốc để quyết định. Nhãn do bộ kiểm chứng C trả về là đầu ra cần đánh giá; không dùng nó làm đáp án chuẩn.

## Rà soát bộ câu hỏi

Trong `data/dev.jsonl`, mọi câu hiện có `review_status=needs_human_review`. Đây là câu và nhãn AI đề xuất. Người rà soát mở URL, kiểm tra đáp án trong phạm vi corpus thực tế, rồi mới điền người/ngày và chuyển trạng thái. Không đổi trạng thái chỉ để vượt qua kiểm tra của script.

Một câu có `expected_action=answer` cần:

- `gold_claims`: các ý bắt buộc, mỗi chuỗi diễn đạt một ý kiểm tra được.
- `acceptable_evidence_sets`: các bộ chunk_id thật, mỗi bộ tự nó đủ chứng minh toàn bộ đáp án. Ví dụ cấu trúc `[["id_1", "id_2"], ["id_3"]]` có nghĩa dùng cả id_1 và id_2, hoặc dùng riêng id_3; đây chỉ là minh họa cấu trúc, không phải ID được phép sao chép.
- `source_urls`: URL để người đọc đối chiếu; chúng không thay thế mã bằng chứng trong chỉ mục.
- `reviewer`, `reviewed_at`: thông tin thực tế của người đã kiểm tra.

Không tìm được nguồn cho kết luận phủ định không chứng minh tính năng không có. Nếu corpus thiếu bằng chứng, sửa nhãn câu hỏi thành `insufficient_evidence` và ghi rõ lý do trước khi đóng băng. Nếu câu hỏi thiếu hoặc mâu thuẫn phiên bản, dùng `clarify`. Phiên bản khác 3.10/3.11 dùng `out_of_scope`.

Lập `group_id` theo họ API hoặc sự kiện, không theo số thứ tự hay cách viết câu. Câu hỏi về sự xuất hiện của TaskGroup ở hai phiên bản phải cùng nhóm, cùng split. Script kiểm tra nhóm trùng và câu trùng nguyên văn; người rà soát còn phải bắt các câu diễn đạt lại.

Nếu làm một mình, rà soát lần hai sau một khoảng thời gian và ghi giới hạn. Không mô tả là hai người gán nhãn độc lập. Có thể nhờ người thứ hai rà các trường hợp khó nếu điều kiện cho phép.

## Chấm một lượt chạy

`scripts.evaluate review-template` tạo phiếu JSONL chứa câu hỏi, gold, câu trả lời, claim và bằng chứng. Điền các trường sau:

| Trường | Cách điền |
|---|---|
| `answer_correct` | true khi câu trả lời đúng trọng tâm, đủ ý gold, đúng điều kiện/phiên bản và không thêm claim sai; false nếu không đạt |
| `version_error` | true khi có ít nhất một claim gán sai phiên bản; một câu so sánh vẫn chỉ đếm một lần |
| `citation_links_correct` | Số cặp claim–evidence_id thật sự chứng minh nội dung và phiên bản |
| `citation_links_total` | Số cặp claim–evidence_id thực tế; script điền và kiểm tra lại, không tự đổi mẫu số |
| `claims_supported` | Số claim có ít nhất một nguồn hợp lệ hỗ trợ đầy đủ; chỉ có link liên quan chưa đủ |
| `claims_total` | Số claim kỹ thuật được trả cho người dùng; script điền và kiểm tra lại |
| `retrieval_sufficient` | null để script đối chiếu các bộ gold; true/false khi người chấm đã đọc và cần ghi nhận bộ bằng chứng thay thế, kèm lý do trong notes |
| `review_status` | Chỉ đổi thành human_reviewed sau khi chấm thật |
| `reviewer`, `reviewed_at`, `notes` | Người/ngày chấm và căn cứ cho trường hợp gây tranh luận |

Với đầu ra không phải `answer`, không cần gán điểm chất lượng câu trả lời. Script vẫn dùng trạng thái để chấm hành động; từ chối một câu gold có đáp án làm giảm độ chính xác đầu cuối. Lỗi API/schema luôn là `error`, không tính là chủ động từ chối vì thiếu bằng chứng.

Nguồn history_note có URL phiên bản mới vẫn có thể hợp lệ với một claim về lịch sử của phiên bản cũ. Đối chiếu `history_targets`, chủ thể và sự kiện cụ thể; không đánh sai chỉ vì URL khác phiên bản. Ngược lại, ghi chú lịch sử không chứng minh mọi hướng dẫn khác trên cùng trang.

## Các mẫu số đã chọn

Các chỉ số dưới đây áp dụng cho từng cấu hình và từng nhóm. Nếu có nhiều lần lặp, mỗi lượt câu hỏi là một quan sát; script báo số lượng quan sát. Lỗi dịch vụ giữ trong các mẫu số đầu cuối. Mẫu số 0 trả N/A. Chưa chấm đủ thì chỉ số cần chấm cũng là N/A kèm `pending_review`.

| Chỉ số | Tử số | Mẫu số |
|---|---|---|
| Độ chính xác trên gold có đáp án | Câu có đáp án được hệ thống trả lời đúng, đủ | Mọi lượt gold có expected_action=answer |
| Độ đúng khi đã trả lời | Câu trả lời đúng | Mọi lượt hệ thống có status=answer |
| Độ bao phủ toàn tập | Lượt có status=answer | Mọi lượt trong tập đánh giá, gồm câu mơ hồ/ngoài phạm vi |
| Độ bao phủ trên gold có đáp án | Gold có đáp án được hệ thống trả lời | Mọi lượt gold có đáp án |
| Tỷ lệ nhầm phiên bản | Câu đã trả lời có ít nhất một claim sai phiên bản | Mọi câu đã trả lời cần xét phiên bản |
| Dẫn nguồn đúng | Liên kết claim–nguồn thực sự hỗ trợ | Mọi liên kết claim–nguồn đã trả |
| Dẫn nguồn đủ | Claim có nguồn hỗ trợ đầy đủ | Mọi claim kỹ thuật đã trả |
| Hành động đúng | Status bằng expected_action | Mọi lượt câu hỏi |
| Truy xuất đủ | Có ít nhất một bộ bằng chứng đủ trong retrieved_ids, hoặc được người chấm xác nhận | Mọi lượt gold có đáp án và có bộ bằng chứng chuẩn |
| Tỷ lệ lỗi | Lượt status=error | Mọi lượt câu hỏi |

Đọc độ đúng khi đã trả lời cùng độ bao phủ. Một hệ thống chỉ trả ít câu dễ có thể đạt độ đúng cao nhưng không đáp ứng phần lớn yêu cầu. Báo riêng truy xuất một nguồn và nhiều nguồn, kết quả theo group_id, lỗi bắt nhầm câu đúng và bỏ lọt câu sai của verifier.

Độ trễ là thời gian xử lý câu hỏi sau warm-up embedding; script ghi trung vị và p95 theo nearest rank. Với C, thời gian và usage bao gồm B cộng bước kiểm chứng. Log cũng ghi riêng incremental_usage để thấy phần phát sinh khi tái sử dụng B trong thí nghiệm. Khi API lỗi không trả usage, số token quan sát được có thể thiếu; không dùng số đó như chi phí đầy đủ.

Ước tính tiền chỉ thực hiện khi có model ID, ngày áp dụng, đơn giá đầu vào/đầu ra/thinking tương ứng và usage đầy đủ. Hiện dự án ghi **Chưa đo** phần chi phí. Không tự suy ra đơn giá của model khác.

## Sau khi đóng băng

Giữ nguyên câu hỏi, gold, corpus, prompt, model, tokenizer và cấu hình đã chốt. Nếu phát hiện lỗi từ test, ghi đó là kết quả và giới hạn. Khi sửa phương pháp, tạo phiên bản mới và chuẩn bị phép đánh giá phù hợp; không dùng lại test đã nhìn để khẳng định đánh giá độc lập.

Trước khi viết kết luận, đối chiếu số đếm trong metrics.json với log. Chọn cả ví dụ cải thiện và thất bại: B sửa lỗi A, C chặn lỗi B, C chặn nhầm, và cả ba cùng thất bại nếu quan sát thấy. Không đặt trước kết luận thứ tự A/B/C.
