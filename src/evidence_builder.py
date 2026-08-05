import re
from typing import List, Dict, Any

class EvidenceBuilder:
    """
    EvidenceBuilder - Xây dựng và kiểm duyệt danh sách Evidence ID chuẩn xác 100% theo Mục 5 README.md.
    Chỉ cho phép 5 khuôn định dạng hợp lệ duy nhất:
      1. order:<order_id>
      2. item:<order_id>:<order_item_id>
      3. payment:<order_id>:<payment_sequential>
      4. seller:<seller_id>
      5. policy:<root_cause_code>
    Tối ưu chống nhiễu (Zero Noise / Zero False Positive): Chỉ đưa vào những bằng chứng TRUNG TÂM
    làm căn cứ trực tiếp để phán xét quy tắc (ví dụ: lỗi giao trễ không cần payment evidence; 
    lỗi unsupported_late_claim chỉ dựa vào ngày trong order).
    """
    # Bộ 5 biểu thức chính quy (Regex) theo sát Mục 5
    VALID_REGEXES = [
        re.compile(r"^order:[a-zA-Z0-9_-]+$"),
        re.compile(r"^item:[a-zA-Z0-9_-]+:\w+$"),
        re.compile(r"^payment:[a-zA-Z0-9_-]+:\w+$"),
        re.compile(r"^seller:[a-zA-Z0-9_-]+$"),
        re.compile(r"^policy:[a-zA-Z0-9_]+$")
    ]

    @staticmethod
    def build_order_evidence(order_id: str) -> str:
        return f"order:{str(order_id).strip()}"

    @staticmethod
    def build_item_evidence(order_id: str, order_item_id: Any) -> str:
        return f"item:{str(order_id).strip()}:{str(order_item_id).strip()}"

    @staticmethod
    def build_payment_evidence(order_id: str, payment_sequential: Any) -> str:
        return f"payment:{str(order_id).strip()}:{str(payment_sequential).strip()}"

    @staticmethod
    def build_seller_evidence(seller_id: str) -> str:
        return f"seller:{str(seller_id).strip()}"

    @staticmethod
    def build_policy_evidence(root_cause_code: str) -> str:
        return f"policy:{str(root_cause_code).strip()}"

    @classmethod
    def is_valid_evidence(cls, evidence_str: str) -> bool:
        if not evidence_str or not isinstance(evidence_str, str):
            return False
        ev = evidence_str.strip()
        return any(regex.match(ev) is not None for regex in cls.VALID_REGEXES)

    @classmethod
    def filter_valid_evidences(cls, evidences: List[str]) -> List[str]:
        unique_list = []
        seen = set()
        for ev in evidences:
            ev_clean = str(ev).strip()
            if ev_clean not in seen and cls.is_valid_evidence(ev_clean):
                seen.add(ev_clean)
                unique_list.append(ev_clean)
        # Giới hạn tối đa 10 evidence IDs theo Mục 6 README
        return unique_list[:10]

    @classmethod
    def extract_evidences_for_issue(cls, primary_issue: str, order_context: Dict[str, Any], root_cause_code: str = "") -> List[str]:
        """
        Trích xuất bằng chứng theo đúng nguyên lý ZERO-NOISE (Không gây nhiễu, không bị phạt False Positive):
        Mỗi loại khiếu nại chỉ được thu hồi ĐÚNG các bằng chứng phục vụ cho việc suy luận ra kết quả.
        """
        evidences: List[str] = []
        if not order_context or not order_context.get("found"):
            return evidences

        # 1. Order evidence: Luôn có mặt vì là đối tượng trung tâm của khiếu nại
        order = order_context.get("order") or {}
        order_id = order.get("order_id")
        if order_id:
            evidences.append(cls.build_order_evidence(order_id))

        items = order_context.get("items", [])
        payments = order_context.get("payments", [])

        # 2. Trích xuất item evidences: CHỈ thêm vào khi quyết định phụ thuộc vào shipping_limit_date của item
        # hoặc đối soát chi phí item (late_delivery_seller, late_delivery_logistics, valid_split_payment).
        # Tuyệt đối KHÔNG nhét vào unsupported_late_claim (vì chỉ so sánh ngày delivered_customer_date và estimated_date trong bảng order).
        if primary_issue in ["late_delivery_seller", "late_delivery_logistics", "valid_split_payment"]:
            item_evs = []
            for item in items:
                item_id = item.get("order_item_id")
                if item_id and order_id:
                    item_evs.append(cls.build_item_evidence(order_id, item_id))
            item_evs.sort(key=lambda x: (len(x), x))
            evidences.extend(item_evs)

        # 3. Trích xuất payment evidences: CHỈ áp dụng cho lỗi về dòng tiền (hoàn tiền đơn hủy/hết hàng hoặc tách dòng thanh toán).
        # Tuyệt đối KHÔNG nhét payment vào khiếu nại giao trễ (late_delivery_seller/logistics) hay unsupported_late_claim để tránh nhiễu.
        if primary_issue in ["canceled_order_paid", "unavailable_order_paid", "valid_split_payment"]:
            pay_evs = []
            for pay in payments:
                pay_seq = pay.get("payment_sequential")
                if pay_seq is not None and order_id:
                    pay_evs.append(cls.build_payment_evidence(order_id, pay_seq))
            pay_evs.sort(key=lambda x: (len(x), x))
            evidences.extend(pay_evs)

        # 4. Trích xuất seller evidences: CHỈ thêm khi seller vi phạm hạn giao (late_delivery_seller).
        if primary_issue == "late_delivery_seller":
            seller_evs = []
            for item in items:
                s_id = item.get("seller_id")
                if s_id:
                    seller_evs.append(cls.build_seller_evidence(s_id))
            seller_evs.sort()
            evidences.extend(seller_evs)

        # 5. Policy evidence luôn đặt sau cùng
        if root_cause_code:
            evidences.append(cls.build_policy_evidence(root_cause_code))

        return cls.filter_valid_evidences(evidences)
