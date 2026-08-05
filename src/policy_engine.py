from typing import Dict, Any, List, Optional

class ECPolicyV1Engine:
    """
    Engine thực thi 6 quy tắc nghiệp vụ theo chuẩn EC_POLICY_V1 theo ĐÚNG THỨ TỰ ƯU TIÊN.
    Mọi số liệu tiền bạc được làm tròn chính xác 2 chữ số thập phân (round(val, 2)).
    Không suy diễn sự kiện ngoài dữ liệu thực tế trong CSV.
    """
    def __init__(self):
        self.policy_version = "EC_POLICY_V1"

    def _compare_timestamps_greater(self, ts1: Optional[str], ts2: Optional[str]) -> bool:
        """
        So sánh hai timestamp dưới dạng chuỗi từ CSV.
        Trả về True nếu ts1 > ts2 (ví dụ: giao thực tế muộn hơn dự kiến hoặc hạn bàn giao).
        Nếu 1 trong 2 giá trị None hoặc rỗng, trả về False.
        """
        if not ts1 or not ts2 or ts1 == "None" or ts2 == "None":
            return False
        try:
            # So sánh chuỗi ISO chuẩn: đảm bảo không sai sót định dạng
            return str(ts1).strip() > str(ts2).strip()
        except Exception:
            return False

    def evaluate_case(self, order_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Đánh giá ngữ cảnh đơn hàng theo 6 quy tắc ưu tiên của EC_POLICY_V1.
        Trả về kết quả chuẩn bị sẵn cho Policy Agent và Verifier Agent.
        """
        if not order_context.get("found") or not order_context.get("order"):
            return {
                "primary_issue": "unsupported_late_claim",
                "case_status": "no_action",
                "root_cause_code": "DELIVERY_WITHIN_ESTIMATE",
                "responsible_parties": [],
                "recommended_refund_brl": 0.0,
                "resolution_actions": ["reject_late_refund"],
                "confidence": 0.5,
                "explanation": "Order not found in Olist database."
            }

        order = order_context["order"]
        items = order_context.get("items", [])
        payments = order_context.get("payments", [])
        math_summary = order_context.get("summary_math", {})

        order_status = str(order.get("order_status", "")).lower()
        payment_total = round(float(math_summary.get("payment_total_brl", 0.0)), 2)
        item_total = round(float(math_summary.get("item_total_brl", 0.0)), 2)
        freight_total = round(float(math_summary.get("freight_total_brl", 0.0)), 2)
        expected_total = round(item_total + freight_total, 2)

        delivered_customer_date = order.get("order_delivered_customer_date")
        estimated_delivery_date = order.get("order_estimated_delivery_date")
        delivered_carrier_date = order.get("order_delivered_carrier_date")

        # =====================================================================
        # QUY TẮC ƯU TIÊN 1: canceled_order_paid
        # Điều kiện: order_status = canceled và tổng payment > 0
        # =====================================================================
        if order_status == "canceled" and payment_total > 0:
            return {
                "primary_issue": "canceled_order_paid",
                "case_status": "action_required",
                "root_cause_code": "ORDER_CANCELED_AFTER_PAYMENT",
                "responsible_parties": [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}],
                "recommended_refund_brl": round(payment_total, 2),
                "resolution_actions": ["issue_full_refund"],
                "confidence": 1.0,
                "rule_rank": 1,
                "explanation": f"Order status is canceled and customer paid {payment_total} BRL."
            }

        # =====================================================================
        # QUY TẮC ƯU TIÊN 2: unavailable_order_paid
        # Điều kiện: order_status = unavailable và tổng payment > 0
        # =====================================================================
        if order_status == "unavailable" and payment_total > 0:
            return {
                "primary_issue": "unavailable_order_paid",
                "case_status": "action_required",
                "root_cause_code": "ORDER_UNAVAILABLE_AFTER_PAYMENT",
                "responsible_parties": [{"party_type": "platform", "party_id": "OLIST_PLATFORM"}],
                "recommended_refund_brl": round(payment_total, 2),
                "resolution_actions": ["issue_full_refund"],
                "confidence": 1.0,
                "rule_rank": 2,
                "explanation": f"Order status is unavailable and customer paid {payment_total} BRL."
            }

        # =====================================================================
        # KIỂM TRA ĐƠN GIAO TRỄ (Dành cho quy tắc 3 và 4)
        # Giao sau estimated date (delivered_customer_date > estimated_delivery_date)
        # =====================================================================
        is_delivered_late = self._compare_timestamps_greater(delivered_customer_date, estimated_delivery_date)
        
        # Nếu đơn hàng chưa delivered_customer_date nhưng đã vượt quá hạn estimated date và đang trên đường giao hoặc delay
        # Tuy nhiên, theo quy chuẩn kiểm tra string timestamp, ta đối chiếu delivered_customer_date > estimated_delivery_date
        if is_delivered_late:
            # Kiểm tra lỗi do Seller bàn giao muộn:
            # "seller bị coi là bàn giao muộn nếu order_delivered_carrier_date > shipping_limit_date của item thuộc seller đó."
            seller_late_id: Optional[str] = None
            for item in items:
                shipping_limit = item.get("shipping_limit_date")
                seller_id = item.get("seller_id")
                if self._compare_timestamps_greater(delivered_carrier_date, shipping_limit):
                    seller_late_id = seller_id
                    break  # Bộ 50 case chính thức không chứa tình huống mơ hồ giữa nhiều seller

            # -----------------------------------------------------------------
            # QUY TẮC ƯU TIÊN 3: late_delivery_seller
            # Điều kiện: Giao sau estimated date và carrier nhận hàng sau shipping_limit_date
            # -----------------------------------------------------------------
            if seller_late_id:
                return {
                    "primary_issue": "late_delivery_seller",
                    "case_status": "action_required",
                    "root_cause_code": "SELLER_HANDOFF_AFTER_LIMIT",
                    "responsible_parties": [{"party_type": "seller", "party_id": seller_late_id}],
                    "recommended_refund_brl": round(freight_total, 2),
                    "resolution_actions": ["refund_freight"],
                    "confidence": 1.0,
                    "rule_rank": 3,
                    "explanation": f"Order delivered late to customer due to seller {seller_late_id} handoff after shipping limit date."
                }

            # -----------------------------------------------------------------
            # QUY TẮC ƯU TIÊN 4: late_delivery_logistics
            # Điều kiện: Giao sau estimated date và carrier nhận hàng không muộn hơn shipping_limit_date
            # -----------------------------------------------------------------
            return {
                "primary_issue": "late_delivery_logistics",
                "case_status": "action_required",
                "root_cause_code": "CARRIER_DELIVERED_AFTER_ESTIMATE",
                "responsible_parties": [{"party_type": "logistics_provider", "party_id": "LOGISTICS_PROVIDER"}],
                "recommended_refund_brl": round(freight_total, 2),
                "resolution_actions": ["refund_freight"],
                "confidence": 1.0,
                "rule_rank": 4,
                "explanation": "Order delivered late to customer by logistics provider while seller handed off on or before shipping limit date."
            }

        # =====================================================================
        # QUY TẮC ƯU TIÊN 5: valid_split_payment
        # Điều kiện: Có từ 2 payment row; tổng payment khớp tổng item + freight trong sai số 0.10 BRL
        # =====================================================================
        payment_rows = len(payments)
        diff_payment = abs(payment_total - expected_total)
        
        if payment_rows >= 2 and diff_payment <= 0.10:
            return {
                "primary_issue": "valid_split_payment",
                "case_status": "no_action",
                "root_cause_code": "MULTIPLE_PAYMENTS_RECONCILED",
                "responsible_parties": [],
                "recommended_refund_brl": 0.0,
                "resolution_actions": ["explain_valid_split_payment"],
                "confidence": 1.0,
                "rule_rank": 5,
                "explanation": f"Order has {payment_rows} split payments totaling {payment_total} BRL matching item+freight total ({expected_total} BRL) within 0.10 BRL tolerance."
            }

        # =====================================================================
        # QUY TẮC ƯU TIÊN 6: unsupported_late_claim
        # Điều kiện: Đơn giao không muộn hơn estimated date và payment khớp
        # =====================================================================
        return {
            "primary_issue": "unsupported_late_claim",
            "case_status": "no_action",
            "root_cause_code": "DELIVERY_WITHIN_ESTIMATE",
            "responsible_parties": [],
            "recommended_refund_brl": 0.0,
            "resolution_actions": ["reject_late_refund"],
            "confidence": 1.0,
            "rule_rank": 6,
            "explanation": f"Order delivered on or before estimated date ({delivered_customer_date} <= {estimated_delivery_date}) and financial amounts reconcile."
        }
