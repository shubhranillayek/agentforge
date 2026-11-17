"""Tests for the bounded conversation buffer in agentforge.memory."""
from __future__ import annotations

from agentforge import ConversationBufferMemory


def test_add_and_render_messages():
    mem = ConversationBufferMemory()
    mem.add_user("hello")
    mem.add_assistant("hi there")
    mem.add_tool("add", "12")
    assert mem.as_messages() == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
        {"role": "tool", "content": "12", "name": "add"},
    ]
    assert len(mem) == 3


def test_memory_is_bounded_and_drops_oldest():
    mem = ConversationBufferMemory(max_messages=5)
    for i in range(10):
        mem.add_user(f"msg {i}")
    assert len(mem) == 5
    contents = [m["content"] for m in mem.as_messages()]
    assert contents == ["msg 5", "msg 6", "msg 7", "msg 8", "msg 9"]


def test_clear_empties_memory():
    mem = ConversationBufferMemory()
    mem.add_user("hello")
    mem.clear()
    assert len(mem) == 0
    assert mem.as_messages() == []
