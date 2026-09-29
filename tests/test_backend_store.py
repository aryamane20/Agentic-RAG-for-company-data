from backend.store import ConversationStore, IdempotencyStore


def test_get_or_create_hydrates_turns_from_loader_on_first_access():
    store = ConversationStore()
    loader = lambda: [("user", "What's the PTO policy?"), ("assistant", "18 days a year.")]

    state = store.get_or_create(user_id=1, conversation_id="abc", loader=loader)

    assert len(state.turns) == 1
    human, ai = state.turns[0]
    assert human.content == "What's the PTO policy?"
    assert ai.content == "18 days a year."


def test_get_or_create_only_calls_loader_once_per_conversation():
    store = ConversationStore()
    calls = []

    def loader():
        calls.append(1)
        return [("user", "hi"), ("assistant", "hello")]

    store.get_or_create(user_id=1, conversation_id="abc", loader=loader)
    store.get_or_create(user_id=1, conversation_id="abc", loader=loader)

    assert len(calls) == 1


def test_get_or_create_ignores_unpaired_trailing_message_from_loader():
    store = ConversationStore()
    # a stray trailing user message with no assistant reply yet shouldn't
    # happen (both rows are written in the same transaction), but must
    # never corrupt the turn shape if it somehow does
    loader = lambda: [("user", "first"), ("assistant", "first reply"), ("user", "dangling")]

    state = store.get_or_create(user_id=1, conversation_id="abc", loader=loader)

    assert len(state.turns) == 1


def test_get_or_create_without_loader_starts_empty_as_before():
    store = ConversationStore()

    state = store.get_or_create(user_id=1, conversation_id="abc")

    assert state.turns == []


def test_get_or_create_returns_same_state_for_same_key():
    store = ConversationStore()

    state1 = store.get_or_create(user_id=1, conversation_id="abc")
    state2 = store.get_or_create(user_id=1, conversation_id="abc")

    assert state1 is state2


def test_get_or_create_isolates_different_conversations_for_same_user():
    store = ConversationStore()

    state1 = store.get_or_create(user_id=1, conversation_id="abc")
    state2 = store.get_or_create(user_id=1, conversation_id="xyz")

    assert state1 is not state2


def test_get_or_create_isolates_same_conversation_id_across_different_users():
    # a user must never be able to continue another user's conversation
    # by supplying (or guessing/leaking) their conversation_id
    store = ConversationStore()

    state_user1 = store.get_or_create(user_id=1, conversation_id="shared-id")
    state_user2 = store.get_or_create(user_id=2, conversation_id="shared-id")

    assert state_user1 is not state_user2


def test_idempotency_store_returns_none_when_not_cached():
    store = IdempotencyStore()

    assert store.get(user_id=1, message_id="abc") is None


def test_idempotency_store_returns_cached_response():
    store = IdempotencyStore()

    store.set(user_id=1, message_id="abc", response={"answer": "18 days"})

    assert store.get(user_id=1, message_id="abc") == {"answer": "18 days"}


def test_idempotency_store_isolates_same_message_id_across_users():
    # a repeated message_id from a DIFFERENT user must never return
    # another user's cached response
    store = IdempotencyStore()

    store.set(user_id=1, message_id="shared-id", response={"answer": "user 1's answer"})

    assert store.get(user_id=2, message_id="shared-id") is None
