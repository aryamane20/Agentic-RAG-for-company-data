"""In-memory stores for conversation history and chat idempotency.
Process-local -- lost on restart, not shared across multiple server
instances. Fine for local dev or a single Render/Railway instance; would
need a real store (Redis/DB) to scale beyond that."""

import threading

from qa.conversation import start_session


class ConversationStore:
    """Keyed by (user_id, conversation_id), not conversation_id alone --
    otherwise a user could supply another user's conversation_id (guessed
    or leaked) and continue reading/extending their conversation."""

    def __init__(self):
        self._lock = threading.Lock()
        self._sessions = {}

    def get_or_create(self, user_id, conversation_id):
        key = (user_id, conversation_id)
        with self._lock:
            if key not in self._sessions:
                self._sessions[key] = start_session()
            return self._sessions[key]


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
