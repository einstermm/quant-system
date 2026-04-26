"""Small YAML subset reader for local strategy configs.

This is intentionally limited to the shapes used by the repository's strategy
configuration files: nested mappings, scalar values, and scalar lists.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class SimpleYAMLError(ValueError):
    """Raised when a local YAML file uses unsupported syntax."""


def load_simple_yaml(path: str | Path) -> dict[str, Any]:
    yaml_path = Path(path)
    lines = yaml_path.read_text(encoding="utf-8").splitlines()
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any] | list[Any]]] = [(-1, root)]

    for index, raw_line in enumerate(lines):
        if _skip_line(raw_line):
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        text = raw_line.strip()

        while indent <= stack[-1][0]:
            stack.pop()

        container = stack[-1][1]
        if text.startswith("- "):
            if not isinstance(container, list):
                raise SimpleYAMLError(f"{yaml_path}:{index + 1}: list item outside list")
            container.append(_parse_scalar(text[2:].strip()))
            continue

        key, separator, value = text.partition(":")
        if separator != ":" or not key.strip():
            raise SimpleYAMLError(f"{yaml_path}:{index + 1}: expected key: value")
        if not isinstance(container, dict):
            raise SimpleYAMLError(f"{yaml_path}:{index + 1}: mapping item inside list is unsupported")

        key = key.strip()
        value = value.strip()
        if value:
            container[key] = _parse_scalar(value)
            continue

        child: dict[str, Any] | list[Any]
        if _next_meaningful_line_starts_list(lines, index, indent):
            child = []
        else:
            child = {}
        container[key] = child
        stack.append((indent, child))

    return root


def _skip_line(raw_line: str) -> bool:
    stripped = raw_line.strip()
    return not stripped or stripped.startswith("#")


def _next_meaningful_line_starts_list(lines: list[str], current_index: int, indent: int) -> bool:
    for next_line in lines[current_index + 1 :]:
        if _skip_line(next_line):
            continue
        next_indent = len(next_line) - len(next_line.lstrip(" "))
        if next_indent <= indent:
            return False
        return next_line.strip().startswith("- ")
    return False


def _parse_scalar(value: str) -> str | bool | int | float | None:
    if value in {"null", "Null", "NULL", "~"}:
        return None
    if value in {"true", "True", "TRUE"}:
        return True
    if value in {"false", "False", "FALSE"}:
        return False
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    if value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
        return int(value)
    try:
        return float(value)
    except ValueError:
        return value
