"""Tests for the PawUI state module."""

from pawui.state import State


class TestState:
    def test_get_set(self):
        state = State()
        state.set("key", "value")
        assert state.get("key") == "value"

    def test_get_default(self):
        state = State()
        assert state.get("missing", "default") == "default"

    def test_attribute_access(self):
        state = State()
        state.key = "value"
        assert state.key == "value"

    def test_dict_access(self):
        state = State()
        state["key"] = "value"
        assert state["key"] == "value"

    def test_has(self):
        state = State()
        state.set("key", "value")
        assert state.has("key") is True
        assert state.has("missing") is False

    def test_contains(self):
        state = State()
        state["key"] = "value"
        assert "key" in state
        assert "missing" not in state

    def test_watch_single_key(self):
        state = State()
        calls = []
        state.watch("key", lambda v: calls.append(v))
        state.set("key", "first")
        state.set("key", "second")
        assert calls == ["first", "second"]

    def test_watch_wildcard(self):
        state = State()
        calls = []
        state.watch("*", lambda v: calls.append(v))
        state.set("a", 1)
        state.set("b", 2)
        assert calls == [1, 2]

    def test_unwatch(self):
        state = State()
        calls = []
        unwatch = state.watch("key", lambda v: calls.append(v))
        state.set("key", "first")
        unwatch()
        state.set("key", "second")
        assert calls == ["first"]

    def test_initial_data(self):
        state = State({"a": 1, "b": 2})
        assert state.get("a") == 1
        assert state.get("b") == 2

    def test_keys(self):
        state = State({"a": 1, "b": 2})
        keys = state.keys()
        assert set(keys) == {"a", "b"}

    def test_snapshot(self):
        state = State({"a": 1})
        snap = state.snapshot()
        assert snap == {"a": 1}
        snap["a"] = 999
        assert state.get("a") == 1

    def test_repr(self):
        state = State({"a": 1})
        assert "State" in repr(state)
        assert "a" in repr(state)
