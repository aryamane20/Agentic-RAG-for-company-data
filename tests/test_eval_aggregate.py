import json
import os

from eval.aggregate import build_summary, save_summary


def make_raw_result(case_id, category, **overrides):
    base = {
        "case_id": case_id,
        "category": category,
        "question": "q",
        "user_role": "engineer",
        "answer": "a",
        "latency_seconds": 0.5,
        "trace_id": "trace-1",
    }
    base.update(overrides)
    return base


def test_build_summary_averages_answer_scores():
    cases_by_id = {
        "answer_01": {"expected_source_document": "a.md"},
        "answer_02": {"expected_source_document": "b.md"},
    }
    raw_results = [
        make_raw_result("answer_01", "answer"),
        make_raw_result("answer_02", "answer"),
    ]
    answer_scores = {
        "answer_01": {"faithfulness": 1.0, "answer_relevancy": 0.8, "context_precision": 0.9},
        "answer_02": {"faithfulness": 0.6, "answer_relevancy": 0.6, "context_precision": 0.7},
    }

    summary = build_summary("v1", cases_by_id, raw_results, answer_scores, verdicts={})

    assert summary["version_label"] == "v1"
    assert summary["answer_scores"]["count"] == 2
    assert summary["answer_scores"]["avg_faithfulness"] == 0.8
    assert summary["answer_scores"]["avg_answer_relevancy"] == 0.7
    assert abs(summary["answer_scores"]["avg_context_precision"] - 0.8) < 1e-9


def test_build_summary_handles_missing_scores_gracefully():
    cases_by_id = {"answer_01": {"expected_source_document": "a.md"}}
    raw_results = [make_raw_result("answer_01", "answer")]
    answer_scores = {}  # ragas scoring produced nothing for this case

    summary = build_summary("v1", cases_by_id, raw_results, answer_scores, verdicts={})

    assert summary["answer_scores"]["count"] == 1
    assert summary["answer_scores"]["avg_faithfulness"] is None


def test_build_summary_computes_deny_and_guardrail_pass_rates():
    cases_by_id = {}
    raw_results = [
        make_raw_result("deny_01", "deny"),
        make_raw_result("deny_02", "deny"),
        make_raw_result("guardrail_direct_injection", "guardrail"),
    ]
    verdicts = {
        "deny_01": {"passed": True, "reason": "ok"},
        "deny_02": {"passed": False, "reason": "leaked"},
        "guardrail_direct_injection": {"passed": True, "reason": "blocked"},
    }

    summary = build_summary("v1", cases_by_id, raw_results, answer_scores={}, verdicts=verdicts)

    assert summary["deny"]["count"] == 2
    assert summary["deny"]["pass_rate"] == 0.5
    assert summary["guardrail"]["count"] == 1
    assert summary["guardrail"]["pass_rate"] == 1.0


def test_build_summary_per_case_results_include_reason_for_deny():
    cases_by_id = {}
    raw_results = [make_raw_result("deny_01", "deny")]
    verdicts = {"deny_01": {"passed": False, "reason": "leaked filename"}}

    summary = build_summary("v1", cases_by_id, raw_results, answer_scores={}, verdicts=verdicts)

    entry = summary["per_case_results"][0]
    assert entry["passed"] is False
    assert entry["reason"] == "leaked filename"


def test_save_summary_writes_versioned_filename(tmp_path):
    summary = {"version_label": "baseline", "per_case_results": []}

    path = save_summary(summary, str(tmp_path))

    assert os.path.exists(path)
    assert "baseline" in os.path.basename(path)
    data = json.loads(open(path).read())
    assert data["version_label"] == "baseline"
