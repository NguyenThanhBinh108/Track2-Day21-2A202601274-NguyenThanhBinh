# Báo Cáo Lab Day 21 - CI/CD cho AI Systems

| | |
|---|---|
| Họ và tên | Nguyễn Thành Bình |
| MSSV | 2A202601274 |
| Lớp / Khóa | K4 |
| Repo GitHub | https://github.com/NguyenThanhBinh108/Track2-Day21-2A202601274-NguyenThanhBinh |
| Ngày nộp | ___ |

---

## 1. Bộ Siêu Tham Số Đã Chọn và Lý Do

| Lần chạy | n_estimators | learning_rate | max_depth | f1_score | accuracy |
|---|---|---|---|---|---|
| 1 | 100 | 0.1 | 3 | 0.7109 | 0.8780 |
| 2 | 50 | 0.05 | 2 | 0.6051 | 0.8460 |
| 3 | 200 | 0.1 | 5 | 0.7149 | 0.8740 |
| 4 | 200 | 0.05 | 3 | 0.7014 | 0.8740 |
| 5 | 100 | 0.2 | 3 | **0.7290** | **0.8840** |

**Bộ đã chọn:** `n_estimators=100`, `learning_rate=0.2`, `max_depth=3`.

**Lý do:** Lần 5 đạt `f1_score` cao nhất (0.7290). Lần này cũng có accuracy cao nhất, nhưng
thứ tự giữa bảng thì hai chỉ số không trùng nhau: lần 3 xếp thứ hai theo F1 (0.7149) lại
thua lần 1 nếu xét accuracy (0.8740 so với 0.8780). Quan trọng hơn, accuracy gần như không
phân biệt được các mô hình — chỉ dao động 0.038 (0.8460 đến 0.8840) trong khi F1 dao động
0.124, gấp hơn ba lần. Về đánh đổi giữa hai tham số: lần 2 với 50 cây và `learning_rate`
0.05 chưa học đủ (F1 0.6051, dưới ngưỡng). Hạ `learning_rate` xuống 0.05 rồi bù bằng 200
cây (lần 4) vẫn chỉ đạt 0.7014, thấp hơn lần 1 chỉ dùng 100 cây với `learning_rate` 0.1 —
tăng số cây không bù đủ cho `learning_rate` thấp trên bộ dữ liệu này.

---

## 2. Vì Sao Ngưỡng Chất Lượng Đặt Trên F1 Chứ Không Phải Accuracy

Chỉ 24,8% mẫu thuộc lớp thu nhập trên 50K. Mô hình vô dụng luôn trả lời "thu nhập thấp" đạt
accuracy 0.7520 trên tập holdout của tôi, trong khi F1 lớp dương bằng 0.0000: accuracy cao
chỉ phản ánh việc đoán đúng lớp đa số. F1 lớp dương là trung bình điều hòa của precision và
recall tính riêng trên lớp thiểu số, nên chỉ cao khi mô hình vừa tìm ra được người thu nhập
cao, vừa không gán nhãn bừa.

Không dùng `average="weighted"` hay `"macro"` vì cả hai trộn lớp đa số vào kết quả. Đo trên
lần chạy 2: F1 lớp dương 0.6051 (trượt ngưỡng 0.65) nhưng `macro` cho 0.7547 và `weighted`
cho 0.8301, cả hai đều vượt ngưỡng. Tệ hơn, mô hình luôn trả lời "thu nhập thấp" vẫn được
`weighted` F1 là 0.6456. Dùng `average` sẽ vô hiệu hóa quality gate.

---

## 3. Khó Khăn Gặp Phải và Cách Giải Quyết

| Khó khăn | Nguyên nhân | Cách giải quyết |
|---|---|---|
| `log_model` chiếm khoảng một phần ba thời gian mỗi lần chạy | MLflow suy luận môi trường bằng một subprocess pip | Khai báo `pip_requirements` tường minh: 2.95 xuống 1.84 giây |
| Ba lần chạy của pytest lẫn vào MLflow UI | `train()` gọi `mlflow.start_run()` nên test cũng ghi vào `mlflow.db` | Thêm `tests/conftest.py` trỏ tracking URI sang thư mục tạm |
| Test báo `Could not find experiment with ID 0` | `tmp_path_factory` tạo sẵn thư mục rỗng nên MLflow không khởi tạo experiment mặc định | Trỏ tracking URI vào một thư mục con chưa tồn tại |

---

## 4. So Sánh Bước 2 và Bước 3

| | f1_score | accuracy |
|---|---|---|
| Bước 2 (`train_batch1`, 22.361 mẫu) | 0.7290 | 0.8840 |
| Bước 3 (thêm `train_batch2`, 44.722 mẫu) | 0.7330 | 0.8820 |

**Nhận xét:** Gấp đôi dữ liệu chỉ làm F1 tăng 0.0040 và accuracy giảm 0.0020, đều nằm trong
sai số lấy mẫu của holdout 500 mẫu. Hai batch chia ngẫu nhiên từ cùng một nguồn nên cùng
phân phối (tỷ lệ lớp dương 0.2477 so với 0.2478), dữ liệu mới không mang thêm thông tin mà
mô hình chưa học được. Giá trị của Bước 3 là chứng minh vòng tự động hóa chạy đúng, không
phải chỉ số cao hơn.

---

## 5. Phần Bonus Đã Thực Hiện

- [ ] Bonus 1 - DagsHub: không thực hiện.
- [x] Bonus 2 - `scan_threshold()` quét 0.10 đến 0.90: ngưỡng 0.30 cho F1 0.7519, so với 0.7290 tại ngưỡng mặc định 0.50.
- [x] Bonus 3 - `write_detail_report()` ghi `outputs/detail.txt` và upload cùng `report.json`. Mô hình bỏ sót 46 người thu nhập cao (recall 0.6290) nhưng chỉ gán nhầm 12 người; bỏ sót là sai lầm tốn kém hơn.
- [x] Bonus 4 - Quality gate tải `artifacts/current/report.json` của model đang chạy và chặn triển khai nếu F1 mới giảm quá 0.02.
- [x] Bonus 5 - `check_drift()` cảnh báo khi tỷ lệ lớp dương lệch quá 5 điểm phần trăm so với 24,8%, và ghi tỷ lệ này vào `report.json`.
