"""Callback rows keep an address ready for a later exact-string lookup."""

from __future__ import annotations

import sqlite3

import pytest

from session_record.store import (
    FIND_MAX,
    PREVIEW_LEN,
    SCHEMA,
    RecordError,
    RecordStore,
)


def _store(tmp_path) -> RecordStore:
    store = RecordStore(tmp_path / "record.sqlite")
    store.initialize()
    return store


def _turn(text: str = "hello", ordinal: int = 0) -> dict:
    return {"ordinal": ordinal, "role": "user", "text": text}


def test_find_returns_the_address_and_the_matching_line(tmp_path) -> None:
    store = _store(tmp_path)
    long_line = "ZX-404 " + ("y" * 400)
    store.file_session(
        "alpha",
        "Licence pass",
        [
            {
                "ordinal": 0,
                "role": "user",
                "text": "Where did we leave the licence?",
            },
            {
                "ordinal": 4,
                "role": "tool",
                "tool_name": "read_file",
                "text": "intro stays off the preview\n" + long_line + "\nTAIL-SENTINEL",
            },
        ],
        project="widgets",
        host="grok",
        sections=[
            {
                "slug": "licence",
                "kind": "decision",
                "title": "Licence",
                "body": "Stay on MIT.\nSECTION-TAIL",
                "source_ordinal": 0,
            }
        ],
    )

    found = store.find("zx-404", project="widgets")
    assert found["truncated"] is False
    assert found["matches"] == [
        {
            "address": "alpha/turns/4",
            "session_id": "alpha",
            "title": "Licence pass",
            "unit": "turn",
            "preview": long_line[: PREVIEW_LEN - 3] + "...",
        }
    ]
    assert "TAIL-SENTINEL" not in str(found)
    assert "callback_text" not in found["matches"][0]
    assert "embedding_id" not in found["matches"][0]

    tool_hits = store.find("read_file")
    assert tool_hits["matches"][0]["address"] == "alpha/turns/4"
    assert "read_file" not in tool_hits["matches"][0]["preview"]

    section = store.find("stay on mit")
    assert section["matches"][0]["address"] == "alpha/sections/licence"
    assert section["matches"][0]["preview"] == "Stay on MIT."
    assert "SECTION-TAIL" not in str(section)

    other = store.file_session(
        "beta",
        "Other",
        [_turn("ZX-404 lives in the other project")],
        project="other",
    )
    assert other["session_id"] == "beta"
    assert {row["session_id"] for row in store.find("ZX-404")["matches"]} == {"alpha", "beta"}
    assert [row["session_id"] for row in store.find("ZX-404", project="other")["matches"]] == ["beta"]

    connection = sqlite3.connect(store.path)
    row = connection.execute(
        """
        SELECT callback_text, embedding_id, embedding_model
        FROM callbacks
        WHERE address = ?
        """,
        ("alpha/turns/4",),
    ).fetchone()
    assert row[1] is None
    assert row[2] is None
    assert "session alpha" in row[0]
    assert "tool read_file" in row[0]
    assert "TAIL-SENTINEL" in row[0]
    section_row = connection.execute(
        "SELECT callback_text FROM callbacks WHERE address = ?",
        ("alpha/sections/licence",),
    ).fetchone()
    assert "source 0" in section_row[0]
    assert connection.execute("SELECT version FROM schema_version").fetchone()[0] == 2
    connection.close()


def test_replace_and_add_section_keep_the_index_in_step(tmp_path) -> None:
    store = _store(tmp_path)
    store.file_session("alpha", "First", [_turn("OLD-TOKEN-42 is the original")])
    store.file_session(
        "alpha",
        "Second",
        [_turn("NEW-TOKEN-42 replaces it")],
        replace=True,
    )
    assert store.find("OLD-TOKEN-42")["matches"] == []
    assert store.find("NEW-TOKEN-42")["matches"][0]["address"] == "alpha/turns/0"

    added = store.add_section("alpha", "follow", "open", "Follow up", "OPEN-TOKEN-42 remains")
    assert added["source"] is None
    assert store.find("OPEN-TOKEN-42")["matches"][0]["address"] == "alpha/sections/follow"
    connection = sqlite3.connect(store.path)
    callback = connection.execute(
        "SELECT callback_text FROM callbacks WHERE address = ?",
        ("alpha/sections/follow",),
    ).fetchone()[0]
    assert "\nsource " not in callback
    fts_count = connection.execute("SELECT COUNT(*) FROM callbacks_fts").fetchone()[0]
    row_count = connection.execute("SELECT COUNT(*) FROM callbacks").fetchone()[0]
    assert fts_count == row_count == 2
    connection.close()


def test_find_reports_a_broken_index(tmp_path) -> None:
    store = _store(tmp_path)
    store.file_session("alpha", "T", [_turn("hello there")])
    connection = sqlite3.connect(store.path)
    connection.execute("DROP TABLE callbacks_fts")
    connection.execute("CREATE TABLE callbacks_fts (search_text TEXT)")
    connection.commit()
    connection.close()
    with pytest.raises(RecordError) as caught:
        store.find("hello")
    assert caught.value.code == "bad_query"


def test_find_rejects_a_short_query_and_a_bad_limit(tmp_path) -> None:
    store = _store(tmp_path)
    store.file_session("alpha", "T", [_turn("hello there")])
    for query in ("ab", "   ", None):
        with pytest.raises(RecordError) as caught:
            store.find(query)  # type: ignore[arg-type]
        assert caught.value.code == "bad_query"
    for limit in (0, FIND_MAX + 1):
        with pytest.raises(RecordError) as caught:
            store.find("hello", limit=limit)
        assert caught.value.code == "bad_page"


def test_find_pages_and_notices_a_missing_row(tmp_path) -> None:
    store = _store(tmp_path)
    store.file_session(
        "alpha",
        "T",
        [_turn(f"SAME-TOKEN line {index}", index) for index in range(3)],
        sections=[
            {
                "slug": "note1",
                "kind": "note",
                "title": "Note",
                "body": "SAME-TOKEN in a section",
            }
        ],
    )
    page = store.find("SAME-TOKEN", limit=2)
    assert page["truncated"] is True
    assert len(page["matches"]) == 2

    connection = sqlite3.connect(store.path)
    connection.execute("DELETE FROM turns WHERE session_id = 'alpha' AND ordinal = 0")
    connection.commit()
    connection.close()
    with pytest.raises(RecordError) as missing_turn:
        store.find("SAME-TOKEN line 0")
    assert missing_turn.value.code == "not_found"

    connection = sqlite3.connect(store.path)
    connection.execute("DELETE FROM sections WHERE session_id = 'alpha'")
    connection.commit()
    connection.close()
    with pytest.raises(RecordError) as missing_section:
        store.find("SAME-TOKEN in a section")
    assert missing_section.value.code == "not_found"


def test_version_one_rows_grow_callback_entries(tmp_path) -> None:
    path = tmp_path / "record.sqlite"
    connection = sqlite3.connect(path)
    connection.executescript(SCHEMA)
    connection.execute("INSERT INTO schema_version (version) VALUES (1)")
    connection.execute(
        """
        INSERT INTO sessions (id, title, project, host, started_at, filed_at)
        VALUES ('old', 'Old title', 'widgets', 'grok', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')
        """
    )
    connection.execute(
        """
        INSERT INTO turns (session_id, ordinal, role, tool_name, text)
        VALUES ('old', 0, 'user', '', 'TOKEN-FROM-V1 is on the first line')
        """
    )
    connection.execute(
        """
        INSERT INTO sections (session_id, slug, kind, title, body, source_ordinal, position)
        VALUES ('old', 'note1', 'note', 'Note', 'SECTION-FROM-V1 body', 0, 0)
        """
    )
    connection.execute(
        """
        INSERT INTO sessions (id, title, project, host, started_at, filed_at)
        VALUES ('empty', 'Empty', '', '', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')
        """
    )
    connection.commit()
    connection.close()

    store = RecordStore(path)
    assert store.find("TOKEN-FROM-V1")["matches"][0]["address"] == "old/turns/0"
    assert store.find("SECTION-FROM-V1")["matches"][0]["address"] == "old/sections/note1"

    connection = sqlite3.connect(path)
    assert connection.execute("SELECT version FROM schema_version").fetchone()[0] == 2
    count = connection.execute("SELECT COUNT(*) FROM callbacks").fetchone()[0]
    connection.execute("UPDATE schema_version SET version = 1")
    connection.commit()
    connection.close()

    store.initialize()
    connection = sqlite3.connect(path)
    assert connection.execute("SELECT COUNT(*) FROM callbacks").fetchone()[0] == count
    assert connection.execute("SELECT version FROM schema_version").fetchone()[0] == 2
    connection.close()
