from src.policy_engine import ECPolicyV1Engine

def test_all_six_policy_rules():
    engine = ECPolicyV1Engine()
    print("\n[Test] Testing ECPolicyV1Engine against 6 business rules in strict priority order...")

    # 1. Test Rule 1: canceled_order_paid
    ctx_canceled = {
        "found": True,
        "order": {"order_status": "canceled"},
        "summary_math": {"payment_total_brl": 150.50, "item_total_brl": 135.50, "freight_total_brl": 15.00}
    }
    res_1 = engine.evaluate_case(ctx_canceled)
    assert res_1["primary_issue"] == "canceled_order_paid"
    assert res_1["case_status"] == "action_required"
    assert res_1["recommended_refund_brl"] == 150.50
    assert res_1["responsible_parties"][0]["party_id"] == "OLIST_PLATFORM"
    print(" -> Rule 1 (canceled_order_paid): PASSED")

    # 2. Test Rule 2: unavailable_order_paid
    ctx_unavail = {
        "found": True,
        "order": {"order_status": "unavailable"},
        "summary_math": {"payment_total_brl": 89.99, "item_total_brl": 79.99, "freight_total_brl": 10.00}
    }
    res_2 = engine.evaluate_case(ctx_unavail)
    assert res_2["primary_issue"] == "unavailable_order_paid"
    assert res_2["recommended_refund_brl"] == 89.99
    print(" -> Rule 2 (unavailable_order_paid): PASSED")

    # 3. Test Rule 3: late_delivery_seller
    ctx_late_seller = {
        "found": True,
        "order": {
            "order_status": "delivered",
            "order_delivered_customer_date": "2018-05-20 12:00:00",
            "order_estimated_delivery_date": "2018-05-15 00:00:00", # 5 days late
            "order_delivered_carrier_date": "2018-05-10 18:00:00"  # Carrier got it on May 10
        },
        "items": [
            {"seller_id": "seller_X", "shipping_limit_date": "2018-05-08 23:59:59"} # Limit was May 8 -> Seller late!
        ],
        "summary_math": {"payment_total_brl": 120.00, "item_total_brl": 100.00, "freight_total_brl": 20.00}
    }
    res_3 = engine.evaluate_case(ctx_late_seller)
    assert res_3["primary_issue"] == "late_delivery_seller"
    assert res_3["root_cause_code"] == "SELLER_HANDOFF_AFTER_LIMIT"
    assert res_3["responsible_parties"][0]["party_id"] == "seller_X"
    assert res_3["recommended_refund_brl"] == 20.00 # Refund freight only!
    print(" -> Rule 3 (late_delivery_seller): PASSED")

    # 4. Test Rule 4: late_delivery_logistics
    ctx_late_logistics = {
        "found": True,
        "order": {
            "order_status": "delivered",
            "order_delivered_customer_date": "2018-05-20 12:00:00",
            "order_estimated_delivery_date": "2018-05-15 00:00:00", # Late
            "order_delivered_carrier_date": "2018-05-07 15:00:00"  # Carrier got it May 07
        },
        "items": [
            {"seller_id": "seller_X", "shipping_limit_date": "2018-05-08 23:59:59"} # Limit May 08 -> Seller on time!
        ],
        "summary_math": {"payment_total_brl": 120.00, "item_total_brl": 100.00, "freight_total_brl": 20.00}
    }
    res_4 = engine.evaluate_case(ctx_late_logistics)
    assert res_4["primary_issue"] == "late_delivery_logistics"
    assert res_4["root_cause_code"] == "CARRIER_DELIVERED_AFTER_ESTIMATE"
    assert res_4["responsible_parties"][0]["party_id"] == "LOGISTICS_PROVIDER"
    assert res_4["recommended_refund_brl"] == 20.00
    print(" -> Rule 4 (late_delivery_logistics): PASSED")

    # 5. Test Rule 5: valid_split_payment
    ctx_split_pay = {
        "found": True,
        "order": {
            "order_status": "delivered",
            "order_delivered_customer_date": "2018-05-10 12:00:00", # On time
            "order_estimated_delivery_date": "2018-05-15 00:00:00"
        },
        "payments": [
            {"payment_sequential": 1, "payment_value": 50.00},
            {"payment_sequential": 2, "payment_value": 50.05} # Total 100.05, within 0.10 tolerance of 100.00
        ],
        "summary_math": {"payment_total_brl": 100.05, "item_total_brl": 80.00, "freight_total_brl": 20.00}
    }
    res_5 = engine.evaluate_case(ctx_split_pay)
    assert res_5["primary_issue"] == "valid_split_payment"
    assert res_5["case_status"] == "no_action"
    assert res_5["root_cause_code"] == "MULTIPLE_PAYMENTS_RECONCILED"
    assert res_5["recommended_refund_brl"] == 0.0
    assert len(res_5["responsible_parties"]) == 0
    print(" -> Rule 5 (valid_split_payment): PASSED")

    # 6. Test Rule 6: unsupported_late_claim
    ctx_unsupported = {
        "found": True,
        "order": {
            "order_status": "delivered",
            "order_delivered_customer_date": "2018-05-10 12:00:00", # On time!
            "order_estimated_delivery_date": "2018-05-15 00:00:00"
        },
        "payments": [{"payment_sequential": 1, "payment_value": 100.00}],
        "summary_math": {"payment_total_brl": 100.00, "item_total_brl": 80.00, "freight_total_brl": 20.00}
    }
    res_6 = engine.evaluate_case(ctx_unsupported)
    assert res_6["primary_issue"] == "unsupported_late_claim"
    assert res_6["case_status"] == "no_action"
    assert res_6["root_cause_code"] == "DELIVERY_WITHIN_ESTIMATE"
    assert res_6["recommended_refund_brl"] == 0.0
    print(" -> Rule 6 (unsupported_late_claim): PASSED")

    print("\n[Test] CONGRATULATIONS: All 6 business rules verified with 100% exactness!")

if __name__ == "__main__":
    test_all_six_policy_rules()
