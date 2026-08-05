# AGENT RULES & OPERATIONAL GUIDELINES — Multi-Agent E-commerce Dispute Resolution

## 1. MỤC TIÊU & NHIỆM VỤ CỐT LÕI (CORE MISSION)
Mọi AI Agent khi làm việc trong repository này phải đọc và tuân thủ tuyệt đối các quy tắc dưới đây. Hệ thống Multi-Agent có trách nhiệm xử lý 50 khiếu nại thương mại điện tử (`input/EC_001.json` đến `EC_050.json`), truy xuất dữ liệu từ `data/*.csv`, áp dụng chính xác quy tắc `EC_POLICY_V1` và xuất ra 50 file JSON hợp lệ tại `output/`.

---

## 2. QUY ĐỊNH PHÂN BỔ THƯ MỤC DỰ ÁN (PROJECT DIRECTORY BOUNDARIES)

1. **`my_workspace/`**: Quản lý quy chuẩn tài liệu, kế hoạch (`plans/`), tiến độ (`progress/`), nhật ký (`logs/`), lịch sử (`history/`). **Bị `.gitignore` bỏ qua**, chỉ dùng làm không gian làm việc giữa User và Agent.
2. **`data/`**: Chứa 9 file CSV Olist statically. **Read-only**, không chỉnh sửa hoặc thêm bất kỳ file nào vào đây.
3. **`input/`**: Chứa 50 file JSON khiếu nại đầu vào (`EC_001.json` - `EC_050.json`). **Read-only**.
4. **`output/`**: Chứa 50 file JSON đầu ra (`EC_001.json` - `EC_050.json`). **CHỈ ĐƯỢC CHỨA ĐÚNG 50 FILE JSON NÀY**. Thư mục này dùng để nén `.zip` gửi nộp bài. Không để file rác, log, hay code vào đây.
5. **`logging/`**: Bắt buộc phải chứa 2 file log chính thức:
   - `trace.jsonl`: Lưu vết các lượt chạy thực tế của Multi-Agent (Agent-to-Agent handoffs).
   - `metadata.json`: Khai báo thông tin mô hình (Model name, <= 10B params), framework và runtime.
6. **`src/`**: Nơi chứa toàn bộ mã nguồn Python (`.py`) triển khai Multi-Agent.
7. **Thư mục gốc `./`**: Chứa `architecture.md`, `individual_5SoCuoiMHV_HoVaTen.md`, `AGENT_RULES.md`, `.gitignore`, `.env.example`.

---

## 3. QUY TẮC NGHIỆP VỤ `EC_POLICY_V1` (BUSINESS RULES)

Mọi tính toán tiền bạc làm tròn 2 chữ số thập phân (`round(val, 2)`). Không suy diễn sự kiện không có trong CSV.

| Primary Issue | Điều Kiện Kiểm Tra | Bên Chịu Trách Nhiệm (`party_type` / `party_id`) | Khoản Hoàn (`recommended_refund_brl`) | Hành Động (`resolution_actions`) | Root Cause Code |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `canceled_order_paid` | `order_status = canceled` & tổng payment > 0 | `platform` / `OLIST_PLATFORM` | Tổng payment | `issue_full_refund` | `ORDER_CANCELED_AFTER_PAYMENT` |
| `unavailable_order_paid` | `order_status = unavailable` & tổng payment > 0 | `platform` / `OLIST_PLATFORM` | Tổng payment | `issue_full_refund` | `ORDER_UNAVAILABLE_AFTER_PAYMENT` |
| `late_delivery_seller` | Giao sau estimated date & carrier nhận hàng sau `shipping_limit_date` | `seller` / `<seller_id>` | Tổng freight | `refund_freight` | `SELLER_HANDOFF_AFTER_LIMIT` |
| `late_delivery_logistics` | Giao sau estimated date & carrier nhận hàng <= `shipping_limit_date` | `logistics_provider` / `LOGISTICS_PROVIDER` | Tổng freight | `refund_freight` | `CARRIER_DELIVERED_AFTER_ESTIMATE` |
| `valid_split_payment` | Từ 2 payment row; tổng payment khớp tổng (item + freight) trong sai số 0.10 BRL | Không có (`none`) | 0 | `explain_valid_split_payment` | `MULTIPLE_PAYMENTS_RECONCILED` |
| `unsupported_late_claim` | Đơn giao <= estimated date và payment khớp | Không có (`none`) | 0 | `reject_late_refund` | `DELIVERY_WITHIN_ESTIMATE` |

---

## 4. QUY CHUẨN CÚ PHÁP EVIDENCE ID (EVIDENCE ID SYNTAX)

Chỉ được xuất Evidence IDs có thể dựng trực tiếp từ dữ liệu CSV thực tế. **Tuyệt đối không bịa đặt hoặc gõ sai cú pháp**:

- `order:<order_id>`
- `item:<order_id>:<order_item_id>` *(Ví dụ: `item:abc123:2`)*
- `payment:<order_id>:<payment_sequential>`
- `seller:<seller_id>`
- `policy:<root_cause_code>` *(Ví dụ: `policy:SELLER_HANDOFF_AFTER_LIMIT`)*

---

## 5. GIỚI HẠN & ĐỊNH DẠNG OUTPUT SCHEMA (OUTPUT BOUNDS & SCHEMA)

Mọi file JSON trong `output/` phải tuân thủ nghiêm ngặt các giới hạn:
- **Entity sets bounds:**
  - `order_ids`: tối đa 5 IDs
  - `item_ids`: tối đa 5 IDs
  - `seller_ids`: tối đa 5 IDs
  - `payment_ids`: tối đa 5 IDs
- **Evidence IDs:** tối đa 10 IDs (`len(evidence_ids) <= 10`).
- **Ranked causes:** tối đa 3 causes (`len(ranked_causes) <= 3`).
- **Responsible parties:** tối đa 3 parties (`len(responsible_parties) <= 3`).
- **Resolution actions:** tối đa 5 actions (`len(resolution_actions) <= 5`).
- **Confidence:** Giá trị Float nằm trong khoảng `[0.0, 1.0]`.
- **Case Status:** Chỉ nhận 1 trong 2 giá trị: `"action_required"` (nếu hoàn tiền > 0) hoặc `"no_action"` (nếu refund = 0).
- **Trường hợp order không có item row:** `item_ids` và `seller_ids` để mảng rỗng `[]`, `item_total_brl` và `freight_total_brl` gán `0.0`.

---

## 6. QUY TẮC MÔ HÌNH & BẢO MẬT (MODEL & SECURITY CONSTRAINTS)

1. **Model Parameter Limit:** Mỗi Agent chỉ được dùng LLM có thông số **<= 10B parameters**. Tên model phải được ghi rõ trong mã nguồn Python và khai báo trong `logging/metadata.json`.
2. **Bảo mật `.env`:** API Key và Secrets chỉ được đặt trong file `.env` (không commit lên Git). `.env.example` chỉ chứa biến mẫu.
3. **Commit trước khi nộp:** Luôn commit toàn bộ mã nguồn lên repository trước khi tạo file zip nộp bài.

---

## 7. QUY TRÌNH 4 BƯỚC THỰC THI DÀNH CHO AI AGENT (`my_workspace`)

Trước và sau mỗi phiên làm việc, Agent **bắt buộc tuân thủ 4 bước**:
1. **Bước 1 (Read README):** Kiểm tra `my_workspace/README.md` để nắm quy chuẩn.
2. **Bước 2 (Read Plan):** Kiểm tra file kế hoạch mới nhất tại `my_workspace/plans/`.
3. **Bước 3 (Update Progress):** Cập nhật phần trăm (%) và checklist tác vụ tại `my_workspace/progress/`.
4. **Bước 4 (Log Session):** Ghi nhật ký công việc, nguyên nhân lỗi (Root Cause + Fix) tại `my_workspace/logs/` và tóm tắt session tại `my_workspace/history/`.

---

## 8. QUY TẮC QUẢN LÝ MÔI TRƯỜNG & THƯ VIỆN (`uv`)

1. **Sử dụng `uv` thay vì `pip`:** Mọi thao tác quản lý virtualenv, cài đặt gói phụ thuộc, compile requirements hoặc chạy script Python **bắt buộc dùng `uv`** (ví dụ: `uv venv`, `uv pip install`, `uv run`). Tuyệt đối không dùng `pip` trực tiếp trừ khi được người dùng yêu cầu cụ thể.

---

## 9. QUY TẮC INTERACTION & XÁC NHẬN VỚI NGƯỜI DÙNG

1. **Hỏi ý kiến người dùng khi chưa rõ:** Nếu gặp bất kỳ yêu cầu mơ hồ, thiếu thông tin, quyết định thiết kế chưa chắc chắn hoặc tình huống phát sinh nhiều phương án xử lý, **Agent KHÔNG ĐƯỢC tự ý ra quyết định lung tung**. Agent phải chủ động liệt kê rõ ràng các phương án và hỏi lại người dùng để nhận xác nhận trước khi tiếp tục thực thi.

