import json

from app.services.evaluation import run_evaluation


def test_labelled_evaluation_reports_observed_metrics_and_reproducibility():
    report = run_evaluation()
    assert report["synthetic_cases"] == 8
    assert report["finding_metrics"] == {
        "true_positives": 4,
        "false_positives": 0,
        "false_negatives": 0,
        "precision": 1.0,
        "recall": 1.0,
    }
    assert report["evidence_verification"]["observed"] == {"verified": 2, "uncertain": 1, "rejected": 1}
    assert report["evidence_verification"]["outcome_matches"] == 4
    assert report["evidence_verification"]["outcome_mismatches"] == 0
    assert report["run_consistency"]["rate"] == 1.0
    assert report["repair_validity"] == {"valid_repairs": 5, "repair_cases": 5, "safe_repair_refusals": 2}


def test_empty_evaluation_dataset_has_explicit_undefined_precision_and_recall(tmp_path):
    dataset = tmp_path / "empty.json"
    dataset.write_text(json.dumps([]), encoding="utf-8")
    report = run_evaluation(dataset)
    assert report["synthetic_cases"] == 0
    assert report["finding_metrics"]["precision"] is None
    assert report["finding_metrics"]["recall"] is None
    assert report["run_consistency"]["rate"] is None
