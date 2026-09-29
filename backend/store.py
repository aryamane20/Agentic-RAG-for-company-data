"""In-memory stores for conversation history and chat idempotency.
Process-local -- lost on restart, not shared across multiple server
instances. Fine for local dev or a single Render/Railway instance; would
need a real store (Redis/DB) to scale beyond that."""

import threading

from langchain_core.messages import AIMessage, HumanMessage

from qa.conversation import start_session


class ConversationStore:
    """Keyed by (user_id, conversation_id), not conversation_id alone --
    otherwise a user could supply another user's conversation_id (guessed
    or leaked) and continue reading/extending their conversation."""

    def __init__(self):
        self._lock = threading.Lock()
        self._sessions = {}

    def get_or_create(self, user_id, conversation_id, loader=None):
        """`loader`, if given, is called (with no args) only when this
        process has no in-memory state yet for this conversation -- e.g.
        after a restart, or the first turn handled by this process for a
        conversation started elsewhere. It should return persisted
        (role, content) pairs in chronological order; they're replayed
        into the fresh state's turn history so the agent still has real
        context, not just a display history with amnesia."""
        key = (user_id, conversation_id)
        with self._lock:
            if key not in self._sessions:
                state = start_session()
                if loader is not None:
                    _replay_history(state, loader())
                self._sessions[key] = state
            return self._sessions[key]


def _replay_history(state, messages):
    """Pair up persisted (role, content) rows into the [Human, AI] turn
    shape ConversationState.turns expects. A stray unpaired trailing
    message (shouldn't happen -- every turn writes both roles in the same
    transaction) is dropped rather than corrupting the turn shape."""
    pending_human = None
    for role, content in messages:
        if role == "user":
            pending_human = HumanMessage(content=content)
        elif role == "assistant" and pending_human is not None:
            state.turns.append([pending_human, AIMessage(content=content)])
            pending_human = None


class IdempotencyStore:
    """Keyed by (user_id, message_id), same cross-user-isolation
    reasoning as ConversationStore. A repeated message_id from the same
    user returns the cached response instead of reprocessing."""

    def __init__(self):
        self._lock = threading.Lock()
        self._responses = {}

    def get(self, user_id, message_id):
        with self._lock:
            return self._responses.get((user_id, message_id))

    def set(self, user_id, message_id, response):
        with self._lock:
            self._responses[(user_id, message_id)] = response
