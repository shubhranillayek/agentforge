"""Lightweight tool framework for AgentForge.

Define tools with plain type hints and let the framework infer the JSON
schema your model needs to call them.
"""
from __future__ import annotations

import inspect
import json
from dataclasses import dataclass, field
from typing import Any, Callable, get_type_hints

_PRIMITIVE_TYPES = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
}


@dataclass
class Tool:
    """A callable piece of agent functionality with an inferred schema."""

    name: str
    description: str
    func: Callable[..., Any]
    parameters: dict[str, Any] = field(default_factory=dict)

    def run(self, **kwargs: Any) -> str:
        result = self.func(**kwargs)
        if isinstance(result, (dict, list)):
            return json.dumps(result, indent=2)
        return str(result)

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": self.parameters,
                "required": [
                    name
                    for name, spec in self.parameters.items()
                    if "default" not in spec
                ],
            },
        }


def tool(
    name: str | None = None, description: str = ""
) -> Callable[[Callable[..., Any]], "Tool"]:
    """Turn a function into a :class:`Tool` with an inferred JSON schema."""

    def decorator(func: Callable[..., Any]) -> "Tool":
        signature = inspect.signature(func)
        hints = get_type_hints(func)
        properties: dict[str, Any] = {}
        for pname, param in signature.parameters.items():
            ptype = hints.get(pname, str)
            prop: dict[str, Any] = {"type": _PRIMITIVE_TYPES.get(ptype, "string")}
            if param.default is not inspect.Parameter.empty:
                prop["default"] = param.default
            properties[pname] = prop
        doc = description or inspect.getdoc(func) or ""
        return Tool(
            name=name or func.__name__,
            description=doc.split("\n\n")[0].strip(),
            func=func,
            parameters=properties,
        )

    return decorator


class ToolRegistry:
    """An ordered, name-indexed collection of tools."""

    def __init__(self, *tools: "Tool") -> None:
        self._tools: dict[str, "Tool"] = {t.name: t for t in tools}

    def add(self, tool: "Tool") -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> "Tool | None":
        return self._tools.get(name)

    def schemas(self) -> list[dict[str, Any]]:
        return [t.schema for t in self._tools.values()]

    def __iter__(self):
        return iter(self._tools.values())

    def __len__(self) -> int:
        return len(self._tools)
