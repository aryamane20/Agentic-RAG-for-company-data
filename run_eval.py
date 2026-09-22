#!/usr/bin/env python3
"""Run the golden-dataset evaluation: execute every case through the full
system, score answer cases with Ragas and deny/guardrail cases as
pass/fail, aggregate into a version-labeled summary, and (if Langfuse
credentials are set) trace every case and log scores back to it.

Usage: python run_eval.py --version <label>
"""

import argparse
import os
import sys

from dotenv import load_dotenv

from eval import aggregate, runner, scoring
from eval.runner import with_rate_limit_retry
from ingestion import db, embeddings
from qa import llm as llm_module

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(ROOT_DIR, "eval_results")

# APP_MODEL is a temporary override of qa/llm.py's DEFAULT_MODEL
# ("openai/gpt-oss-120b"), which hit its Groq free-tier daily token cap
# during today's session. gpt-oss-20b still has quota. This means today's
# eval runs score a different (smaller) model than the one used throughout
# manual testing -- the baseline-vs-change comparison is still internally
# valid (same model both times), just not representative of gpt-oss-120b
# specifically. Revert to None (falls back to DEFAULT_MODEL) once quota
# resets.
APP_MODEL = "openai/gpt-oss-20b"

# Separate from APP_MODEL so the Ragas judge has its own quota bucket and
# isn't grading its own output (self-preference bias). Fixed across runs
# so before/after score comparisons stay apples-to-apples -- a different
# judge model would change score calibration, not just the system under
# test. gpt-oss-safeguard-20b is a safety/moderation-tuned model, not a
# general one -- picked here only because it had quota when the standard
# candidates didn't; watch for oddly-skewed scores.
JUDGE_MODEL = "openai/gpt-oss-safeguard-20b"

# Pacing between cases to stay under Groq's tokens-per-minute limit
# (separate from the tokens-per-day cap that forced the model switch
# above) -- doesn't fix an exhausted daily budget, but prevents the
# per-minute throttling we hit earlier in the session.
SECONDS_BETWEEN_CASES = 3


def log_scores_to_langfuse(raw_results, answer_scores, verdicts):
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
    if not public_key or not secret_key:
        return

    from langfuse import Langfuse

    client = Langfuse(
        public_key=public_key, secret_key=secret_key, host=os.environ.get("LANGFUSE_HOST")
    )

    for r in raw_results:
        trace_id = r.get("trace_id")
        if not trace_id:
            continue

        if r["category"] == "answer":
            for metric, value in answer_scores.get(r["case_id"], {}).items():
                if value is not None:
                    client.create_score(trace_id=trace_id, name=metric, value=value, data_type="NUMERIC")
        else:
            verdict = verdicts.get(r["case_id"])
            if verdict:
                client.create_score(
                    trace_id=trace_id,
                    name="pass_fail",
                    value=1.0 if verdict["passed"] else 0.0,
                    data_type="BOOLEAN",
                    comment=verdict["reason"],
                )

    client.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, help="Version label for this eval run")
    args = parser.parse_args()

    load_dotenv()

    print("Loading embedding model...")
    embed_model = embeddings.load_model()
    print("Connecting to Groq...")
    llm = llm_module.get_llm(model_name=APP_MODEL)
    judge_llm = llm_module.get_llm(model_name=JUDGE_MODEL)

    conn = db.get_connection()
    cur = conn.cursor()

    try:
        cases = runner.load_cases()
        cases_by_id = {c["id"]: c for c in cases}

        print(f"Running {len(cases)} golden-dataset cases (version={args.version})...")
        raw_results = runner.run_all_cases(
            cur, embed_model, llm, args.version, cases=cases, seconds_between_cases=SECONDS_BETWEEN_CASES
        )

        answer_results = [r for r in raw_results if r["category"] == "answer"]
        deny_guardrail_results = [r for r in raw_results if r["category"] != "answer"]

        print(f"Scoring answer cases with Ragas (judge model: {JUDGE_MODEL})...")
        answer_scores = with_rate_limit_retry(
            scoring.score_answer_cases, answer_results, judge_llm=judge_llm, embed_model=embed_model
        )

        verdicts = {}
        for r in deny_guardrail_results:
            case = cases_by_id[r["case_id"]]
            if r["category"] == "deny":
                verdicts[r["case_id"]] = scoring.score_deny_case(r, case)
            else:
                verdicts[r["case_id"]] = scoring.score_guardrail_case(r, case)

        summary = aggregate.build_summary(
            args.version, cases_by_id, raw_results, answer_scores, verdicts, judge_model=JUDGE_MODEL
        )
        aggregate.print_summary(summary)
        path = aggregate.save_summary(summary, RESULTS_DIR)
        print(f"Summary saved to: {path}")

        log_scores_to_langfuse(raw_results, answer_scores, verdicts)
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
