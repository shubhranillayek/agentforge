"""Lightweight tool framework for AgentForge.

Define tools with plain type hints and let the framework infer the JSON
schema your model needs to call them.
"""
from __future__ import annotations

import inspect
import json
import types
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Annotated, Any, Union, get_args, get_origin, get_type_hints

_PRIMITIVE_TYPES = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
}

# Names used when an annotation could not be resolved to a real type
# (for example a forward reference to a class that is not imported).
_NAME_TYPES = {
    "str": "string",
    "string": "string",
    "int": "integer",
    "integer": "integer",
    "float": "number",
    "number": "number",
    "bool": "boolean",
    "boolean": "boolean",
    "list": "array",
    "dict": "object",
    "set": "array",
    "tuple": "array",
}


def _schema_for_string(name: str) -> dict[str, Any]:
    """Best-effort schema for an unresolved string annotation."""
    cleaned = name.strip().strip("'\"")
    lower = cleaned.lower()
    if lower in _NAME_TYPES:
        return {"type": _NAME_TYPES[lower]}
    for prefix in ("list[", "set[", "tuple[", "frozenset["):
        if lower.startswith(prefix):
            return {"type": "array"}
    if lower.startswith("dict"):
        return {"type": "object"}
    if lower.startswith("optional[") and cleaned.endswith("]"):
        inner = cleaned[cleaned.index("[") + 1 : -1]
        schema = _schema_for_string(inner)
        schema["nullable"] = True
        return schema
    return {"type": "string"}


def _schema_for_type(annotation: Any) -> dict[str, Any]:
    """Turn a Python type annotation into a JSON-schema fragment."""
    if annotation is Any or annotation is inspect.Parameter.empty:
        return {"type": "string"}
    if isinstance(annotation, str):
        return _schema_for_string(annotation)

    origin = get_origin(annotation)
    args = get_args(annotation)

    # Annotated[X, ...] -> schema of X
    if origin is Annotated and args:
        return _schema_for_type(args[0])

    # Optional[X] / Union[X, None] / X | None, and general unions
    if origin is Union or isinstance(annotation, types.UnionType):
        non_none = [a for a in args if a is not types.NoneType]
        if len(non_none) == 1 and len(non_none) != len(args):
            schema = _schema_for_type(non_none[0])
            schema["nullable"] = True
            return schema
        if non_none:
            return {"anyOf": [_schema_for_type(a) for a in non_none]}
        return {"type": "string"}

    if annotation in _PRIMITIVE_TYPES:
        return {"type": _PRIMITIVE_TYPES[annotation]}

    # list[X], set[X], tuple[X, ...]
    if annotation in (list, set, frozenset, tuple) or origin in (list, set, frozenset, tuple):
        schema: dict[str, Any] = {"type": "array"}
        if args and args[0] is not Ellipsis:
            schema["items"] = _schema_for_type(args[0])
        return schema

    # dict[K, V]
    if annotation is dict or origin is dict:
        schema: dict[str, Any] = {"type": "object"}
        if len(args) == 2:
            schema["additionalProperties"] = _schema_for_type(args[1])
        return schema

    return {"type": "string"}


def _is_optional(annotation: Any) -> bool:
    if isinstance(annotation, str):
        lower = annotation.strip().lower()
        return lower.startswith("optional[") or "| none" in lower or "none |" in lower
    origin = get_origin(annotation)
    if origin is Union or isinstance(annotation, types.UnionType):
        return types.NoneType in get_args(annotation)
    if origin is Annotated:
        args = get_args(annotation)
        return bool(args) and _is_optional(args[0])
    return False


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
                    if "default" not in spec and not spec.get("nullable")
                ],
            },
        }


def tool(
    name: str | None = None, description: str = ""
) -> Callable[[Callable[..., Any]], Tool]:
    """Turn a function into a :class:`Tool` with an inferred JSON schema."""

    def decorator(func: Callable[..., Any]) -> Tool:
        signature = inspect.signature(func)
        try:
            hints = get_type_hints(func, include_extras=True)
        except Exception:  # noqa: BLE001 - an unresolved hint must not break decoration
            # Fall back to the raw annotations from the signature. A missing
            # import in an annotation should not crash at decoration time.
            hints = {}
        properties: dict[str, Any] = {}
        for pname, param in signature.parameters.items():
            if pname in hints:
                ptype: Any = hints[pname]
            elif param.annotation is not inspect.Parameter.empty:
                ptype = param.annotation
            else:
                ptype = str
            prop = _schema_for_type(ptype)
            if _is_optional(ptype):
                prop["nullable"] = True
            if param.default is not inspect.Parameter.empty:
                try:
                    json.dumps(param.default)
                    prop["default"] = param.default
                except (TypeError, ValueError):
                    prop["default"] = None
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

    def __init__(self, *tools: Tool) -> None:
        self._tools: dict[str, Tool] = {t.name: t for t in tools}

    def add(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def schemas(self) -> list[dict[str, Any]]:
        return [t.schema for t in self._tools.values()]

    def __iter__(self):
        return iter(self._tools.values())

    def __len__(self) -> int:
        return len(self._tools)
