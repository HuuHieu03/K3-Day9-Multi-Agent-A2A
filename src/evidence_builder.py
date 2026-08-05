import re
from typing import List, Dict, Any, Optional

class EvidenceBuilder:
    """
    Module chịu trách nhiệm sinh và kiểm duyệt 5 chuỗi định dạng Evidence ID chuẩn theo đề bài.
    Mục đích lớn nhất là:
    1. Tránh cho các LLM Sub-Agents tự ý tạo ra Evidence ID sai format hoặc suy đoán dữ liệu ảo (Hallucination).
    2. Kiểm duyệt chặt chẽ bằng Regex (Validator) nhằm loại bỏ hoàn toàn lỗi False Positive (FP).
    """
    
    # 5 chuỗi Regex chuẩn hóa cho 5 định dạng Evidence ID
    REGEX_PATTERNS = {
        "order_status": re.compile(r"^order_status:[a-zA-Z0-9_-]+:[a-zA-Z0-9_-]+$"),
        "order_timestamp": re.compile(r"^order_timestamp:[a-zA-Z0-9_-]+:[a-zA-Z0-9_-]+:.+$"),
        "order_item_seller": re.compile(r"^order_item_seller:[a-zA-Z0-9_-]+:\d+:[a-zA-Z0-9_-]+$"),
        "shipping_limit": re.compile(r"^shipping_limit:[a-zA-Z0-9_-]+:\d+:.+$"),
        "payment_row": re.compile(r"^payment_row:[a-zA-Z0-9_-]+:\d+:[a-zA-Z0-9_-]+:\d+(\.\d+)?$")
    }

    @classmethod
    def build_order_status_evidence(cls, order_id: str, status: str) -> str:
        return f"order_status:{order_id}:{status}"

    @classmethod
    def build_timestamp_evidence(cls, order_id: str, field_name: str, timestamp: Any) -> str:
        return f"order_timestamp:{order_id}:{field_name}:{str(timestamp).strip()}"

    @classmethod
    def build_item_seller_evidence(cls, order_id: str, item_id: Any, seller_id: str) -> str:
        return f"order_item_seller:{order_id}:{item_id}:{seller_id}"

    @classmethod
    def build_shipping_limit_evidence(cls, order_id: str, item_id: Any, shipping_limit_date: Any) -> str:
        return f"shipping_limit:{order_id}:{item_id}:{str(shipping_limit_date).strip()}"

    @classmethod
    def build_payment_row_evidence(cls, order_id: str, sequential: Any, payment_type: str, payment_value: Any) -> str:
        # Chuẩn hóa giá trị số thực của payment_value về float string sạchẽ
        try:
            val_str = f"{float(payment_value):.2f}".rstrip("0").rstrip(".") if float(payment_value) == int(float(payment_value)) else f"{float(payment_value):.2f}"
            # Tuy nhiên trong dữ liệu Olist đôi khi giữ nguyên float, ta có thể dùng str() hoặc f"{float(payment_value):.2f}"
            # Cần tương thích với cả "183.29" hoặc "50"
            val_float = float(payment_value)
            val_repr = f"{val_float:.2f}"
        except Exception:
            val_repr = str(payment_value)
        return f"payment_row:{order_id}:{sequential}:{payment_type}:{val_repr}"

    @classmethod
    def is_valid_evidence_format(cls, evidence_id: str) -> bool:
        """
        Kiểm tra xem một chuỗi Evidence ID có khớp chính xác với 1 trong 5 định dạng hợp lệ hay không.
        Trả về True nếu đúng định dạng chuẩn, False nếu vi phạm cú pháp.
        """
        if not evidence_id or not isinstance(evidence_id, str):
            return False
        evidence_str = evidence_id.strip()
        for pattern in cls.REGEX_PATTERNS.values():
            if pattern.match(evidence_str):
                return True
        return False

    @classmethod
    def filter_valid_evidences(cls, evidence_list: List[str]) -> List[str]:
        """
        Lọc danh sách các Evidence IDs từ LLM, chỉ giữ lại những chuỗi hoàn toàn đúng định dạng chuẩn.
        Hàm này là chốt chặn (gatekeeper) của Verifier Agent nhằm triệt tiêu False Positives.
        """
        valid_list = []
        for ev in evidence_list:
            ev_clean = ev.strip()
            if cls.is_valid_evidence_format(ev_clean) and ev_clean not in valid_list:
                valid_list.append(ev_clean)
        return valid_list

    @classmethod
    def extract_evidences_for_issue(cls, issue: str, order_context: Dict[str, Any]) -> List[str]:
        """
        Tự động trích xuất các Evidence ID chuẩn xác từ cơ sở dữ liệu RAM theo lỗi (primary_issue).
        Đây là công cụ hỗ trợ Agent nhanh chóng có đầy đủ bằng chứng thuyết phục 100% không lo Hallucinations.
        """
        if not order_context.get("found") or not order_context.get("order"):
            return []

        evidences = []
        order = order_context["order"]
        order_id = order.get("order_id", "")
        items = order_context.get("items", [])
        payments = order_context.get("payments", [])

        # 1. canceled_order_paid & unavailable_order_paid: Cần bằng chứng status + các dòng payment
        if issue in ["canceled_order_paid", "unavailable_order_paid"]:
            if order.get("order_status"):
                evidences.append(cls.build_order_status_evidence(order_id, order["order_status"]))
            for p in payments:
                evidences.append(cls.build_payment_row_evidence(order_id, p.get("payment_sequential", 1), p.get("payment_type", ""), p.get("payment_value", 0.0)))
            return cls.filter_valid_evidences(evidences)

        # 2. late_delivery_seller & late_delivery_logistics: Cần timestamp giao, dự kiến, carrier, và shipping limit của item
        if issue in ["late_delivery_seller", "late_delivery_logistics", "unsupported_late_claim"]:
            for field in ["order_delivered_customer_date", "order_estimated_delivery_date", "order_delivered_carrier_date"]:
                val = order.get(field)
                if val and str(val) != "None":
                    evidences.append(cls.build_timestamp_evidence(order_id, field, val))
            for item in items:
                item_id = item.get("order_item_id", 1)
                seller_id = item.get("seller_id", "")
                limit_date = item.get("shipping_limit_date")
                if seller_id:
                    evidences.append(cls.build_item_seller_evidence(order_id, item_id, seller_id))
                if limit_date and str(limit_date) != "None":
                    evidences.append(cls.build_shipping_limit_evidence(order_id, item_id, limit_date))

        # 3. valid_split_payment & các lỗi tiền bạc: Thêm toàn bộ các bằng chứng payment
        if issue in ["valid_split_payment"] or not evidences:
            for p in payments:
                evidences.append(cls.build_payment_row_evidence(order_id, p.get("payment_sequential", 1), p.get("payment_type", ""), p.get("payment_value", 0.0)))

        return cls.filter_valid_evidences(evidences)
