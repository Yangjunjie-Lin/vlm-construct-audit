from __future__ import annotations

from vlm_construct_audit.audit import build_audit_decisions
from vlm_construct_audit.calibration.runner import run_calibration
from vlm_construct_audit.data import generate_dataset
from vlm_construct_audit.interventions import build_interventions
from vlm_construct_audit.serialization import build_serializations, validate_equivalence
from vlm_construct_audit.statistics import analyze_predictions


def _run_components():
    generate_dataset()
    build_interventions()
    build_serializations()
    assert validate_equivalence()["programmatic_fact_equivalence"] is True
    run_calibration()
    analyze_predictions()
    return build_audit_decisions()


def test_six_known_states_recover_expected_claim_classes() -> None:
    output = _run_components()
    assert output["expected_class_matches"] == 6
    assert output["decisions"]["OracleEvidenceReasoner"]["decision"] == "VALID_BEHAVIORAL_EFFECT"
    assert output["decisions"]["EvidenceBlindSystem"]["decision"] == "INVALID_INTERVENTION"
    assert output["decisions"]["ParserCorruptedSystem"]["decision"] == "INVALID_MEASUREMENT"
    assert output["decisions"]["FormatShortcutSystem"]["decision"] == "FORMAT_DEPENDENT"
    assert output["decisions"]["UptakeOnlySystem"]["decision"] == "INCONCLUSIVE"
    output_corruption = output["decisions"]["ReasonerWithOutputCorruption"]
    assert output_corruption["decision"] == "INVALID_MEASUREMENT"
    assert output_corruption["diagnostic_subtype"] == "final_output_mapping"


def test_prediction_inventory_is_complete() -> None:
    generate_dataset()
    build_interventions()
    build_serializations()
    manifest = run_calibration()
    assert manifest["prediction_count"] == manifest["expected_prediction_count"] == 6912
    assert manifest["measurement_probe_count"] == 1800
