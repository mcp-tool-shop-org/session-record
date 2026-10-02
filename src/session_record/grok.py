"""File a Grok chat_history.jsonl without retyping it.

User text, assistant text, tool calls, and tool results become turns.
System lines and reasoning lines are skipped, including any encrypted
reasoning payload. Sections stay caller-supplied and point at the turn
ordinals this parser assigns, starting at 0.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from session_record.store import OUTLINE_MAX, RecordError, RecordStore


def file_grok_transcript(
    store: RecordStore,
    session_id: str,
    title: str,
    transcript_path: str,
    *,
    project: str = "",
    sections: list[dict[str, Any]] | None = None,
    replace: bool = False,
    started_at: str | None = None,
) -> dict[str, Any]:
    """Read one chat_history.jsonl and file it. Returns the map plus an outline."""
    path = Path(transcript_path)
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise RecordError("bad_transcript", "The transcript must be UTF-8.") from exc
    except OSError as exc:
        raise RecordError(
            "bad_transcript",
            f"Could not read the transcript at {transcript_path}.",
        ) from exc
    turns = turns_from_grok_jsonl(text)
    store.file_session(
        session_id,
        title,
        turns,
        project=project,
        host="grok",
        started_at=started_at,
        sections=sections,
        replace=replace,
    )
    return store.session_map(session_id, outline_limit=OUTLINE_MAX)


def turns_from_grok_jsonl(text: str) -> list[dict[str, Any]]:
    """Convert Grok chat_history.jsonl text into record turns."""
    turns: list[dict[str, Any]] = []
    calls: dict[str, str] = {}
    for line_no, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RecordError("bad_transcript", f"Line {line_no} is not JSON.") from exc
        if not isinstance(item, dict):
            raise RecordError("bad_transcript", f"Line {line_no} must be an object.")
        kind = item.get("type")
        if kind in ("system", "reasoning"):
            continue
        if kind == "user":
            body = _text_content(item.get("content"), line_no)
            if body.strip():
                turns.append(_turn(len(turns), "user", body))
            continue
        if kind == "assistant":
            _append_assistant(item, turns, calls, line_no)
            continue
        if kind == "tool_result":
            _append_tool_result(item, turns, calls, line_no)
            continue
        raise RecordError("bad_transcript", f"Line {line_no} has unsupported type {kind!r}.")
    return turns


def _append_assistant(
    item: dict[str, Any],
    turns: list[dict[str, Any]],
    calls: dict[str, str],
    line_no: int,
) -> None:
    content = item.get("content")
    if content is None:
        body = ""
    elif isinstance(content, str):
        body = content
    else:
        raise RecordError("bad_transcript", f"Line {line_no} assistant content must be text.")
    if body.strip():
        turns.append(_turn(len(turns), "assistant", body))
    tool_calls = item.get("tool_calls") or []
    if not isinstance(tool_calls, list):
        raise RecordError("bad_transcript", f"Line {line_no} tool_calls must be an array.")
    for call in tool_calls:
        if not isinstance(call, dict):
            raise RecordError("bad_transcript", f"Line {line_no} has a tool call that is not an object.")
        name = call.get("name")
        if not isinstance(name, str) or not name.strip():
            raise RecordError("bad_transcript", f"Line {line_no} has a tool call without a name.")
        name = name.strip()
        call_id = call.get("id")
        if isinstance(call_id, str) and call_id and call_id not in calls:
            calls[call_id] = name
        turns.append(_turn(len(turns), "tool", _call_text(call, name, line_no), tool_name=name))


def _append_tool_result(
    item: dict[str, Any],
    turns: list[dict[str, Any]],
    calls: dict[str, str],
    line_no: int,
) -> None:
    call_id = item.get("tool_call_id")
    if not isinstance(call_id, str) or call_id not in calls:
        raise RecordError("bad_transcript", f"Line {line_no} tool result does not match a tool call.")
    content = item.get("content")
    if content is None:
        return
    if isinstance(content, str):
        body = content
    elif isinstance(content, list):
        body = _text_content(content, line_no)
    else:
        raise RecordError("bad_transcript", f"Line {line_no} tool result must be text.")
    if body.strip():
        turns.append(_turn(len(turns), "tool", body, tool_name=calls[call_id]))


def _call_text(call: dict[str, Any], name: str, line_no: int) -> str:
    arguments = call.get("arguments")
    if arguments is None:
        return name
    if isinstance(arguments, str):
        return arguments if arguments.strip() else name
    if isinstance(arguments, dict):
        return json.dumps(arguments, sort_keys=True)
    raise RecordError("bad_transcript", f"Line {line_no} tool arguments must be text.")


def _text_content(content: object, line_no: int) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        raise RecordError("bad_transcript", f"Line {line_no} content must be text.")
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            if block.strip():
                parts.append(block)
            continue
        if not isinstance(block, dict):
            raise RecordError("bad_transcript", f"Line {line_no} has a content block that is not text.")
        text = block.get("text")
        if text is None:
            continue
        if not isinstance(text, str):
            raise RecordError("bad_transcript", f"Line {line_no} has a non-text block.")
        if text.strip():
            parts.append(text)
    return "\n".join(parts)


def _turn(ordinal: int, role: str, text: str, tool_name: str = "") -> dict[str, Any]:
    turn: dict[str, Any] = {"ordinal": ordinal, "role": role, "text": text}
    if tool_name:
        turn["tool_name"] = tool_name
    return turn
