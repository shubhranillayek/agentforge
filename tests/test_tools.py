"""Tests for tool schema generation in agentforge.tools."""
from __future__ import annotations

from typing import Annotated, Optional

from agentforge import ToolRegistry, tool


def props(t) -> dict:
    return t.schema["input_schema"]["properties"]


def required(t) -> list:
    return t.schema["input_schema"]["required"]


def test_primitive_types():
    @tool(description="primitives")
    def f(a: str, b: int, c: float, d: bool) -> None:
        return

    p = props(f)
    assert p["a"] == {"type": "string"}
    assert p["b"] == {"type": "integer"}
    assert p["c"] == {"type": "number"}
    assert p["d"] == {"type": "boolean"}
    assert required(f) == ["a", "b", "c", "d"]


def test_list_and_dict_types():
    @tool(description="containers")
    def f(names: list, config: dict) -> None:
        return

    p = props(f)
    assert p["names"]["type"] == "array"
    assert p["config"]["type"] == "object"


def test_parameterised_containers():
    @tool(description="parameterised")
    def f(nums: list[int], items: list[dict], mapping: dict[str, int]) -> None:
        return

    p = props(f)
    assert p["nums"] == {"type": "array", "items": {"type": "integer"}}
    assert p["items"] == {"type": "array", "items": {"type": "object"}}
    assert p["mapping"]["type"] == "object"
    assert p["mapping"]["additionalProperties"] == {"type": "integer"}


def test_optional_is_nullable_and_not_required():
    @tool(description="optional")
    def f(name: str, nickname: Optional[str], count: int | None = None) -> None:  # noqa: UP045 - testing Optional itself
        return

    p = props(f)
    assert p["nickname"]["type"] == "string"
    assert p["nickname"]["nullable"] is True
    assert p["count"]["type"] == "integer"
    assert p["count"]["nullable"] is True
    assert required(f) == ["name"]


def test_defaults_are_kept_and_not_required():
    @tool(description="defaults")
    def f(query: str, max_results: int = 3) -> None:
        return

    p = props(f)
    assert p["max_results"] == {"type": "integer", "default": 3}
    assert required(f) == ["query"]


def test_annotated_uses_inner_type():
    @tool(description="annotated")
    def f(age: Annotated[int, "years"]) -> None:
        return

    assert props(f)["age"] == {"type": "integer"}


def test_no_annotation_defaults_to_string():
    @tool(description="no hints")
    def f(x, y) -> None:
        return

    p = props(f)
    assert p["x"] == {"type": "string"}
    assert p["y"] == {"type": "string"}


def test_undefined_annotation_does_not_crash_decoration():
    # "SomeUndefinedClass" is never imported. Decoration used to raise
    # NameError here because get_type_hints() tried to resolve it.
    @tool(description="forward ref")
    def f(thing: "SomeUndefinedClass", n: int) -> None:  # noqa: F821, UP037 - deliberate forward reference
        return

    p = props(f)
    assert p["thing"] == {"type": "string"}
    assert p["n"] == {"type": "integer"}


def test_description_from_docstring_and_explicit():
    @tool()
    def f(x: str) -> None:
        """Docstring description.

        Extra detail that should not be included.
        """
        return

    assert f.description == "Docstring description."

    @tool(description="Explicit description.")
    def g(x: str) -> None:
        """Docstring that should be ignored."""
        return

    assert g.description == "Explicit description."


def test_tool_run_serialises_dict_and_list_results():
    @tool(description="dict result")
    def f() -> dict:
        return {"a": 1}

    assert f.run() == '{\n  "a": 1\n}'

    @tool(description="plain result")
    def g() -> int:
        return 12

    assert g.run() == "12"


def test_registry_lookup_and_schemas():
    @tool(description="one")
    def one(x: str) -> None:
        return

    @tool(description="two")
    def two(x: str) -> None:
        return

    registry = ToolRegistry(one)
    registry.add(two)
    assert len(registry) == 2
    assert registry.get("one") is one
    assert registry.get("missing") is None
    assert [s["name"] for s in registry.schemas()] == ["one", "two"]
