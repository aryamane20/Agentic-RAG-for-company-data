import os
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from qa.llm import FORCE_ANSWER_INSTRUCTION, get_llm, run_agent
from qa.prompt import STANDARDIZED_REFUSAL


class FakeLLM:
    """Returns canned AIMessage responses in sequence, in the order
    .invoke() is called (whether via the bound-tools object or the plain
    forced-final call -- bind_tools() returns self so both share one
    call sequence, matching how the real loop only ever calls .invoke
    once per turn)."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.invoke_calls = []

    def bind_tools(self, tools):
        self.bound_tools = tools
        return self

    def invoke(self, messages, config=None):
        self.invoke_calls.append(list(messages))
        return self.responses.pop(0)


def make_fake_tool(return_value="[Source: a.md]\nsome content"):
    tool = MagicMock()
    tool.func = MagicMock(return_value=return_value)
    return tool


def make_messages(question):
    return [SystemMessage(content="system prompt"), HumanMessage(content=question)]


def test_run_agent_returns_answer_immediately_when_no_tool_call():
    llm = FakeLLM([AIMessage(content="The answer is 18 days.", tool_calls=[])])
    tool = make_fake_tool()
    messages = make_messages("How much PTO?")

    answer, hit_cap = run_agent(llm, tool, messages)

    assert answer == "The answer is 18 days."
    assert hit_cap is False
    assert len(llm.invoke_calls) == 1
    tool.func.assert_not_called()
    # the final AIMessage must be left appended in the caller's list
    assert messages[-1].content == "The answer is 18 days."


def test_run_agent_executes_tool_call_then_returns_final_answer():
    tool_call = {"name": "search_documents", "args": {"query": "PTO policy"}, "id": "call_1"}
    llm = FakeLLM(
        [
            AIMessage(content="", tool_calls=[tool_call]),
            AIMessage(content="18 days per year, per employee_handbook.md.", tool_calls=[]),
        ]
    )
    tool = make_fake_tool(return_value="[Source: employee_handbook.md]\n18 days")
    messages = make_messages("How much PTO?")

    answer, hit_cap = run_agent(llm, tool, messages)

    assert answer == "18 days per year, per employee_handbook.md."
    assert hit_cap is False
    tool.func.assert_called_once_with(query="PTO policy")
    assert len(llm.invoke_calls) == 2
    # messages list now holds the full scratchpad: system, human, ai(tool_call), tool, ai(final)
    assert len(messages) == 5


def test_run_agent_stops_at_max_tool_calls_and_forces_final_answer():
    tool_call = {"name": "search_documents", "args": {"query": "q"}, "id": "call_x"}
    # 3 rounds all requesting another search, then the forced final call
    llm = FakeLLM(
        [
            AIMessage(content="", tool_calls=[tool_call]),
            AIMessage(content="", tool_calls=[tool_call]),
            AIMessage(content="", tool_calls=[tool_call]),
            AIMessage(content="I don't know based on the provided documents.", tool_calls=[]),
        ]
    )
    tool = make_fake_tool()
    messages = make_messages("some obscure question")

    answer, hit_cap = run_agent(llm, tool, messages, max_tool_calls=3)

    assert answer == "I don't know based on the provided documents."
    assert hit_cap is True
    assert tool.func.call_count == 3
    assert len(llm.invoke_calls) == 4
    # the forced final turn must include the cap-hit instruction
    last_call_messages = llm.invoke_calls[-1]
    assert any(FORCE_ANSWER_INSTRUCTION in getattr(m, "content", "") for m in last_call_messages)
    # the final AIMessage must be appended too, not dropped
    assert messages[-1].content == "I don't know based on the provided documents."


def test_run_agent_substitutes_refusal_when_early_return_answer_is_blank():
    # model stops calling tools (no tool_calls) but returns blank content
    # on a normal turn, not just the forced-final one -- same bug, earlier
    # exit point
    llm = FakeLLM([AIMessage(content="", tool_calls=[])])
    tool = make_fake_tool()
    messages = make_messages("some obscure question")

    answer, hit_cap = run_agent(llm, tool, messages)

    assert answer == STANDARDIZED_REFUSAL
    assert hit_cap is False
    assert messages[-1].content == STANDARDIZED_REFUSAL


def test_run_agent_substitutes_refusal_when_forced_final_answer_is_blank():
    tool_call = {"name": "search_documents", "args": {"query": "q"}, "id": "call_x"}
    llm = FakeLLM(
        [
            AIMessage(content="", tool_calls=[tool_call]),
            AIMessage(content="", tool_calls=[tool_call]),
            AIMessage(content="", tool_calls=[tool_call]),
            AIMessage(content="", tool_calls=[]),  # model goes blank on the forced final turn
        ]
    )
    tool = make_fake_tool()
    messages = make_messages("some obscure question")

    answer, hit_cap = run_agent(llm, tool, messages, max_tool_calls=3)

    assert answer == STANDARDIZED_REFUSAL
    assert hit_cap is True
    # conversation memory must reflect the substituted text, not the blank
    assert messages[-1].content == STANDARDIZED_REFUSAL


def test_run_agent_substitutes_refusal_when_forced_final_answer_is_whitespace_only():
    tool_call = {"name": "search_documents", "args": {"query": "q"}, "id": "call_x"}
    llm = FakeLLM(
        [
            AIMessage(content="", tool_calls=[tool_call]),
            AIMessage(content="", tool_calls=[tool_call]),
            AIMessage(content="", tool_calls=[tool_call]),
            AIMessage(content="   \n  ", tool_calls=[]),
        ]
    )
    tool = make_fake_tool()
    messages = make_messages("some obscure question")

    answer, hit_cap = run_agent(llm, tool, messages, max_tool_calls=3)

    assert answer == STANDARDIZED_REFUSAL


def test_get_llm_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        get_llm()
