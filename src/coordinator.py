import time
import traceback
from typing import Dict, Any, List, Optional, Callable, Protocol
from src.models import AgentMessage, AgentResult
from src.tracer import A2ATracer

# Định nghĩa Interface (Giao thức) chuẩn cho các Sub-Agent nhằm ngăn chặn chồng chéo nhiệm vụ
class ISubAgent(Protocol):
    def get_name(self) -> str: ...
    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]: ...
    def fallback(self, payload: Dict[str, Any]) -> Dict[str, Any]: ...

class CoordinatorAgent:
    """
    Coordinator Agent - "Nhạc trưởng" điều phối luồng xử lý khiếu nại Multi-Agent.
    Tuân thủ tuyệt đối các tiêu chí:
    1. Phân định vai trò rõ ràng, không lấn át việc tra cứu/phác thảo/lọc chứng cứ của Sub-Agent.
    2. Cô lập lỗi (Fault Isolation) - Ghi nhận đích danh Agent gây lỗi và dòng lệnh cụ thể qua A2ATracer.
    3. Cơ chế Retry có trần (mặc định tối đa 3 lần).
    4. Kịch bản Fallback - Khi hết lượt retry, lập tức kích hoạt bộ chuyển đổi ngầm (Deterministic Fallback).
    5. Cơ chế Báo Cáo Người Dùng (Human Escalation) - Nếu ngay cả fallback thất bại, TUYỆT ĐỐI KHÔNG BỊA ĐẶT (Hallucinate/False Positive) mà xuất cảnh báo cần con người can thiệp.
    """
    def __init__(self, tracer: Optional[A2ATracer] = None, max_retries: int = 3):
        self.tracer = tracer if tracer is not None else A2ATracer()
        self.max_retries = max_retries
        
        # Registry lưu trữ các Sub-Agent được ủy quyền cho từng bước
        # Bước 1: retrieve_data -> DataRetrievalAgent
        # Bước 2: evaluate_policy -> PolicySpecialistAgent
        # Bước 3: verify_evidence -> VerifierAgent
        self.sub_agents: Dict[str, ISubAgent] = {}

    def register_sub_agent(self, step_name: str, agent: ISubAgent):
        """
        Đăng ký một Sub-Agent chịu trách nhiệm DUY NHẤT cho một bước cụ thể trong luồng.
        """
        self.sub_agents[step_name] = agent

    def _log_step(self, trace_id: str, step_id: int, receiver: str, action: str, 
                  payload: Dict[str, Any], status: str = "SUCCESS", error: Optional[str] = None):
        """
        Hàm phụ trợ ghi vết sang A2ATracer nhằm bảo đảm minh bạch và định vị lỗi tức khắc.
        """
        msg = AgentMessage(
            trace_id=trace_id,
            step_id=step_id,
            sender="CoordinatorAgent",
            receiver=receiver,
            action=action,
            payload=payload,
            status=status,
            error_details=error
        )
        self.tracer.record(msg)

    def _execute_agent_step(self, trace_id: str, step_id: int, step_name: str, payload: Dict[str, Any]) -> AgentResult:
        """
        Thực thi một bước với Sub-Agent đi kèm cơ chế 3 TẦNG BẢO MỆNH:
        Tầng 1: Chạy bình thường kèm Retry có trần (max_retries).
        Tầng 2: Deterministic Fallback (Khi hết Quý Nhất, chạy kịch bản an toàn của Sub-Agent).
        Tầng 3: Escalation (Khẩn cấp báo cáo con người, từ chối đưa thông tin giả/bị động).
        """
        agent = self.sub_agents.get(step_name)
        if not agent:
            error_msg = f"No Sub-Agent registered for step '{step_name}'"
            self._log_step(trace_id, step_id, step_name, "EXECUTE", payload, status="FAIL_ESCALATE", error=error_msg)
            return AgentResult(success=False, error_message=error_msg, error_agent=f"CoordinatorAgent (Missing {step_name})", escalated_to_human=True)

        agent_name = agent.get_name()
        attempts = 0
        last_error = ""

        # =====================================================================
        # TẦNG 1: THỰC THI & RETRY CÓ TRẦN (TỐI ĐA MAX_RETRIES LẦN)
        # =====================================================================
        while attempts < self.max_retries:
            attempts += 1
            try:
                self._log_step(trace_id, step_id, agent_name, f"EXECUTE_ATTEMPT_{attempts}", payload)
                output = agent.execute(payload)
                self._log_step(trace_id, step_id, agent_name, "EXECUTE_SUCCESS", output, status="SUCCESS")
                return AgentResult(success=True, data=output, retries_exhausted=attempts-1)
            except Exception as e:
                last_error = f"{str(e)} | Trace: {traceback.format_exc(limit=1).strip()}"
                status_str = "RETRY" if attempts < self.max_retries else "RETRY_EXHAUSTED"
                self._log_step(trace_id, step_id, agent_name, f"EXECUTE_FAIL_ATTEMPT_{attempts}", payload, status=status_str, error=last_error)

        print(f"[CoordinatorAgent] '{agent_name}' failed after {self.max_retries} retries. Activating FALLBACK...")

        # =====================================================================
        # TẦNG 2: DETERMINISTIC FALLBACK (PHƯƠNG ÁN TIẾP THEO KHI RETRY THẤT BẠI)
        # =====================================================================
        try:
            self._log_step(trace_id, step_id, agent_name, "ACTIVATE_FALLBACK", payload, status="FALLBACK")
            fallback_output = agent.fallback(payload)
            self._log_step(trace_id, step_id, agent_name, "FALLBACK_SUCCESS", fallback_output, status="SUCCESS_VIA_FALLBACK")
            return AgentResult(success=True, data=fallback_output, fallback_used=True, retries_exhausted=self.max_retries)
        except Exception as fb_error:
            fb_err_msg = f"Fallback also failed: {str(fb_error)} | Original error: {last_error}"
            self._log_step(trace_id, step_id, agent_name, "FALLBACK_FAILED", payload, status="FAIL_ESCALATE", error=fb_err_msg)

            # =================================================================
            # TẦNG 3: ESCALATE VÀ BÁO VỀ NGƯỜI DÙNG - KHÔNG BỊA ĐẶT DỮ LIỆU
            # =================================================================
            print(f"[CoordinatorAgent] CRITICAL: Fallback for '{agent_name}' failed. Escalating to human operator.")
            return AgentResult(
                success=False,
                error_message=fb_err_msg,
                error_agent=agent_name,
                fallback_used=True,
                escalated_to_human=True,
                retries_exhausted=self.max_retries
            )

    def process_claim_case(self, case_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Điều phối toàn bộ quy trình 3 bước xử lý một ca khiếu nại (Claim Case):
        Bước 1: Data Retrieval (Tra cứu dữ liệu)
        Bước 2: Policy Evaluation (Đánh giá quy tắc)
        Bước 3: Evidence & Gatekeeper Verification (Kiểm duyệt bằng chứng)
        """
        case_id = case_input.get("case_id", f"case_{int(time.time()*1000)}")
        trace_id = f"trace_{case_id}"

        print(f"\n[CoordinatorAgent] Starting processing for Case: '{case_id}' | Trace ID: '{trace_id}'")
        self._log_step(trace_id, 0, "CoordinatorAgent", "INIT_CASE", case_input, status="START")

        # -----------------------------------------------------------------
        # Bước 1: Tra Cứu Dữ Liệu (Data Retrieval)
        # -----------------------------------------------------------------
        step1_res = self._execute_agent_step(trace_id, 1, "retrieve_data", case_input)
        if not step1_res.success or step1_res.escalated_to_human:
            return self._build_escalation_report(case_id, trace_id, 1, step1_res)

        retrieved_data = step1_res.data or {}

        # -----------------------------------------------------------------
        # Bước 2: Đánh Giá Quy Tắc Nghiệp Vụ (Policy Evaluation)
        # -----------------------------------------------------------------
        step2_res = self._execute_agent_step(trace_id, 2, "evaluate_policy", retrieved_data)
        if not step2_res.success or step2_res.escalated_to_human:
            return self._build_escalation_report(case_id, trace_id, 2, step2_res)

        policy_decision = step2_res.data or {}

        # -----------------------------------------------------------------
        # Bước 3: Kiểm Duyệt Bằng Chứng & False Positive Gatekeeping
        # -----------------------------------------------------------------
        verification_payload = {
            "case_input": case_input,
            "retrieved_data": retrieved_data,
            "policy_decision": policy_decision
        }
        step3_res = self._execute_agent_step(trace_id, 3, "verify_evidence", verification_payload)
        if not step3_res.success or step3_res.escalated_to_human:
            return self._build_escalation_report(case_id, trace_id, 3, step3_res)

        final_output = step3_res.data or {}

        # Hoàn tất luồng thành công
        self._log_step(trace_id, 4, "CoordinatorAgent", "FINALIZE_CASE", final_output, status="COMPLETED")
        print(f"[CoordinatorAgent] Successfully processed Case '{case_id}' (Fallback Used: {step1_res.fallback_used or step2_res.fallback_used or step3_res.fallback_used})")
        
        # Gắn siêu dữ liệu theo dõi về tình trạng chạy
        final_output["_meta"] = {
            "trace_id": trace_id,
            "status": "COMPLETED",
            "fallbacks_invoked": any([step1_res.fallback_used, step2_res.fallback_used, step3_res.fallback_used])
        }
        return final_output

    def _build_escalation_report(self, case_id: str, trace_id: str, failed_step: int, res: AgentResult) -> Dict[str, Any]:
        """
        Xây dựng báo cáo Escalation gửi trực tiếp về Người Dùng khi hệ thống gặp lỗi bất khả kháng,
        đáp ứng yêu cầu TUYỆT ĐỐI KHÔNG BỊA ĐẶT hay xuất ra thông tin sai lệch.
        """
        error_report = {
            "case_id": case_id,
            "case_status": "ESCALATED_TO_HUMAN",
            "error_diagnosis": {
                "trace_id": trace_id,
                "failed_step": failed_step,
                "responsible_agent": res.error_agent or "Unknown",
                "error_message": res.error_message or "Unknown exception occurred",
                "retries_exhausted": res.retries_exhausted,
                "fallback_attempted": res.fallback_used
            },
            "explanation": f"System encountered critical failure at agent '{res.error_agent}'. All {res.retries_exhausted} retries and automated fallback failed. Case escalated to human operator to prevent false positives and inaccurate output.",
            "recommended_refund_brl": 0.0,
            "resolution_actions": ["escalate_for_human_review"]
        }
        self._log_step(trace_id, failed_step, "CoordinatorAgent", "ESCALATE_TO_HUMAN", error_report, status="ESCALATION_FINAL", error=res.error_message)
        return error_report
