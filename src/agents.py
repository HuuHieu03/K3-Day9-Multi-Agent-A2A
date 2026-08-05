from typing import Dict, Any, Optional
from src.coordinator import ISubAgent
from src.data_loader import OlistDataLoader
from src.policy_engine import ECPolicyV1Engine

class DataRetrievalAgent(ISubAgent):
    """
    Sub-Agent Chuyên Gia Tra Cứu Dữ Liệu (Data Retrieval Specialist).
    Trách nhiệm DUY NHẤT: Tra cứu toàn bộ thông tin đơn hàng từ RAM (qua OlistDataLoader).
    Tuyệt đối không phán đoán lỗi hay ra quyết định nghiệp vụ (tránh chồng việc).
    """
    def __init__(self, data_loader: OlistDataLoader):
        self.data_loader = data_loader
        self.name = "DataRetrievalAgent"

    def get_name(self) -> str:
        return self.name

    def _extract_order_id(self, payload: Dict[str, Any]) -> str:
        """
        Trích xuất mã đơn hàng từ yêu cầu khiếu nại đầu vào.
        """
        req = payload.get("customer_request", {})
        claimed_id = req.get("claimed_order_id")
        if not claimed_id:
            # Nếu cấu trúc JSON có khác biệt, cố gắng tìm order_id trực tiếp
            claimed_id = payload.get("claimed_order_id") or payload.get("order_id")
        if not claimed_id:
            raise ValueError("[DataRetrievalAgent] Cannot find 'claimed_order_id' in case input payload!")
        return str(claimed_id).strip()

    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        order_id = self._extract_order_id(payload)
        context = self.data_loader.get_order_context(order_id)
        
        if not context.get("found"):
            raise ValueError(f"[DataRetrievalAgent] Order ID '{order_id}' not found in Olist database!")
            
        return {
            "order_context": context,
            "original_request": payload.get("customer_request", payload)
        }

    def fallback(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Kịch bản Fallback an toàn: Trích xuất trực tiếp bằng truy vấn khóa đơn giản nhất.
        Nếu sau cả Retry và Fallback vẫn không tim thấy đơn hàng trong CSDL thật,
        BẮT BUỘC ném lỗi để Coordinator kích hoạt Tầng 3 (Escalate báo người dùng), tuyệt đối không suy đoán!
        """
        print(f"[{self.name}] Activating deterministic retrieval fallback...")
        order_id = self._extract_order_id(payload)
        context = self.data_loader.get_order_context(order_id)
        if not context.get("found"):
            raise RuntimeError(f"[DataRetrievalAgent] Fallback exhausted: Order ID '{order_id}' completely missing in database! Escalation to human operator required.")
        return {
            "order_context": context,
            "original_request": payload.get("customer_request", payload),
            "retrieved_via_fallback": True
        }


class PolicySpecialistAgent(ISubAgent):
    """
    Sub-Agent Chuyên Gia Quy Tắc Nghiệp Vụ (Policy Specialist).
    Trách nhiệm DUY NHẤT: Đánh giá dữ liệu theo 6 quy tắc ưu tiên của EC_POLICY_V1 (qua ECPolicyV1Engine).
    Tuyệt đối không tra cứu CSDL hoặc kiểm duyệt format evidence (tránh chồng việc).
    """
    def __init__(self, policy_engine: Optional[ECPolicyV1Engine] = None):
        self.policy_engine = policy_engine if policy_engine is not None else ECPolicyV1Engine()
        self.name = "PolicySpecialistAgent"

    def get_name(self) -> str:
        return self.name

    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        order_context = payload.get("order_context", {})
        if not order_context:
            raise ValueError("[PolicySpecialistAgent] Missing 'order_context' in execution payload!")
            
        decision = self.policy_engine.evaluate_case(order_context)
        return {
            "policy_decision": decision,
            "order_context": order_context
        }

    def fallback(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Kịch bản Fallback an toàn: Áp dụng trực tiếp engine toán học lập trình cứng theo thứ tự ưu tiên 1-6.
        """
        print(f"[{self.name}] Activating deterministic policy fallback...")
        order_context = payload.get("order_context", {})
        return {
            "policy_decision": self.policy_engine.evaluate_case(order_context),
            "order_context": order_context,
            "decided_via_fallback": True
        }
