import os
import json
from typing import List, Dict, Any
from src.models import AgentMessage

class A2ATracer:
    """
    Hệ thống ghi vết tin nhắn giữa các Agent (Agent-to-Agent Tracing).
    Đảm bảo tính minh bạch, hỗ trợ định vị chính xác Agent và chuỗi thao tác nào gây rò rỉ lỗi,
    và tự động ghi xuất ra file logging/trace.jsonl theo yêu cầu của dự án.
    """
    def __init__(self, log_dir: str = "logging", log_filename: str = "trace.jsonl"):
        self.log_dir = log_dir
        self.log_filepath = os.path.join(self.log_dir, log_filename)
        self.trace_buffer: List[Dict[str, Any]] = []
        
        # Đảm bảo thư mục lưu trữ log được khởi tạo sẵn sàng
        os.makedirs(self.log_dir, exist_ok=True)

    def record(self, message: AgentMessage) -> None:
        """
        Ghi lại một sự kiện giao tiếp/xử lý của Agent vào bộ nhớ và append thẳng ra file trace.jsonl.
        """
        data = message.to_dict()
        self.trace_buffer.append(data)
        
        # Ghi trực tiếp dưới dạng JSON Lines (mỗi sự kiện là 1 chuỗi JSON trên 1 dòng)
        try:
            with open(self.log_filepath, "a", encoding="utf-8") as f:
                f.write(json.dumps(data, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[A2ATracer] Warning: Failed to write trace to file: {e}")

    def get_traces_by_id(self, trace_id: str) -> List[Dict[str, Any]]:
        """
        Trích xuất toàn bộ lịch sử thao tác của một luồng khiếu nại (theo trace_id).
        """
        return [msg for msg in self.trace_buffer if msg.get("trace_id") == trace_id]

    def clear(self) -> None:
        """
        Xóa buffer và reset file trace (sử dụng khi khởi tạo phiên chạy mới hoặc test).
        """
        self.trace_buffer.clear()
        if os.path.exists(self.log_filepath):
            try:
                open(self.log_filepath, "w", encoding="utf-8").close()
            except Exception:
                pass
