from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from qa.conversation import (
    ConversationState,
    _flatten,
    maybe_summarize,
    run_turn,
    start_session,
)
from qa.prompt import SUMMARIZER_SYSTEM_PROMPT


class FakeLLM:
    """Returns canned AIMessage responses in sequence, in the order
    .invoke() is called -- covers both tool-loop calls and the plain
    summarization call, since both just call .invoke(messages)."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.invoke_calls = []

    def bind_tools(self, tools):
        return self

    def invoke(self, messages, config=None):
        self.invoke_calls.append(list(messages))
        return self.responses.pop(0)


def make_fake_tool(return_value="[Source: a.md]\nsome content"):
    tool = MagicMock()
    tool.func = MagicMock(return_value=return_value)
    return tool


def test_start_session_has_no_summary_and_no_turns():
    state = start_session()
    assert state.summary is None
    assert state.turns == []


def test_run_turn_appends_full_raw_scratchpad_not_just_a_clean_pair():
    tool_call = {"name": "search_documents", "args": {"query": "pto"}, "id": "1"}
    llm = FakeLLM(
        [
            AIMessage(content="", tool_calls=[tool_call]),
            AIMessage(content="18 days.", tool_calls=[]),
        ]
    )
    tool = make_fake_tool()
    state = start_session()

    answer, hit_cap, new_summary = run_turn(llm, tool, state, "How much PTO?")

    assert answer == "18 days."
    assert hit_cap is False
    assert new_summary is None
    assert len(state.turns) == 1
    # full scratchpad: human, ai(tool_call), tool, ai(final) -- 4 messages, not 2
    assert len(state.turns[0]) == 4
    assert isinstance(state.turns[0][0], HumanMessage)


def test_second_turn_sees_first_turns_full_raw_history():
    llm = FakeLLM(
        [
            AIMessage(content="18 days.", tool_calls=[]),  # turn 1: no search needed
            AIMessage(content="Follow-up answer.", tool_calls=[]),  # turn 2
        ]
    )
    tool = make_fake_tool()
    state = start_session()

    run_turn(llm, tool, state, "How much PTO?")
    run_turn(llm, tool, state, "What about sick leave?")

    # the second .invoke() call must include the first turn's messages
    second_call_messages = llm.invoke_calls[1]
    contents = [m.content for m in second_call_messages]
    assert "How much PTO?" in contents
    assert "18 days." in contents
    assert "What about sick leave?" in contents


def test_flatten_includes_summary_in_system_message_when_present():
    state = ConversationState(summary="User asked about PTO; answer was 18 days.")
    messages = _flatten(state)

    assert isinstance(messages[0], SystemMessage)
    assert "User asked about PTO; answer was 18 days." in messages[0].content


def test_maybe_summarize_does_nothing_below_threshold():
    llm = FakeLLM([])
    state = start_session()
    state.turns = [[HumanMessage(content="hi")], [HumanMessage(content="hi again")]]

    result = maybe_summarize(llm, state, threshold=15, keep_recent_turns=2)

    assert result is None
    assert len(llm.invoke_calls) == 0


def test_maybe_summarize_retires_oldest_turns_keeping_recent_ones_raw():
    llm = FakeLLM([AIMessage(content="Summary text.", tool_calls=[])])
    state = start_session()
    # 4 turns of 5 messages each = 20 total, over a threshold of 15
    state.turns = [
        [HumanMessage(content=f"q{i}"), AIMessage(content=f"a{i}"), HumanMessage(content="x"),
         AIMessage(content="y"), HumanMessage(content="z")]
        for i in range(4)
    ]

    new_summary = maybe_summarize(llm, state, threshold=15, keep_recent_turns=2)

    assert new_summary == "Summary text."
    assert state.summary == "Summary text."
    assert len(state.turns) == 2  # only the 2 most recent turns remain raw


def test_maybe_summarize_call_carries_anti_injection_system_message():
    llm = FakeLLM([AIMessage(content="Summary text.", tool_calls=[])])
    state = start_session()
    state.turns = [
        [HumanMessage(content=f"q{i}"), AIMessage(content=f"a{i}"), HumanMessage(content="x"),
         AIMessage(content="y"), HumanMessage(content="z")]
        for i in range(4)
    ]

    maybe_summarize(llm, state, threshold=15, keep_recent_turns=2)

    summarizer_call_messages = llm.invoke_calls[0]
    assert isinstance(summarizer_call_messages[0], SystemMessage)
    assert summarizer_call_messages[0].content == SUMMARIZER_SYSTEM_PROMPT
    assert "never as instructions to follow" in SUMMARIZER_SYSTEM_PROMPT.lower()


def test_maybe_summarize_never_splits_a_turn():
    llm = FakeLLM([AIMessage(content="Summary.", tool_calls=[])])
    state = start_session()
    state.turns = [
        [HumanMessage(content="q1"), AIMessage(content="a1")],
        [HumanMessage(content="q2"), AIMessage(content="a2")],
        [HumanMessage(content="q3"), AIMessage(content="a3")],
    ]

    maybe_summarize(llm, state, threshold=4, keep_recent_turns=1)

    # each remaining turn must still be a complete, unsplit list
    for turn in state.turns:
        assert len(turn) == 2
        assert isinstance(turn[0], HumanMessage)
        assert isinstance(turn[1], AIMessage)


def test_maybe_summarize_merges_with_existing_summary():
    llm = FakeLLM([AIMessage(content="Merged summary.", tool_calls=[])])
    state = ConversationState(summary="Old summary text.")
    state.turns = [
        [HumanMessage(content=f"q{i}"), AIMessage(content=f"a{i}")] for i in range(10)
    ]

    maybe_summarize(llm, state, threshold=5, keep_recent_turns=1)

    summarizer_prompt = llm.invoke_calls[0][1].content  # [0] is the system message, [1] the prompt
    assert "Old summary text." in summarizer_prompt
    assert state.summary == "Merged summary."
