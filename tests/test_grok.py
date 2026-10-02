"""A Grok chat_history.jsonl files as turns. Reasoning stays out of the record."""

from __future__ import annotations

import json

import pytest

from session_record.grok import file_grok_transcript, turns_from_grok_jsonl
from session_record.store import RecordError, RecordStore


def _line(payload: dict) -> str:
    return json.dumps(payload)


def _transcript(*rows: dict) -> str:
    return "\n".join(_line(row) for row in rows) + "\n"


SAMPLE = _transcript(
    {"type": "system", "content": "SECRET-SYSTEM prompt"},
    {"type": "user", "content": [{"type": "text", "text": "Where is the widget licence?"}]},
    {
        "type": "reasoning",
        "summary": [{"type": "summary_text", "text": "HIDDEN-REASONING"}],
        "encrypted_content": "ENCRYPTED-BLOB",
    },
    {
        "type": "assistant",
        "content": "It is MIT.\nSENTINEL-SECOND-LINE",
        "encrypted_content": "ENCRYPTED-BLOB",
        "tool_calls": [
            {
                "id": "call_1",
                "name": "read_file",
                "arguments": '{"target_file": "src/session_record/store.py"}',
            }
        ],
    },
    {
        "type": "tool_result",
        "tool_call_id": "call_1",
        "content": "short\nError code ZX-404\nTAIL-SENTINEL",
    },
    {"type": "user", "content": "Thanks"},
)


def test_handoff_files_turns_and_skips_reasoning(tmp_path) -> None:
    path = tmp_path / "chat_history.jsonl"
    path.write_text(SAMPLE, encoding="utf-8")
    sections = [
        {
            "slug": "licence",
            "kind": "decision",
            "title": "Licence",
            "body": "Stay on MIT.",
            "source_ordinal": 1,
        }
    ]
    store = RecordStore(tmp_path / "record.sqlite")
    filed = file_grok_transcript(
        store,
        "alpha",
        "Licence pass",
        str(path),
        project="widgets",
        sections=sections,
        started_at="2026-04-01T00:00:00+00:00",
    )

    assert filed["host"] == "grok"
    assert filed["turn_count"] == 5
    assert [row["address"] for row in filed["outline"]] == [
        "alpha/turns/0",
        "alpha/turns/1",
        "alpha/turns/2",
        "alpha/turns/3",
        "alpha/turns/4",
    ]
    assert filed["outline"][1]["preview"] == "It is MIT."
    assert filed["sections"][0]["source"] == "alpha/turns/1"
    assert "SENTINEL-SECOND-LINE" not in json.dumps(filed)
    assert "ENCRYPTED-BLOB" not in json.dumps(filed)

    assert store.refer("alpha/turns/0")["text"] == "Where is the widget licence?"
    assert store.refer("alpha/turns/1")["role"] == "assistant"
    call = store.refer("alpha/turns/2")
    assert call["tool_name"] == "read_file"
    assert "store.py" in call["text"]
    result = store.refer("alpha/turns/3")
    assert result["tool_name"] == "read_file"
    assert "ZX-404" in result["text"]
    assert store.refer("alpha/turns/4")["text"] == "Thanks"

    blob = (tmp_path / "record.sqlite").read_bytes()
    assert b"ENCRYPTED-BLOB" not in blob
    assert b"SECRET-SYSTEM" not in blob
    assert b"HIDDEN-REASONING" not in blob

    found = store.find("ZX-404")
    assert found["matches"][0]["address"] == "alpha/turns/3"
    assert found["matches"][0]["preview"] == "Error code ZX-404"
    assert "TAIL-SENTINEL" not in str(found)
    assert store.find("store.py")["matches"][0]["address"] == "alpha/turns/2"


def test_parser_shapes(tmp_path) -> None:
    text = _transcript(
        {"type": "user", "content": "   "},
        {
            "type": "user",
            "content": [
                {"type": "image"},
                {"type": "text", "text": "hello from parts"},
                "plain block",
            ],
        },
        {"type": "assistant", "content": "   ", "tool_calls": []},
        {
            "type": "assistant",
            "content": "",
            "tool_calls": [
                {"id": "c1", "name": "read_file", "arguments": {"b": 1, "a": 2}},
                {"id": "c1", "name": "other_tool", "arguments": "   "},
                {"name": "read_file", "arguments": ""},
            ],
        },
        {"type": "tool_result", "tool_call_id": "c1", "content": None},
        {
            "type": "tool_result",
            "tool_call_id": "c1",
            "content": [{"type": "text", "text": "from a block"}],
        },
        {"type": "tool_result", "tool_call_id": "c1", "content": "   "},
        {"type": "user", "content": "plain user line"},
        {"type": "user", "content": None},
        {"type": "assistant", "tool_calls": [{"name": "read_file"}]},
    )
    turns = turns_from_grok_jsonl("\n" + text)
    assert [turn["role"] for turn in turns] == [
        "user",
        "tool",
        "tool",
        "tool",
        "tool",
        "user",
        "tool",
    ]
    assert turns[0]["text"] == "hello from parts\nplain block"
    assert turns[1]["text"] == '{"a": 2, "b": 1}'
    assert turns[1]["tool_name"] == "read_file"
    assert turns[2]["tool_name"] == "other_tool"
    assert turns[2]["text"] == "other_tool"
    assert turns[3]["text"] == "read_file"
    assert turns[4]["text"] == "from a block"
    assert turns[4]["tool_name"] == "read_file"
    assert turns[5]["text"] == "plain user line"
    assert turns[6]["tool_name"] == "read_file"
    assert turns[6]["text"] == "read_file"

    path = tmp_path / "only_system.jsonl"
    path.write_text(_transcript({"type": "system", "content": "no turns here at all"}), encoding="utf-8")
    store = RecordStore(tmp_path / "record.sqlite")
    with pytest.raises(RecordError) as caught:
        file_grok_transcript(store, "alpha", "Empty", str(path))
    assert caught.value.code == "bad_session"


@pytest.mark.parametrize(
    ("rows", "fragment"),
    [
        (["{"], "not JSON"),
        (["1"], "must be an object"),
        ([_line({"type": "image"})], "unsupported type"),
        ([_line({"type": "user", "content": 1})], "content must be text"),
        ([_line({"type": "user", "content": [1]})], "not text"),
        ([_line({"type": "user", "content": [{"text": 1}]})], "non-text block"),
        ([_line({"type": "assistant", "content": []})], "assistant content"),
        ([_line({"type": "assistant", "content": "hi", "tool_calls": "nope"})], "tool_calls"),
        ([_line({"type": "assistant", "content": "hi", "tool_calls": ["x"]})], "not an object"),
        ([_line({"type": "assistant", "content": "hi", "tool_calls": [{"id": "a"}]})], "without a name"),
        (
            [_line({"type": "assistant", "content": "hi", "tool_calls": [{"name": "read_file", "arguments": 1}]})],
            "tool arguments",
        ),
        ([_line({"type": "tool_result", "content": "orphan result text"})], "does not match"),
        (
            [
                _line({"type": "assistant", "content": "", "tool_calls": [{"id": "c", "name": "read_file", "arguments": "abc"}]}),
                _line({"type": "tool_result", "tool_call_id": "c", "content": 1}),
            ],
            "tool result must be text",
        ),
        (
            [
                _line({"type": "assistant", "content": "", "tool_calls": [{"id": 7, "name": "read_file", "arguments": "abc"}]}),
                _line({"type": "tool_result", "tool_call_id": "7", "content": "later result"}),
            ],
            "does not match",
        ),
    ],
)
def test_parser_rejects_a_bad_line(rows, fragment) -> None:
    with pytest.raises(RecordError) as caught:
        turns_from_grok_jsonl("\n".join(rows))
    assert caught.value.code == "bad_transcript"
    assert fragment in str(caught.value)


def test_file_errors_and_mcp_handoff(tmp_path, monkeypatch) -> None:
    store = RecordStore(tmp_path / "record.sqlite")
    missing = tmp_path / "missing.jsonl"
    with pytest.raises(RecordError) as missing_error:
        file_grok_transcript(store, "alpha", "T", str(missing))
    assert missing_error.value.code == "bad_transcript"
    assert "Could not read" in str(missing_error.value)

    bad_bytes = tmp_path / "bad.jsonl"
    bad_bytes.write_bytes(b"\xff\xfe")
    with pytest.raises(RecordError) as decode_error:
        file_grok_transcript(store, "alpha", "T", str(bad_bytes))
    assert decode_error.value.code == "bad_transcript"
    assert "UTF-8" in str(decode_error.value)

    path = tmp_path / "chat_history.jsonl"
    path.write_text(
        _transcript({"type": "user", "content": "Keep this sentence for the handoff."}),
        encoding="utf-8",
    )
    monkeypatch.setenv("SESSION_RECORD_DB", str(tmp_path / "mcp.sqlite"))
    import session_record.server as server

    server._store = None
    filed = server.record_handoff("alpha", "Licence pass", str(path), project="widgets")
    assert filed["outline"][0]["address"] == "alpha/turns/0"
    found = server.record_find("handoff", project="widgets")
    assert found["matches"][0]["address"] == "alpha/turns/0"
    assert server.record_find("ab")["error"]["code"] == "bad_query"
    assert server.record_handoff("beta", "T", str(missing))["error"]["code"] == "bad_transcript"
