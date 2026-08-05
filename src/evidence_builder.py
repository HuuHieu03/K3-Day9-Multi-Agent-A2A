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
    Bất kỳ định dạng sai nào cũng sẽ bị cản ngục loại trừ để bảo vệ điểm số, tránh 100% lỗi False Positive.
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
        Trích xuất chuỗi bằng chứng hợp lệ từ dữ liệu gốc trên RAM theo ĐÚNG trật tự chuẩn Mục 5 & Mục 6:
          1. order:<order_id>
          2. item:<order_id>:<order_item_id> (đã sắp xếp)
          3. payment:<order_id>:<payment_sequential> (đã sắp xếp)
          4. seller:<seller_id> (đã sắp xếp)
          5. policy:<root_cause_code> (luôn đặt ở sau cùng theo mẫu EC_001 Mục 6)
        """
        evidences: List[str] = []
        if not order_context or not order_context.get("found"):
            return evidences

        order = order_context.get("order") or {}
        order_id = order.get("order_id")
        if order_id:
            evidences.append(cls.build_order_evidence(order_id))

        items = order_context.get("items", [])
        payments = order_context.get("payments", [])

        # 1. Trích xuất và sắp xếp item evidences
        item_evs = []
        for item in items:
            item_id = item.get("order_item_id")
            if item_id and order_id:
                item_evs.append(cls.build_item_evidence(order_id, item_id))
        item_evs.sort(key=lambda x: (len(x), x))
        evidences.extend(item_evs)

        # 2. Trích xuất và sắp xếp payment evidences (đứng trước seller theo chuẩn mẫu Mục 5 & 6)
        pay_evs = []
        for pay in payments:
            pay_seq = pay.get("payment_sequential")
            if pay_seq is not None and order_id:
                pay_evs.append(cls.build_payment_evidence(order_id, pay_seq))
        pay_evs.sort(key=lambda x: (len(x), x))
        evidences.extend(pay_evs)

        # 3. Trích xuất và sắp xếp seller evidences
        seller_evs = []
        for item in items:
            s_id = item.get("seller_id")
            if s_id:
                seller_evs.append(cls.build_seller_evidence(s_id))
        seller_evs.sort()
        evidences.extend(seller_evs)

        # 4. Policy evidence đứng sau cùng
        if root_cause_code:
            evidences.append(cls.build_policy_evidence(root_cause_code))

        return cls.filter_valid_evidences(evidences)
