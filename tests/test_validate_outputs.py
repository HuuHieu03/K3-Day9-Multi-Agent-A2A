import os
import json
import glob
import re

def test_validate_all_50_output_files():
    print("\n[Test] Starting thorough Section 6 schema and Section 5 regex validation for 50 output files...")
    
    output_files = sorted(glob.glob("output/EC_*.json"))
    assert len(output_files) == 50, f"Expected exactly 50 output files, found {len(output_files)}!"

    valid_evidence_regexes = [
        re.compile(r"^order:[a-zA-Z0-9_-]+$"),
        re.compile(r"^item:[a-zA-Z0-9_-]+:\w+$"),
        re.compile(r"^payment:[a-zA-Z0-9_-]+:\w+$"),
        re.compile(r"^seller:[a-zA-Z0-9_-]+$"),
        re.compile(r"^policy:[a-zA-Z0-9_]+$")
    ]

    for file_path in output_files:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 1. Required Top-Level Schema (Mục 6 README)
        assert "case_id" in data, f"Missing 'case_id' in {file_path}"
        assert "assessment" in data, f"Missing 'assessment' in {file_path}"
        assert "affected_entities" in data, f"Missing 'affected_entities' in {file_path} - Hard Gate hazard!"
        assert "root_cause_analysis" in data, f"Missing 'root_cause_analysis' in {file_path} - Hard Gate hazard!"
        assert "evidence_ids" in data, f"Missing 'evidence_ids' in {file_path} - Hard Gate hazard!"
        assert "financial_resolution" in data, f"Missing 'financial_resolution' in {file_path} - Hard Gate hazard!"
        assert "resolution_actions" in data, f"Missing 'resolution_actions' in {file_path} - Hard Gate hazard!"

        # 2. Check Assessment Constraints
        assessment = data["assessment"]
        assert "primary_issue" in assessment
        assert "case_status" in assessment
        assert "confidence" in assessment
        conf = assessment["confidence"]
        assert 0.0 <= conf <= 1.0, f"Confidence {conf} out of bounds [0.0, 1.0] in {file_path}"

        # 3. Check Affected Entities
        entities = data["affected_entities"]
        for k in ["order_ids", "item_ids", "seller_ids", "payment_ids"]:
            assert k in entities, f"Missing entity set '{k}' in {file_path}"
            assert len(entities[k]) <= 5, f"Entity set '{k}' exceeded limit of 5 in {file_path}"

        # 4. Check Root Cause Analysis
        rca = data["root_cause_analysis"]
        assert "ranked_causes" in rca
        assert "responsible_parties" in rca
        assert len(rca["ranked_causes"]) <= 3, f"Ranked causes count > 3 in {file_path}"
        assert len(rca["responsible_parties"]) <= 3, f"Responsible parties count > 3 in {file_path}"

        # 5. Check Financial Resolution Math (2 decimal places) & Bounds
        fin = data["financial_resolution"]
        assert fin.get("currency") == "BRL", f"Currency missing or not BRL in {file_path}"
        for fk in ["item_total_brl", "freight_total_brl", "payment_total_brl", "recommended_refund_brl"]:
            val = fin.get(fk)
            assert isinstance(val, (int, float)), f"Financial field {fk} not number in {file_path}"
            assert round(val, 2) == val, f"Financial field {fk} not rounded to 2 decimal places in {file_path}: {val}"

        actions = data["resolution_actions"]
        assert isinstance(actions, list) and len(actions) <= 5, f"Actions list exceed bound of 5 in {file_path}"

        # 6. Check Evidence IDs Gatekeeping (Zero FP according to Section 5)
        evidences = data["evidence_ids"]
        assert isinstance(evidences, list) and len(evidences) <= 10, f"Evidence count exceeded limit of 10 in {file_path}"
        for ev_str in evidences:
            is_valid = any(regex.match(ev_str) for regex in valid_evidence_regexes)
            assert is_valid, f"INVALID EVIDENCE SYNTAX (False Positive Risk!) in {file_path}: '{ev_str}'"

    print(" -> All 50 output files passed 100% Section 6 schema validation and Section 5 regex gatekeeping!")

    # 7. Verify Tracing and Metadata exist in root and logging/
    assert os.path.exists("trace.jsonl"), "Missing trace.jsonl at repository root (Section 8 requirement)!"
    assert os.path.exists("metadata.json"), "Missing metadata.json at repository root (Section 8 requirement)!"
    assert os.path.exists("logging/trace.jsonl"), "Missing logging/trace.jsonl!"
    assert os.path.exists("logging/metadata.json"), "Missing logging/metadata.json!"
    
    with open("metadata.json", "r", encoding="utf-8") as mf:
        metadata = json.load(mf)
    assert metadata["processed_cases_output"] == 50, "Metadata processed count mismatch!"
    assert metadata["total_cases_input"] == 50, "Metadata total input count mismatch!"
    assert "model" in metadata, "Missing required 'model' field in metadata.json!"
    assert "parameter_size" in metadata, "Missing required 'parameter_size' field in metadata.json!"
    print(" -> Tracing files and metadata.json verified successfully!")
    print("\n[Test] CONGRATULATIONS: V2 fix verification PASSED with ZERO schema errors!")

if __name__ == "__main__":
    test_validate_all_50_output_files()
