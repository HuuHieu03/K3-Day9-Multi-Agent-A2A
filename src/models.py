from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
import time

@dataclass
class AgentMessage:
    """
    Cấu trúc tin nhắn chuẩn cho giao tiếp giữa các Agent (Agent-to-Agent / A2A Protocol).
    Giúp phân định rõ ràng trách nhiệm, theo dõi vết (tracing), và xác định chính xác nguồn gốc lỗi.
    """
    trace_id: str                  # Mã theo dõi của luồng xử lý đơn hàng/khiếu nại
    step_id: int                   # Số thứ tự bước xử lý trong chuỗi quy trình
    sender: str                    # Agent gửi (vd: CoordinatorAgent, DataRetrievalAgent)
    receiver: str                  # Agent nhận
    action: str                    # Hành động (vd: RETRIEVE_DATA, EVALUATE_POLICY, VERIFY_EVIDENCE)
    payload: Dict[str, Any]        # Dữ liệu truyền tải
    status: str = "SUCCESS"        # Trang thái: SUCCESS, RETRY, FALLBACK, ESCALATION_REQUIRED
    error_details: Optional[str] = None # Chi tiết lỗi (nếu có) để định vị chính xác vị trí phát sinh lỗi
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class AgentResult:
    """
    Kết quả trả về của một Agent sau khi thực hiện tác vụ (có hỗ trợ cơ chế lỗi & escalate).
    """
    success: bool
    data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    error_agent: Optional[str] = None
    fallback_used: bool = False
    escalated_to_human: bool = False
    retries_exhausted: int = 0
