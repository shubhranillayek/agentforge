"""Memory primitives for AgentForge agents."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Message:
    """A single conversation turn."""

    role: str  # "user" | "assistant" | "tool"
    content: str
    name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ConversationBufferMemory:
    """A bounded, append-only conversation log."""

    def __init__(self, max_messages: int = 50) -> None:
        self._messages: deque[Message] = deque(maxlen=max_messages)

    def add(self, message: Message) -> None:
        self._messages.append(message)

    def add_user(self, content: str) -> None:
        self.add(Message(role="user", content=content))

    def add_assistant(self, content: str) -> None:
        self.add(Message(role="assistant", content=content))

    def add_tool(self, name: str, content: str) -> None:
        self.add(Message(role="tool", name=name, content=content))

    def as_messages(self) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        for message in self._messages:
            entry: dict[str, Any] = {"role": message.role, "content": message.content}
            if message.name:
                entry["name"] = message.name
            messages.append(entry)
        return messages

    def clear(self) -> None:
        self._messages.clear()

    def __len__(self) -> int:
        return len(self._messages)
