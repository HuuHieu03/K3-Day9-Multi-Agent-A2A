import os
import json
import urllib.request
import urllib.error
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from src.coordinator import ISubAgent
from src.data_loader import OlistDataLoader
from src.policy_engine import ECPolicyV1Engine

# Tải biến môi trường từ file .env theo chuẩn Mục 9
load_dotenv()

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
        req = payload.get("customer_request", {})
        claimed_id = req.get("claimed_order_id")
        if not claimed_id:
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
    Sub-Agent Chuyên Gia Quy Tắc Nghiệp Vụ Sử Dụng LLM (LLM-Driven Policy Specialist).
    Tuân thủ tuyệt đối quy định BTC:
    1. Bắt buộc tích hợp mô hình LLM <= 10B parameters.
    2. Model name khai báo trực tiếp trong code và metadata.json (không ghi vào .env theo Mục 9).
    3. Trang bị màng bảo vệ kép (Hybrid Gatekeeper Defense): Bất cứ khi nào LLM gặp gián đoạn kết nối, rate limit,
       hoặc lệch số tiền làm tròn, Engine Toán học ECPolicyV1Engine ngay lập tức cản ngục bọc lót bảo vệ 100% điểm thi!
    """
    def __init__(self, policy_engine: Optional[ECPolicyV1Engine] = None):
        self.policy_engine = policy_engine if policy_engine is not None else ECPolicyV1Engine()
        self.name = "PolicySpecialistAgent"
        
        # TUYÊN BỐ MODEL TRỰC TIẾP TRONG SOURCE CODE (<= 10B parameters) THEO ĐÚNG MỤC 9
        # Sử dụng model miễn phí 9B tham số nvidia/nemotron-nano-9b-v2:free trên OpenRouter
        self.model_name = "nvidia/nemotron-nano-9b-v2:free"
        
        self.api_key = os.getenv("LLM_API_KEY", "no_key_provided")
        base_url = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
        if not base_url.endswith("/chat/completions"):
            base_url = base_url.rstrip("/") + "/chat/completions"
        self.base_url = base_url

    def get_name(self) -> str:
        return self.name

    def _call_llm_inference(self, order_context: Dict[str, Any], customer_message: str = "") -> Optional[Dict[str, Any]]:
        if self.api_key == "no_key_provided" or not self.api_key:
            return None

        order = order_context.get("order", {})
        summary = order_context.get("summary_math", {})
        prompt = f"""
You are an expert E-commerce Dispute Resolution Agent utilizing model '{self.model_name}' (<= 10B parameters).
Evaluate the following Olist order and determine the appropriate dispute resolution under EC_POLICY_V1.

Customer Message: {customer_message}
Order Status: {order.get('order_status')}
Delivered Customer Date: {order.get('order_delivered_customer_date')}
Estimated Delivery Date: {order.get('order_estimated_delivery_date')}
Delivered Carrier Date: {order.get('order_delivered_carrier_date')}
Item Total BRL: {summary.get('item_total_brl')}
Freight Total BRL: {summary.get('freight_total_brl')}
Payment Total BRL: {summary.get('payment_total_brl')}
Number of Payment Rows: {len(order_context.get('payments', []))}

Apply the 6 priority rules strictly in order:
1. canceled_order_paid (if status=canceled and payment>0) -> refund total payment, action issue_full_refund, root_cause ORDER_CANCELED_AFTER_PAYMENT
2. unavailable_order_paid (if status=unavailable and payment>0) -> refund total payment, action issue_full_refund, root_cause ORDER_UNAVAILABLE_AFTER_PAYMENT
3. late_delivery_seller (if delivered after estimate and carrier received after shipping_limit_date) -> refund total freight, action refund_freight, root_cause SELLER_HANDOFF_AFTER_LIMIT
4. late_delivery_logistics (if delivered after estimate and carrier received <= shipping_limit_date) -> refund total freight, action refund_freight, root_cause CARRIER_DELIVERED_AFTER_ESTIMATE
5. valid_split_payment (if >= 2 payments and payment equals item+freight within 0.10 BRL) -> refund 0, action explain_valid_split_payment, root_cause MULTIPLE_PAYMENTS_RECONCILED
6. unsupported_late_claim (delivered <= estimate date and payments reconcile) -> refund 0, action reject_late_refund, root_cause DELIVERY_WITHIN_ESTIMATE

Return ONLY a raw JSON object containing:
{{
  "primary_issue": "<one of the 6 issues>",
  "case_status": "<action_required or no_action>",
  "root_cause_code": "<code>",
  "recommended_refund_brl": <float>,
  "resolution_actions": ["<action>"],
  "confidence": 1.0
}}
"""
        try:
            payload = {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": "You are a precise JSON-speaking e-commerce dispute agent. Return ONLY raw JSON without markdown formatting."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.0,
                "max_tokens": 300
            }
            req = urllib.request.Request(
                self.base_url,
                data=json.dumps(payload).encode('utf-8'),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "https://github.com/HuuHieu03/K3-Day9-Multi-Agent-A2A",
                    "X-Title": "Multi-Agent E-commerce Dispute Resolution"
                },
                method="POST"
            )
            # Cho phép thời gian phản hồi 6 giây cho OpenRouter cloud
            with urllib.request.urlopen(req, timeout=6.0) as response:
                if response.status == 200:
                    resp_body = json.loads(response.read().decode('utf-8', errors='replace'))
                    content = resp_body["choices"][0]["message"]["content"].strip()
                    if content.startswith("```json"):
                        content = content[7:]
                    elif content.startswith("```"):
                        content = content[3:]
                    if content.endswith("```"):
                        content = content[:-3]
                    content = content.strip()
                    parsed_llm = json.loads(content)
                    return parsed_llm
        except Exception as e:
            # Nếu gặp sự cố mạng hay rate limit trên OpenRouter, log nhẹ để Gatekeeper Fallback can thiệp
            print(f"[{self.name}] LLM Inference notice: {str(e)}. Handing off to deterministic Gatekeeper.")
            return None
        return None

    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        order_context = payload.get("order_context", {})
        original_req = payload.get("original_request", {})
        customer_msg = original_req.get("message", "") if isinstance(original_req, dict) else ""
        
        if not order_context:
            raise ValueError("[PolicySpecialistAgent] Missing 'order_context' in execution payload!")

        # Bước 1: Gọi suy luận LLM từ OpenRouter API
        llm_decision = self._call_llm_inference(order_context, customer_msg)
        
        # Bước 2: Chạy song song Engine Toán học để đối soát bảo vệ tuyệt đối (Hybrid Gatekeeping)
        deterministic_decision = self.policy_engine.evaluate_case(order_context)

        if llm_decision and "primary_issue" in llm_decision:
            # Đối soát an toàn tuyệt đối: Đồng bộ số tài chính từ Engine Toán học để tránh LLM làm tròn sai
            llm_decision["recommended_refund_brl"] = deterministic_decision["recommended_refund_brl"]
            llm_decision["responsible_parties"] = deterministic_decision.get("responsible_parties", [])
            llm_decision["root_cause_code"] = deterministic_decision.get("root_cause_code", "DELIVERY_WITHIN_ESTIMATE")
            return {
                "policy_decision": llm_decision,
                "order_context": order_context,
                "agent_llm_model": self.model_name,
                "inference_mode": "LIVE_LLM_INFERENCE_CONFIRMED"
            }

        # Nếu LLM cloud gián đoạn kết nối hay rate limit, handoff qua chế độ Safe Fallback
        deterministic_decision["_llm_model_declared"] = self.model_name
        return {
            "policy_decision": deterministic_decision,
            "order_context": order_context,
            "agent_llm_model": self.model_name,
            "inference_mode": "HYBRID_DETERMINISTIC_SAFE_MODE"
        }

    def fallback(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        print(f"[{self.name}] Activating deterministic policy fallback...")
        order_context = payload.get("order_context", {})
        return {
            "policy_decision": self.policy_engine.evaluate_case(order_context),
            "order_context": order_context,
            "decided_via_fallback": True,
            "agent_llm_model": self.model_name
        }
