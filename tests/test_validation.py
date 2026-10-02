"""The record refuses a session it could not refer back to cleanly."""

from __future__ import annotations

import pytest

from session_record.store import (
    MAX_TEXT,
    PREVIEW_LEN,
    REFER_PAGE,
    RecordError,
    preview,
    RecordStore,
)


def _store(tmp_path) -> RecordStore:
    store = RecordStore(tmp_path / "record.sqlite")
    store.initialize()
    store.initialize()
    return store


def _turn(**overrides):
    turn = {"ordinal": 0, "role": "user", "text": "hello"}
    turn.update(overrides)
    return turn


def test_rejected_sessions_name_the_problem(tmp_path) -> None:
    store = _store(tmp_path)
    cases = [
        ({"session_id": "Alpha", "title": "T", "turns": [_turn()]}, "bad_id"),
        ({"session_id": "alpha", "title": " ", "turns": [_turn()]}, "bad_text"),
        ({"session_id": "alpha", "title": "T", "turns": []}, "bad_session"),
        (
            {
                "session_id": "alpha",
                "title": "T",
                "turns": [_turn(), _turn(ordinal=0, text="again")],
            },
            "bad_turn",
        ),
        ({"session_id": "alpha", "title": "T", "turns": ["nope"]}, "bad_turn"),
        ({"session_id": "alpha", "title": "T", "turns": [_turn(ordinal=True)]}, "bad_turn"),
        ({"session_id": "alpha", "title": "T", "turns": [_turn(role="narrator")]}, "bad_turn"),
        (
            {
                "session_id": "alpha",
                "title": "T",
                "turns": [_turn(role="tool", tool_name="")],
            },
            "bad_turn",
        ),
        (
            {
                "session_id": "alpha",
                "title": "T",
                "turns": [_turn(role="tool", tool_name="has space")],
            },
            "bad_turn",
        ),
        (
            {
                "session_id": "alpha",
                "title": "T",
                "turns": [_turn(role="user", tool_name=12)],
            },
            "bad_turn",
        ),
        ({"session_id": "alpha", "title": "T", "turns": [_turn(text="")]}, "bad_text"),
        ({"session_id": "alpha", "title": "x" * 201, "turns": [_turn()]}, "bad_text"),
        (
            {
                "session_id": "alpha",
                "title": "T",
                "turns": [_turn()],
                "sections": ["nope"],
            },
            "bad_section",
        ),
        (
            {
                "session_id": "alpha",
                "title": "T",
                "turns": [_turn()],
                "sections": [
                    {"slug": "a", "kind": "poem", "title": "A", "body": "b"},
                ],
            },
            "bad_section",
        ),
        (
            {
                "session_id": "alpha",
                "title": "T",
                "turns": [_turn()],
                "sections": [
                    {
                        "slug": "a",
                        "kind": "note",
                        "title": "A",
                        "body": "b",
                        "source_ordinal": True,
                    },
                ],
            },
            "bad_section",
        ),
        (
            {
                "session_id": "alpha",
                "title": "T",
                "turns": [_turn()],
                "sections": [
                    {
                        "slug": "a",
                        "kind": "note",
                        "title": "A",
                        "body": "b",
                        "position": -1,
                    },
                ],
            },
            "bad_section",
        ),
        (
            {
                "session_id": "alpha",
                "title": "T",
                "turns": [_turn()],
                "sections": [
                    {"slug": "same", "kind": "note", "title": "A", "body": "one"},
                    {"slug": "same", "kind": "note", "title": "B", "body": "two"},
                ],
            },
            "bad_section",
        ),
    ]
    for kwargs, code in cases:
        with pytest.raises(RecordError) as caught:
            store.file_session(**kwargs)
        assert caught.value.code == code
        assert "code" in caught.value.to_dict()["error"]


def test_user_turn_does_not_keep_a_tool_name(tmp_path) -> None:
    store = _store(tmp_path)
    filed = store.file_session(
        "alpha",
        "T",
        [_turn(role="user", tool_name="pytest", text="noted")],
        project=None,
        host=None,
        started_at="  ",
    )
    assert filed["tools"] == {}
    assert filed["started_at"] != "  "
    assert "T" in filed["started_at"]
    assert "." in filed["started_at"]
    assert store.refer("alpha/turns/0")["tool_name"] == ""
    system = store.file_session(
        "beta",
        "T",
        [_turn(role="system", tool_name="pytest", text="noted")],
    )
    assert system["tools"] == {}
    assert store.refer("beta/turns/0")["tool_name"] == ""
    tool = store.file_session(
        "gamma",
        "T",
        [_turn(role="tool", tool_name="pytest", text="ran")],
    )
    assert tool["tools"] == {"pytest": ["gamma/turns/0"]}


def test_section_without_a_source_and_a_duplicate_name(tmp_path) -> None:
    store = _store(tmp_path)
    store.file_session(
        "alpha",
        "T",
        [_turn()],
        sections=[{"slug": "loose", "kind": "note", "title": "Loose", "body": "no turn"}],
    )
    assert store.refer("alpha/sections/loose")["source"] is None
    added = store.add_section("alpha", "also", "file", "Path", "src/app.py")
    assert added["source"] is None
    with pytest.raises(RecordError) as caught:
        store.add_section("alpha", "also", "note", "Again", "no")
    assert caught.value.code == "section_exists"
    with pytest.raises(RecordError) as missing:
        store.add_section("missing", "a", "note", "A", "b")
    assert missing.value.code == "not_found"


def test_pages_offsets_and_list_limit(tmp_path) -> None:
    store = _store(tmp_path)
    long_line = "n" * (PREVIEW_LEN + 10)
    store.file_session("alpha", "T", [_turn(text=long_line + "\nrest")])
    outline = store.session_map("alpha", outline_limit=1)
    assert outline["outline"][0]["preview"].endswith("...")
    assert len(outline["outline"][0]["preview"]) == PREVIEW_LEN

    with pytest.raises(RecordError) as page:
        store.refer("alpha/turns/0", offset=10_000)
    assert page.value.code == "bad_page"
    with pytest.raises(RecordError) as negative:
        store.refer("alpha/turns/0", offset=-1)
    assert negative.value.code == "bad_page"
    whole = store.refer("alpha/turns/0", limit=10_000)
    assert whole["continued"] is False
    long_body = "p" * (REFER_PAGE + 25)
    store.file_session("paged", "T", [_turn(text=long_body)])
    clamped = store.refer("paged/turns/0", limit=10_000)
    assert len(clamped["text"]) == REFER_PAGE
    assert clamped["text"] == long_body[:REFER_PAGE]
    assert clamped["continued"] is True
    remainder = store.refer("paged/turns/0", offset=clamped["next_offset"])
    assert remainder["text"] == long_body[REFER_PAGE:]
    assert remainder["continued"] is False

    with pytest.raises(RecordError) as outline_error:
        store.session_map("alpha", outline_limit=21)
    assert outline_error.value.code == "bad_page"
    with pytest.raises(RecordError) as outline_negative:
        store.session_map("alpha", outline_offset=-1)
    assert outline_negative.value.code == "bad_page"
    with pytest.raises(RecordError) as absent:
        store.session_map("missing")
    assert absent.value.code == "not_found"
    with pytest.raises(RecordError) as empty_address:
        store.refer("")
    assert empty_address.value.code == "bad_address"
    with pytest.raises(RecordError) as missing_turn:
        store.refer("alpha/turns/9")
    assert missing_turn.value.code == "not_found"

    for index in range(3):
        store.file_session(f"s{index}", "T", [_turn()], project="")
    listed = store.list_sessions(project="", limit=2)
    assert listed["truncated"] is True
    assert len(listed["sessions"]) == 2
    with pytest.raises(RecordError) as bad_limit:
        store.list_sessions(limit=0)
    assert bad_limit.value.code == "bad_page"


def test_oversized_text_is_refused(tmp_path) -> None:
    store = _store(tmp_path)
    with pytest.raises(RecordError) as caught:
        store.file_session("alpha", "T", [_turn(text="x" * (MAX_TEXT + 1))])
    assert caught.value.code == "bad_text"


def test_blank_preview() -> None:
    assert preview("   ") == ""
