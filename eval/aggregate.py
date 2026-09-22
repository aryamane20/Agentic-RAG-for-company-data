"""Combine raw per-case results + scores into one run summary: average
Ragas scores for answer cases, pass rates for deny/guardrail cases, all
tagged with the run's version label."""

import json
import os
from datetime import datetime, timezone


def _average(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def build_summary(version_label, cases_by_id, raw_results, answer_scores, verdicts, judge_model=None):
    """
    cases_by_id: {case_id: case_dict} from the golden dataset
    raw_results: list of run_case() result dicts
    answer_scores: {case_id: {faithfulness, answer_relevancy, context_precision}}
    verdicts: {case_id: {passed, reason}} for deny + guardrail cases
    judge_model: recorded for traceability -- Ragas scores are only
    comparable across runs that used the same judge model
    """
    per_case = []
    answer_metric_lists = {"faithfulness": [], "answer_relevancy": [], "context_precision": []}
    deny_results, guardrail_results = [], []

    for r in raw_results:
        case_id = r["case_id"]
        category = r["category"]
        entry = {
            "case_id": case_id,
            "category": category,
            "question": r["question"],
            "user_role": r["user_role"],
            "answer": r["answer"],
            "latency_seconds": r["latency_seconds"],
            "trace_id": r.get("trace_id"),
        }

        if category == "answer":
            scores = answer_scores.get(case_id, {})
            entry["scores"] = scores
            entry["expected_source_document"] = cases_by_id[case_id].get("expected_source_document")
            for metric, values in answer_metric_lists.items():
                if scores.get(metric) is not None:
                    values.append(scores[metric])
        else:
            verdict = verdicts.get(case_id, {"passed": False, "reason": "not scored"})
            entry["passed"] = verdict["passed"]
            entry["reason"] = verdict["reason"]
            if category == "deny":
                deny_results.append(verdict["passed"])
            else:
                guardrail_results.append(verdict["passed"])

        per_case.append(entry)

    answer_count = sum(1 for r in raw_results if r["category"] == "answer")

    return {
        "version_label": version_label,
        "judge_model": judge_model,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "case_count": len(raw_results),
        "answer_scores": {
            "count": answer_count,
            "avg_faithfulness": _average(answer_metric_lists["faithfulness"]),
            "avg_answer_relevancy": _average(answer_metric_lists["answer_relevancy"]),
            "avg_context_precision": _average(answer_metric_lists["context_precision"]),
        },
        "deny": {
            "count": len(deny_results),
            "pass_rate": _average([1.0 if p else 0.0 for p in deny_results]),
        },
        "guardrail": {
            "count": len(guardrail_results),
            "pass_rate": _average([1.0 if p else 0.0 for p in guardrail_results]),
        },
        "per_case_results": per_case,
    }


def save_summary(summary, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    filename = f"{summary['version_label']}_{timestamp}.json"
    path = os.path.join(output_dir, filename)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return path


def print_summary(summary):
    print("\n" + "=" * 70)
    print(f"EVAL SUMMARY -- version: {summary['version_label']} (judge: {summary.get('judge_model')})")
    print("=" * 70)

    a = summary["answer_scores"]
    print(f"\nAnswer cases ({a['count']}):")
    print(f"  avg faithfulness:      {_fmt(a['avg_faithfulness'])}")
    print(f"  avg answer_relevancy:  {_fmt(a['avg_answer_relevancy'])}")
    print(f"  avg context_precision: {_fmt(a['avg_context_precision'])}")

    d = summary["deny"]
    print(f"\nDeny cases ({d['count']}): pass rate {_fmt(d['pass_rate'], pct=True)}")

    g = summary["guardrail"]
    print(f"\nGuardrail cases ({g['count']}): pass rate {_fmt(g['pass_rate'], pct=True)}")
    print()


def _fmt(value, pct=False):
    if value is None:
        return "n/a"
    return f"{value * 100:.1f}%" if pct else f"{value:.3f}"
