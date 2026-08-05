import os
import json
import glob
import re

def test_validate_all_50_output_files():
    print("\n[Test] Starting thorough schema and constraints validation for 50 output files...")
    
    output_files = sorted(glob.glob("output/EC_*.json"))
    assert len(output_files) == 50, f"Expected exactly 50 output files, found {len(output_files)}!"

    valid_evidence_regexes = [
        re.compile(r"^order_status:[a-zA-Z0-9_-]+:[a-zA-Z0-9_-]+$"),
        re.compile(r"^order_timestamp:[a-zA-Z0-9_-]+:[a-zA-Z0-9_]+:\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}$"),
        re.compile(r"^order_item_seller:[a-zA-Z0-9_-]+:\w+:[a-zA-Z0-9_-]+$"),
        re.compile(r"^shipping_limit:[a-zA-Z0-9_-]+:\w+:\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}$"),
        re.compile(r"^payment_row:[a-zA-Z0-9_-]+:\w+:[a-zA-Z0-9_-]+:\d+(\.\d+)?$")
    ]

    for file_path in output_files:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 1. Required Top-Level Schema
        assert "case_id" in data, f"Missing 'case_id' in {file_path}"
        assert data.get("policy_version") == "EC_POLICY_V1", f"Invalid policy_version in {file_path}"
        assert "assessment" in data, f"Missing 'assessment' in {file_path}"
        assert "resolution" in data, f"Missing 'resolution' in {file_path}"
        assert "evidence" in data, f"Missing 'evidence' in {file_path}"

        # 2. Check Assessment Constraints
        assessment = data["assessment"]
        assert "primary_issue" in assessment
        assert "case_status" in assessment
        assert "root_cause" in assessment
        root_cause = assessment["root_cause"]
        assert "code" in root_cause
        assert "responsible_parties" in root_cause
        assert len(root_cause["responsible_parties"]) <= 5, f"Responsible parties bound exceeded in {file_path}"

        # 3. Check Resolution & Financial Math (2 decimal places)
        resolution = data["resolution"]
        assert "recommended_refund_brl" in resolution
        refund = resolution["recommended_refund_brl"]
        assert isinstance(refund, (int, float)), f"Refund must be number in {file_path}"
        assert round(refund, 2) == refund, f"Refund must be rounded to 2 decimal places in {file_path}: {refund}"
        assert len(resolution.get("actions", [])) <= 5, f"Actions bound exceeded in {file_path}"
        assert "explanation" in resolution

        # 4. Check Evidence IDs Gatekeeping (Zero FP)
        evidences = data["evidence"].get("evidence_ids", [])
        assert len(evidences) <= 10, f"Evidence count bound exceeded in {file_path}"
        for ev_str in evidences:
            is_valid = any(regex.match(ev_str) for regex in valid_evidence_regexes)
            assert is_valid, f"Invalid regex evidence ID syntax in {file_path}: '{ev_str}' -> False Positive risk!"

    print(" -> All 50 output files passed 100% schema validation and regex gatekeeping!")

    # 5. Verify Tracing and Metadata
    assert os.path.exists("logging/trace.jsonl"), "Missing logging/trace.jsonl!"
    assert os.path.exists("logging/metadata.json"), "Missing logging/metadata.json!"
    
    with open("logging/metadata.json", "r", encoding="utf-8") as mf:
        metadata = json.load(mf)
    assert metadata["processed_cases_output"] == 50, "Metadata processed count mismatch!"
    assert metadata["total_cases_input"] == 50, "Metadata total input count mismatch!"
    print(" -> Tracing file and metadata.json verified successfully!")
    print("\n[Test] CONGRATULATIONS: Phase 4 verification PASSED with ZERO schema errors!")

if __name__ == "__main__":
    test_validate_all_50_output_files()
