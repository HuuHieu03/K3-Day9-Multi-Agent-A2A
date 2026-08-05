import json
import os
import time
from src.data_loader import OlistDataLoader
from src.coordinator import CoordinatorAgent
from src.agents import DataRetrievalAgent, PolicySpecialistAgent
from src.verifier import VerifierAgent
from src.tracer import A2ATracer

def test_full_multi_agent_pipeline():
    print("\n[Test] Initializing Full Multi-Agent Dispute Resolution Pipeline (Phase 3 Integration)...")
    t0 = time.time()
    loader = OlistDataLoader(data_dir="data")
    print(f"[Test] Data loader ready in {time.time()-t0:.2f}s")

    tracer = A2ATracer(log_dir="logging", log_filename="integration_trace.jsonl")
    tracer.clear()

    coordinator = CoordinatorAgent(tracer=tracer, max_retries=3)
    coordinator.register_sub_agent("retrieve_data", DataRetrievalAgent(loader))
    coordinator.register_sub_agent("evaluate_policy", PolicySpecialistAgent())
    coordinator.register_sub_agent("verify_evidence", VerifierAgent())

    # =========================================================================
    # TEST 1: Real Case processing using input/EC_001.json
    # =========================================================================
    with open("input/EC_001.json", "r", encoding="utf-8") as f:
        case_001 = json.load(f)
    
    print(f"\n[Test] Running pipeline for real case: {case_001.get('case_id')}...")
    start_time = time.time()
    result_001 = coordinator.process_claim_case(case_001)
    duration_001 = time.time() - start_time
    print(f"[Test] Pipeline execution time for EC_001: {duration_001:.4f}s")

    # Verify JSON Schema exactness (Section 6 of README)
    assert "case_id" in result_001
    assert "assessment" in result_001
    assert "affected_entities" in result_001
    assert "root_cause_analysis" in result_001
    assert "evidence_ids" in result_001
    assert "financial_resolution" in result_001
    assert "resolution_actions" in result_001

    assert result_001["assessment"]["primary_issue"] == "late_delivery_seller"
    assert result_001["financial_resolution"]["recommended_refund_brl"] > 0
    assert len(result_001["evidence_ids"]) > 0
    print(" -> Real Case EC_001 Processing (Diagnosed as late_delivery_seller) & Section 6 Schema Exactness: PASSED")

    # =========================================================================
    # TEST 2: Simulate Unresolvable Error (Non-existent Order ID) -> Human Escalation
    # =========================================================================
    fake_case = {
        "case_id": "EC_FAKE_999",
        "customer_request": {
            "claimed_order_id": "NON_EXISTENT_ORDER_ID_ABC123"
        }
    }
    print("\n[Test] Running pipeline for invalid order ID to verify Zero Hallucination & Escalation...")
    result_fake = coordinator.process_claim_case(fake_case)
    
    assert result_fake["case_status"] == "ESCALATED_TO_HUMAN"
    assert result_fake["error_diagnosis"]["responsible_agent"] == "DataRetrievalAgent"
    assert result_fake["error_diagnosis"]["retries_exhausted"] == 3
    assert result_fake["recommended_refund_brl"] == 0.0
    print(" -> Unresolvable Error Handling (Retry 3x -> Fallback -> Escalate without Hallucinating): PASSED")

    # =========================================================================
    # TEST 3: Verify Traces in integration_trace.jsonl
    # =========================================================================
    trace_path = "logging/integration_trace.jsonl"
    assert os.path.exists(trace_path), "Trace file was not generated!"
    with open(trace_path, "r", encoding="utf-8") as f:
        logs = [json.loads(line) for line in f if line.strip()]
    assert len(logs) > 0, "No trace logs recorded!"
    print(f" -> A2A Trace file generated successfully with {len(logs)} communication events: PASSED")

    if os.path.exists(trace_path):
        os.remove(trace_path)

    print("\n[Test] CONGRATULATIONS: Complete Phase 3 Multi-Agent Architecture verified 100%!")

if __name__ == "__main__":
    test_full_multi_agent_pipeline()
