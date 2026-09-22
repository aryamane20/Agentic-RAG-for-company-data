"""Write a full trace of a conversation session -- every turn, every
search issued within it, and any summarization events -- to
debug_output/queries/. One file per session, rewritten after every turn,
so you can see how prior turns influenced a later turn's search query."""

import json
import os
from datetime import datetime, timezone


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def start_session_trace(output_dir, user_id):
    """Begin a new session trace. Returns (trace_dict, file_path). Call
    append_turn(...) after each turn to record it and persist to disk."""
    session_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    path = os.path.join(output_dir, "queries", f"session_{session_id}_user{user_id}.json")

    trace = {
        "session_id": session_id,
        "user_id": user_id,
        "started_at": _now_iso(),
        "turns": [],
        "summarization_events": [],
    }
    return trace, path


def _build_turn(turn_number, question, search_log, final_answer, hit_cap, blocked_reason, pii_findings):
    return {
        "turn_number": turn_number,
        "timestamp": _now_iso(),
        "question": question,
        "blocked_reason": blocked_reason,
        "search_count": len(search_log),
        "hit_cap": hit_cap,
        "searches": [
            {"iteration": i + 1, "query": entry["query"], "results": entry["chunks"]}
            for i, entry in enumerate(search_log)
        ],
        "final_answer": final_answer,
        "pii_findings": pii_findings or [],
    }


def append_turn(
    trace,
    path,
    question,
    search_log,
    final_answer,
    hit_cap,
    new_summary=None,
    blocked_reason=None,
    pii_findings=None,
):
    """Record one turn into the session trace and rewrite the file to
    disk immediately -- so nothing is lost if the session is interrupted
    partway through. Returns the file path (same as passed in)."""
    turn_number = len(trace["turns"]) + 1
    trace["turns"].append(
        _build_turn(
            turn_number, question, search_log, final_answer, hit_cap, blocked_reason, pii_findings
        )
    )

    if new_summary is not None:
        trace["summarization_events"].append(
            {"after_turn": turn_number, "summary": new_summary, "timestamp": _now_iso()}
        )

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(trace, f, indent=2)

    return path
