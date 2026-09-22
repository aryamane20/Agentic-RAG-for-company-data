"""Groq LLM setup and the agentic tool-calling loop: the model decides
whether to call search_documents, how many times (capped), and when it
has enough to answer."""

import os

from langchain_core.messages import HumanMessage, ToolMessage

from qa.prompt import STANDARDIZED_REFUSAL

DEFAULT_MODEL = "openai/gpt-oss-120b"
MAX_TOOL_CALLS = 3

FORCE_ANSWER_INSTRUCTION = (
    "You have reached the maximum number of searches. Answer now using "
    "only the information you've already found. If it isn't enough to "
    f'answer the question, say exactly: "{STANDARDIZED_REFUSAL}" Do not '
    "speculate about why it might be missing."
)


def get_llm(model_name=None, temperature=0.0):
    from langchain_groq import ChatGroq

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Get a free key at console.groq.com "
            "and export it before running this script."
        )

    return ChatGroq(
        model=model_name or os.environ.get("GROQ_MODEL", DEFAULT_MODEL),
        temperature=temperature,
        api_key=api_key,
    )


def _execute_tool_calls(tool, ai_message):
    """Run every tool call the model requested and return the resulting
    ToolMessages, in the order the model asked for them."""
    tool_messages = []
    for call in ai_message.tool_calls:
        result = tool.func(**call["args"])
        tool_messages.append(
            ToolMessage(content=result, tool_call_id=call["id"])
        )
    return tool_messages


def _finalize(messages, content, hit_cap):
    """Turn a model response's content into the answer returned to the
    caller. Some models occasionally return a blank response instead of
    real text -- including the standardized refusal they were told to
    say when they have nothing to report -- at any point they choose to
    stop calling tools, not just on the forced-final turn. A blank answer
    is never correct even when nothing leaked (retrieval came back
    empty), so substitute the guaranteed refusal rather than trust every
    model to always comply, and keep conversation memory (the last
    appended message) consistent with what's actually returned."""
    if content and content.strip():
        return content, hit_cap

    messages[-1].content = STANDARDIZED_REFUSAL
    return STANDARDIZED_REFUSAL, hit_cap


def run_agent(llm, tool, messages, max_tool_calls=MAX_TOOL_CALLS, config=None):
    """Run the tool-calling loop against an already-assembled message list
    (mutated in place -- every tool-call request/result and the final
    answer get appended to it). Returns (answer_text, hit_cap) -- hit_cap
    is True if the loop had to force a final answer after exhausting
    max_tool_calls. Callers decide what `messages` contains going in (a
    single question, or prior conversation history + a new question).
    `config` (a LangChain RunnableConfig, e.g. {"callbacks": [...]}) is
    passed through to every .invoke() call -- used by the eval pipeline to
    attach a Langfuse callback handler without changing normal callers."""
    llm_with_tools = llm.bind_tools([tool])

    for _ in range(max_tool_calls):
        response = llm_with_tools.invoke(messages, config=config)
        messages.append(response)

        if not getattr(response, "tool_calls", None):
            return _finalize(messages, response.content, False)

        messages.extend(_execute_tool_calls(tool, response))

    # Cap hit without a final answer: force one last plain-text turn.
    messages.append(HumanMessage(content=FORCE_ANSWER_INSTRUCTION))
    final_response = llm.invoke(messages, config=config)
    messages.append(final_response)

    return _finalize(messages, final_response.content, True)
