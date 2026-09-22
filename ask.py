#!/usr/bin/env python3
"""Agentic query CLI with multi-turn memory: type a question, watch the
model decide whether to search (and how many times), then see the
retrieved chunks and the final answer printed separately for manual
checking. Conversation history persists across turns for the session."""

import os
import sys

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage

from ingestion import db, embeddings
from qa import conversation, debug_output, guardrails, llm as llm_module
from qa.tools import build_search_tool

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DEBUG_DIR = os.path.join(ROOT_DIR, "debug_output")


def ask_once(cur, embed_model, llm, state, question, user_id, config=None):
    """`config` (a LangChain RunnableConfig, e.g. {"callbacks": [...]}) is
    forwarded to every LLM call for this turn -- unused by the normal CLI,
    but lets the eval pipeline attach a Langfuse callback handler without
    a separate code path."""
    blocked_reason = guardrails.check_input(question)
    if blocked_reason is not None:
        answer = guardrails.BLOCKED_RESPONSE
        # record as a completed turn (no tool calls) so history/trace stay consistent
        state.turns.append([HumanMessage(content=question), AIMessage(content=answer)])
        return answer, False, [], None, blocked_reason, []

    search_log = []

    def on_search(query, chunks):
        search_log.append({"query": query, "chunks": chunks})

    tool = build_search_tool(cur, embed_model, user_id=user_id, on_search=on_search)
    answer, hit_cap, new_summary = conversation.run_turn(llm, tool, state, question, config=config)

    redacted_answer, answer_findings = guardrails.redact_output(answer)
    if answer_findings:
        # keep conversation memory consistent with the redacted version shown
        # to the user -- raw PII should never persist into later turns either
        state.turns[-1][-1].content = redacted_answer

    # the retrieved-chunk previews (console output + debug trace) are a
    # separate human-facing surface from the model's answer -- redact them
    # too, so PII in a chunk can't leak there even if the model never
    # echoes it in its own answer. This does NOT change what the model
    # itself already saw during retrieval, only what's displayed/logged.
    redacted_search_log, chunk_findings = guardrails.redact_search_log(search_log)
    pii_findings = answer_findings + chunk_findings

    return redacted_answer, hit_cap, redacted_search_log, new_summary, None, pii_findings


def print_result(search_log, answer, hit_cap, new_summary, blocked_reason, pii_findings):
    if blocked_reason is not None:
        print(f"\n--- Blocked by input guardrail ({blocked_reason}) ---")
        print(answer)
        print()
        return

    print("\n--- Retrieved chunks ---")
    if not search_log:
        print("(model answered without searching)")
    for i, entry in enumerate(search_log, start=1):
        print(f"\nSearch {i}: \"{entry['query']}\"")
        for chunk in entry["chunks"]:
            print(f"  [{chunk['distance']:.4f}] {chunk['filename']}")
            preview = chunk["content"].replace("\n", " ")[:120]
            print(f"    {preview}...")

    print("\n--- Answer ---")
    print(answer)
    if hit_cap:
        print("\n(note: hit the max search cap before answering)")
    if new_summary is not None:
        print("\n(note: older conversation history was just summarized to stay within limits)")
    if pii_findings:
        print(f"\n(note: output guardrail redacted {len(pii_findings)} PII match(es): "
              f"{[f['type'] for f in pii_findings]})")
    print()


def prompt_for_user_id(input_fn=input):
    """Ask once, at session start, which test user_id to run as. Loops
    until a valid integer is given -- this stand-in for real auth still
    shouldn't let a typo silently become an invalid/empty user_id."""
    while True:
        raw = input_fn("Run as which test user? (enter user_id): ").strip()
        try:
            return int(raw)
        except ValueError:
            print("Please enter a numeric user_id (see seed_test_users.py output).")


def main():
    load_dotenv()

    print("Loading embedding model...")
    embed_model = embeddings.load_model()

    print("Connecting to Groq...")
    llm = llm_module.get_llm()

    conn = db.get_connection()
    cur = conn.cursor()

    user_id = prompt_for_user_id()
    state = conversation.start_session()
    trace, trace_path = debug_output.start_session_trace(DEBUG_DIR, user_id)

    print(f"\nRunning as user_id={user_id}. Type a question, or 'quit' to exit.\n")
    try:
        while True:
            try:
                question = input("> ").strip()
            except EOFError:
                break

            if not question:
                continue
            if question.lower() in ("quit", "exit"):
                break

            try:
                answer, hit_cap, search_log, new_summary, blocked_reason, pii_findings = ask_once(
                    cur, embed_model, llm, state, question, user_id
                )
            except Exception as exc:  # noqa: BLE001 - keep the REPL alive
                print(f"Error: {exc}\n")
                continue

            print_result(search_log, answer, hit_cap, new_summary, blocked_reason, pii_findings)

            debug_output.append_turn(
                trace, trace_path, question, search_log, answer, hit_cap,
                new_summary, blocked_reason, pii_findings,
            )
            print(f"(trace saved to {trace_path})\n")
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
