from typing import Dict, Any, List
from src.coordinator import ISubAgent
from src.evidence_builder import EvidenceBuilder

class VerifierAgent(ISubAgent):
    """
    Sub-Agent Chuyên Gia Kiểm Duyệt (Gatekeeper & Verifier Specialist).
    Trách nhiệm DUY NHẤT:
    1. Kiểm duyệt bằng chứng bằng Regex Validator nhằm chặn đứng 100% rủi ro False Positive (FP).
    2. Xác minh số liệu tài chính làm tròn 2 chữ số thập phân, không vượt quá tổng số tiền khách đã nộp.
    3. Chuẩn hóa đầu ra thành cấu trúc JSON ĐÚNG CHUẨN Mục 5 của đề bài thi.
    """
    def __init__(self):
        self.name = "VerifierAgent"

    def get_name(self) -> str:
        return self.name

    def _verify_and_build_output(self, payload: Dict[str, Any], is_fallback: bool = False) -> Dict[str, Any]:
        case_input = payload.get("case_input", {})
        retrieved_wrapper = payload.get("retrieved_data", {})
        decision_wrapper = payload.get("policy_decision", {})

        order_context = retrieved_wrapper.get("order_context", {})
        decision = decision_wrapper.get("policy_decision", {})

        case_id = case_input.get("case_id", "UNKNOWN_CASE")
        primary_issue = decision.get("primary_issue", "unsupported_late_claim")
        case_status = decision.get("case_status", "no_action")
        root_cause_code = decision.get("root_cause_code", "DELIVERY_WITHIN_ESTIMATE")
        responsible_parties = decision.get("responsible_parties", [])
        recommended_refund = round(float(decision.get("recommended_refund_brl", 0.0)), 2)
        actions = decision.get("resolution_actions", ["reject_late_refund"])
        explanation = decision.get("explanation", "Verified policy execution.")

        # Gatekeeper Check 1: Đảm bảo số tiền hoàn trả hợp lệ 2 số thập phân và không vượt quá tổng thanh toán
        summary_math = order_context.get("summary_math", {})
        max_payment = round(float(summary_math.get("payment_total_brl", 9999999.0)), 2)
        if recommended_refund > max_payment and max_payment > 0:
            print(f"[{self.name}] WARNING: Recommended refund ({recommended_refund}) > total paid ({max_payment}). Capping to max_payment!")
            recommended_refund = max_payment

        # Gatekeeper Check 2: Trích xuất và lọc bằng chứng an toàn tuyệt đối qua EvidenceBuilder (Loại 100% FP)
        raw_evidences = EvidenceBuilder.extract_evidences_for_issue(primary_issue, order_context)
        valid_evidences = EvidenceBuilder.filter_valid_evidences(raw_evidences)

        # Gatekeeper Check 3: Chuẩn hóa toàn diện output theo cấu trúc chuẩn JSON Mục 5 của README
        verified_output = {
            "case_id": case_id,
            "policy_version": "EC_POLICY_V1",
            "assessment": {
                "primary_issue": primary_issue,
                "case_status": case_status,
                "root_cause": {
                    "code": root_cause_code,
                    "responsible_parties": responsible_parties
                }
            },
            "resolution": {
                "recommended_refund_brl": round(recommended_refund, 2),
                "actions": actions,
                "explanation": explanation
            },
            "evidence": {
                "evidence_ids": valid_evidences
            }
        }

        if is_fallback:
            verified_output["_verifier_fallback"] = True

        return verified_output

    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._verify_and_build_output(payload, is_fallback=False)

    def fallback(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        print(f"[{self.name}] Activating deterministic gatekeeper fallback...")
        return self._verify_and_build_output(payload, is_fallback=True)
