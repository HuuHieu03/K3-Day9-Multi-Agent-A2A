import os
import json
from typing import Dict, Any
from src.coordinator import CoordinatorAgent, ISubAgent
from src.tracer import A2ATracer

# --- MOCK AGENTS FOR TESTING SEPARATION OF DUTIES & DEFENSE MECHANISMS ---

class MockSuccessfulAgent(ISubAgent):
    def __init__(self, name: str, return_data: Dict[str, Any]):
        self.name = name
        self.return_data = return_data

    def get_name(self) -> str:
        return self.name

    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.return_data

    def fallback(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.return_data

class MockRetryThenSuccessAgent(ISubAgent):
    """
    Sub-agent giả lập thất bại 2 lần đầu và chỉ thành công ở lần thử (retry) thứ 3.
    """
    def __init__(self, name: str, return_data: Dict[str, Any]):
        self.name = name
        self.return_data = return_data
        self.attempts = 0

    def get_name(self) -> str:
        return self.name

    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.attempts += 1
        if self.attempts < 3:
            raise ValueError(f"Simulated transient error on attempt {self.attempts}")
        return self.return_data

    def fallback(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.return_data

class MockFallbackRequiredAgent(ISubAgent):
    """
    Sub-agent giả lập thất bại TOÀN BỘ 3 lần retry và phải dùng đến Fallback deterministic.
    """
    def __init__(self, name: str, fallback_data: Dict[str, Any]):
        self.name = name
        self.fallback_data = fallback_data
        self.attempts = 0

    def get_name(self) -> str:
        return self.name

    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.attempts += 1
        raise ConnectionError(f"Simulated persistent LLM failure on attempt {self.attempts}")

    def fallback(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        print(f"[{self.name}] Executing safe deterministic fallback!")
        return self.fallback_data

class MockTotalFailureAgent(ISubAgent):
    """
    Sub-agent giả lập lỗi thảm họa: Cả Retry và Fallback đều thất bại, yêu cầu KHÔNG BỊA ĐẶT và phải Escalate.
    """
    def __init__(self, name: str):
        self.name = name

    def get_name(self) -> str:
        return self.name

    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise RuntimeError("Simulated Database Corruption - Execute Failed!")

    def fallback(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise RuntimeError("Simulated Backup Fallback Failed - Impossible to generate accurate answer!")


def test_coordinator_defense_layers():
    print("\n[Test] Starting CoordinatorAgent defense layers and fault isolation tests...")
    
    # Sử dụng log file riêng cho test
    tracer = A2ATracer(log_dir="logging", log_filename="test_trace.jsonl")
    tracer.clear()

    # =========================================================================
    # CASE 1: Test Retry then Success (Tầng 1: Retry thành công)
    # =========================================================================
    coord1 = CoordinatorAgent(tracer=tracer, max_retries=3)
    coord1.register_sub_agent("retrieve_data", MockSuccessfulAgent("DataRetrievalAgent", {"found": True, "order_id": "ORD01"}))
    coord1.register_sub_agent("evaluate_policy", MockRetryThenSuccessAgent("PolicySpecialistAgent", {"issue": "late_delivery_seller"}))
    coord1.register_sub_agent("verify_evidence", MockSuccessfulAgent("VerifierAgent", {"verified": True, "evidence_ids": ["order_status:ORD01:canceled"]}))

    res1 = coord1.process_claim_case({"case_id": "CASE_RETRY_TEST"})
    assert res1["_meta"]["status"] == "COMPLETED"
    print(" -> Level 1 (Retry up to 3 times & Recover): PASSED")

    # =========================================================================
    # CASE 2: Test Fallback Activation (Tầng 2: Hết lượt Retry -> Dùng Fallback)
    # =========================================================================
    coord2 = CoordinatorAgent(tracer=tracer, max_retries=3)
    coord2.register_sub_agent("retrieve_data", MockSuccessfulAgent("DataRetrievalAgent", {"found": True}))
    coord2.register_sub_agent("evaluate_policy", MockFallbackRequiredAgent("PolicySpecialistAgent", {"issue": "fallback_resolved"}))
    coord2.register_sub_agent("verify_evidence", MockSuccessfulAgent("VerifierAgent", {"verified": True}))

    res2 = coord2.process_claim_case({"case_id": "CASE_FALLBACK_TEST"})
    assert res2["_meta"]["status"] == "COMPLETED"
    assert res2["_meta"]["fallbacks_invoked"] == True
    print(" -> Level 2 (Exhaust Retries -> Activating Deterministic Fallback): PASSED")

    # =========================================================================
    # CASE 3: Test Human Escalation (Tầng 3: Tất cả thất bại -> Escalate, TUYỆT ĐỐI KHÔNG BỊA ĐẶT)
    # =========================================================================
    coord3 = CoordinatorAgent(tracer=tracer, max_retries=3)
    coord3.register_sub_agent("retrieve_data", MockSuccessfulAgent("DataRetrievalAgent", {"found": True}))
    coord3.register_sub_agent("evaluate_policy", MockTotalFailureAgent("FaultyPolicyAgent"))
    coord3.register_sub_agent("verify_evidence", MockSuccessfulAgent("VerifierAgent", {}))

    res3 = coord3.process_claim_case({"case_id": "CASE_CRITICAL_FAIL"})
    assert res3["case_status"] == "ESCALATED_TO_HUMAN", "Must escalate to human when fallback fails!"
    assert res3["error_diagnosis"]["responsible_agent"] == "FaultyPolicyAgent", "Must pinpoint EXACT agent causing failure!"
    assert res3["error_diagnosis"]["retries_exhausted"] == 3
    assert res3["error_diagnosis"]["fallback_attempted"] == True
    assert res3["recommended_refund_brl"] == 0.0, "Must NOT hallucinate financial refund on error!"
    print(" -> Level 3 (Critical Failure -> Pinpoint Agent Error & Escalate cleanly with ZERO Hallucination): PASSED")

    # =========================================================================
    # CASE 4: Verify A2ATracer Logs (Kiểm chứng ghi vết chính xác ra trace file)
    # =========================================================================
    log_file = "logging/test_trace.jsonl"
    assert os.path.exists(log_file), "Trace file must be created by A2ATracer!"
    
    with open(log_file, "r", encoding="utf-8") as f:
        lines = [json.loads(l) for l in f if l.strip()]
    
    # Verify we have traces representing normal execution, retries, fallbacks, and escalations
    statuses = {line["status"] for line in lines}
    assert "RETRY" in statuses, "Must trace RETRY attempts"
    assert "FALLBACK" in statuses, "Must trace FALLBACK activations"
    assert "ESCALATION_FINAL" in statuses, "Must trace ESCALATION to human"
    
    # Cleanup test trace
    if os.path.exists(log_file):
        os.remove(log_file)
        
    print(" -> A2A Tracing & Fault Isolation Logging: PASSED")
    print("[Test] CONGRATULATIONS: All Coordinator defense mechanisms and fault isolation criteria verified 100%!")

if __name__ == "__main__":
    test_coordinator_defense_layers()
