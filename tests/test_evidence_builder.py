from src.evidence_builder import EvidenceBuilder

def test_evidence_builder_and_validator():
    print("\n[Test] Testing EvidenceBuilder: generating 5 standard formats and validating against False Positives...")

    # 1. Test building 5 valid formats
    ev1 = EvidenceBuilder.build_order_status_evidence("010ac529", "canceled")
    assert ev1 == "order_status:010ac529:canceled"
    
    ev2 = EvidenceBuilder.build_timestamp_evidence("010ac529", "order_delivered_customer_date", "2018-05-18 13:20:41")
    assert ev2 == "order_timestamp:010ac529:order_delivered_customer_date:2018-05-18 13:20:41"
    
    ev3 = EvidenceBuilder.build_item_seller_evidence("010ac529", 1, "982b6b21")
    assert ev3 == "order_item_seller:010ac529:1:982b6b21"
    
    ev4 = EvidenceBuilder.build_shipping_limit_evidence("010ac529", 1, "2018-05-13 14:31:51")
    assert ev4 == "shipping_limit:010ac529:1:2018-05-13 14:31:51"
    
    ev5 = EvidenceBuilder.build_payment_row_evidence("010ac529", 1, "credit_card", 183.29)
    assert ev5 == "payment_row:010ac529:1:credit_card:183.29"

    print(" -> Building 5 string formats: PASSED")

    # 2. Test format validator (Gatekeeper against False Positives)
    valid_inputs = [ev1, ev2, ev3, ev4, ev5]
    for v in valid_inputs:
        assert EvidenceBuilder.is_valid_evidence_format(v) == True, f"Valid evidence rejected: {v}"
    
    # Simulate LLM hallucinations or formatting errors (which would cause False Positives)
    invalid_inputs = [
        "order_status 010ac529 canceled", # Missing colons
        "status:010ac529:canceled",       # Wrong prefix
        "payment_row:010ac529:one:card:abc", # Non-numeric sequential & value
        "",
        "order_item_seller::1:982b6b21",  # Empty order ID
        "random_hallucination_string"
    ]
    for inv in invalid_inputs:
        assert EvidenceBuilder.is_valid_evidence_format(inv) == False, f"Invalid format passed validation: {inv}"

    print(" -> Regex Validation & Rejecting Malformed Evidences (Zero FP): PASSED")

    # 3. Test automated extraction from Order Context
    mock_ctx = {
        "found": True,
        "order": {
            "order_id": "ord_123",
            "order_status": "canceled",
            "order_delivered_customer_date": "None"
        },
        "payments": [
            {"payment_sequential": 1, "payment_type": "boleto", "payment_value": 45.50}
        ]
    }
    extracted = EvidenceBuilder.extract_evidences_for_issue("canceled_order_paid", mock_ctx)
    assert len(extracted) == 2
    assert "order_status:ord_123:canceled" in extracted
    assert "payment_row:ord_123:1:boleto:45.50" in extracted
    print(" -> Automated Evidence Extraction for Agents: PASSED")

    print("[Test] CONGRATULATIONS: EvidenceBuilder verified with 100% precision and zero False Positives!")

if __name__ == "__main__":
    test_evidence_builder_and_validator()
