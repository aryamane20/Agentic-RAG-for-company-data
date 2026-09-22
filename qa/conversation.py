"""Multi-turn conversation state: full raw detail (every tool call and
result, not just clean Q/A pairs) kept per turn, with real summarization
-- not truncation -- once the raw scratchpad grows past a threshold.
Summarization always retires whole turns, never splits a tool_call from
its tool_result, since that would produce an invalid message sequence."""

from dataclasses import dataclass, field
from typing import List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from qa.llm import run_agent
from qa.prompt import SUMMARIZER_SYSTEM_PROMPT, SYSTEM_PROMPT

MAX_HISTORY_MESSAGES = 15
KEEP_RECENT_TURNS = 2

SUMMARY_HEADER = "\n\nSummary of earlier conversation so far:\n"


@dataclass
class ConversationState:
    summary: Optional[str] = None
    turns: List[List] = field(default_factory=list)


def start_session():
    return ConversationState()


def _system_message(state):
    content = SYSTEM_PROMPT
    if state.summary:
        content += SUMMARY_HEADER + state.summary
    return SystemMessage(content=content)


def _flatten(state):
    """The full message list the model sees for the next turn: one system
    message (with the running summary folded in, if any) plus every raw
    message from every not-yet-summarized turn."""
    messages = [_system_message(state)]
    for turn in state.turns:
        messages.extend(turn)
    return messages


def _render_turns_as_text(turns):
    """Readable transcript of retiring turns, for the summarizer prompt."""
    lines = []
    for turn in turns:
        for message in turn:
            role = message.__class__.__name__.replace("Message", "")
            tool_calls = getattr(message, "tool_calls", None)
            if tool_calls:
                for call in tool_calls:
                    query = call.get("args", {}).get("query", "")
                    lines.append(f"Assistant searched for: {query!r}")
            elif message.content:
                lines.append(f"{role}: {message.content}")
    return "\n".join(lines)


def maybe_summarize(
    llm, state, threshold=MAX_HISTORY_MESSAGES, keep_recent_turns=KEEP_RECENT_TURNS, config=None
):
    """If the raw scratchpad has grown past `threshold` messages, retire
    all but the most recent `keep_recent_turns` turns into an updated
    summary (merged with any existing summary), via one extra LLM call.
    Returns the new summary text, or None if nothing was retired."""
    total_messages = sum(len(turn) for turn in state.turns)
    if total_messages <= threshold or len(state.turns) <= keep_recent_turns:
        return None

    turns_to_retire = state.turns[:-keep_recent_turns]
    state.turns = state.turns[-keep_recent_turns:]

    transcript = _render_turns_as_text(turns_to_retire)
    parts = []
    if state.summary:
        parts.append(f"Existing summary of earlier conversation:\n{state.summary}")
    parts.append(f"Additional conversation to fold into the summary:\n{transcript}")
    parts.append(
        "Write an updated, concise summary of the entire conversation so far. "
        "Preserve key facts, filenames cited, and what was asked and answered."
    )
    summarizer_prompt = "\n\n".join(parts)

    response = llm.invoke(
        [SystemMessage(content=SUMMARIZER_SYSTEM_PROMPT), HumanMessage(content=summarizer_prompt)],
        config=config,
    )
    state.summary = response.content
    return state.summary


def run_turn(llm, tool, state, question, max_tool_calls=3, config=None):
    """Run one conversation turn using the full current history (system +
    running summary + every raw message from unsummarized turns), then
    record this turn's full raw scratchpad -- not a stripped-down pair --
    and check whether it's time to summarize. Returns (answer, hit_cap,
    new_summary_or_None). `config` is forwarded to every LLM call in this
    turn (see qa.llm.run_agent) -- used by the eval pipeline to attach a
    Langfuse callback handler without changing normal callers."""
    working_messages = _flatten(state)
    turn_start = len(working_messages)
    working_messages.append(HumanMessage(content=question))

    answer, hit_cap = run_agent(llm, tool, working_messages, max_tool_calls=max_tool_calls, config=config)

    state.turns.append(working_messages[turn_start:])
    new_summary = maybe_summarize(llm, state, config=config)

    return answer, hit_cap, new_summary
