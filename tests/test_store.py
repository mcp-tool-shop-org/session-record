"""The record keeps the original turn and hands back one address at a time."""

from __future__ import annotations

import pytest

from session_record.store import PREVIEW_LEN, RecordError, RecordStore

TURNS = [
    {"ordinal": 0, "role": "user", "text": "Where did we leave the licence?"},
    {
        "ordinal": 1,
        "role": "assistant",
        "text": "MIT, with the org as the copyright holder.\nSecond line stays in the turn.",
    },
    {
        "ordinal": 4,
        "role": "tool",
        "tool_name": "pytest",
        "text": "Error code TS-999\n" + ("x" * 5000),
    },
]

SECTIONS = [
    {
        "slug": "licence",
        "kind": "decision",
        "title": "Licence",
        "body": "The package stays MIT.",
        "source_ordinal": 1,
    }
]


def _store(tmp_path) -> RecordStore:
    store = RecordStore(tmp_path / "record.sqlite")
    store.initialize()
    return store


def test_map_is_addresses_and_refer_returns_the_turn(tmp_path) -> None:
    store = _store(tmp_path)
    filed = store.file_session(
        "alpha",
        "Licence pass",
        TURNS,
        project="widgets",
        host="claude",
        sections=SECTIONS,
    )

    assert filed["address"] == "alpha"
    assert filed["turn_count"] == 3
    assert "outline" not in filed
    assert filed["tools"] == {"pytest": ["alpha/turns/4"]}
    assert filed["sections"][0]["address"] == "alpha/sections/licence"
    assert filed["sections"][0]["source"] == "alpha/turns/1"
    assert "TS-999" not in str(filed)
    assert "Second line" not in str(filed)

    turn = store.refer("alpha/turns/4")
    assert turn["text"].startswith("Error code TS-999")
    assert turn["continued"] is True
    assert turn["tool_name"] == "pytest"
    rest = store.refer("alpha/turns/4", offset=turn["next_offset"])
    assert rest["continued"] is False
    assert "TS-999" not in rest["text"]

    section = store.refer("alpha/sections/licence")
    assert section["body"] == "The package stays MIT."
    assert section["source"] == "alpha/turns/1"

    as_session = store.refer("alpha")
    assert as_session["turn_count"] == 3
    assert "text" not in as_session


def test_outline_page_is_short_and_does_not_carry_the_body(tmp_path) -> None:
    store = _store(tmp_path)
    store.file_session("alpha", "Licence pass", TURNS, sections=SECTIONS)
    page = store.session_map("alpha", outline_offset=0, outline_limit=2)

    assert [row["address"] for row in page["outline"]] == [
        "alpha/turns/0",
        "alpha/turns/1",
    ]
    assert page["outline_truncated"] is True
    assert all(len(row["preview"]) <= PREVIEW_LEN for row in page["outline"])
    assert "Second line" not in page["outline"][1]["preview"]
    assert "TS-999" not in str(page["outline"])


def test_section_must_point_at_a_real_turn(tmp_path) -> None:
    store = _store(tmp_path)
    with pytest.raises(RecordError) as caught:
        store.file_session(
            "alpha",
            "Licence pass",
            TURNS,
            sections=[
                {
                    "slug": "missing",
                    "kind": "note",
                    "title": "Missing",
                    "body": "No such turn.",
                    "source_ordinal": 99,
                }
            ],
        )
    assert caught.value.code == "bad_source"


def test_add_section_after_filing(tmp_path) -> None:
    store = _store(tmp_path)
    store.file_session("alpha", "Licence pass", TURNS)
    added = store.add_section(
        "alpha",
        "still-open",
        "open",
        "Publish name",
        "The name is not settled.",
        source_ordinal=0,
    )
    assert added["address"] == "alpha/sections/still-open"
    assert added["source"] == "alpha/turns/0"
    assert store.refer("alpha/sections/still-open")["body"] == "The name is not settled."


def test_list_is_newest_first_and_can_filter_by_project(tmp_path) -> None:
    store = _store(tmp_path)
    store.file_session("older", "First", [TURNS[0]], project="widgets", started_at="2026-01-01T00:00:00+00:00")
    store.file_session("newer", "Second", [TURNS[0]], project="other", started_at="2026-02-01T00:00:00+00:00")

    listed = store.list_sessions()
    assert [row["session_id"] for row in listed["sessions"]] == ["newer", "older"]
    widgets = store.list_sessions(project="widgets")
    assert [row["session_id"] for row in widgets["sessions"]] == ["older"]
    assert widgets["sessions"][0]["address"] == "older"


def test_replace_is_explicit(tmp_path) -> None:
    store = _store(tmp_path)
    store.file_session("alpha", "Licence pass", TURNS)
    with pytest.raises(RecordError) as caught:
        store.file_session("alpha", "Again", [TURNS[0]])
    assert caught.value.code == "session_exists"
    replaced = store.file_session("alpha", "Again", [TURNS[0]], replace=True)
    assert replaced["title"] == "Again"
    assert replaced["turn_count"] == 1
    with pytest.raises(RecordError):
        store.refer("alpha/turns/4")


def test_sessions_do_not_share_turns(tmp_path) -> None:
    store = _store(tmp_path)
    store.file_session("alpha", "A", TURNS, sections=SECTIONS)
    store.file_session("beta", "B", [TURNS[0]])
    beta = store.session_map("beta")
    assert beta["sections"] == []
    assert beta["tools"] == {}
    with pytest.raises(RecordError) as caught:
        store.refer("beta/sections/licence")
    assert caught.value.code == "not_found"


def test_mcp_tools_file_and_refer(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SESSION_RECORD_DB", str(tmp_path / "record.sqlite"))
    import session_record.server as server

    server._store = None
    filed = server.record_file(
        "alpha",
        "Licence pass",
        [{"ordinal": 0, "role": "user", "text": "hello"}],
    )
    assert filed["address"] == "alpha"
    assert server.record_refer("alpha/turns/0")["text"] == "hello"
    names = {tool.name for tool in server.mcp._tool_manager.list_tools()}
    assert names == {
        "record_file",
        "record_section",
        "record_map",
        "record_refer",
        "record_list",
    }


def test_bad_address_names_the_three_forms(tmp_path) -> None:
    store = _store(tmp_path)
    with pytest.raises(RecordError) as caught:
        store.refer("../secret")
    assert caught.value.code == "bad_address"
