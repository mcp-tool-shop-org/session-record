"""Filing a session from a JSON file, then referring to one address."""

from __future__ import annotations

import json

import pytest

from session_record.__main__ import main
from session_record.server import db_path, record_list, record_map, record_refer, record_section


def _db(tmp_path, monkeypatch):
    monkeypatch.setenv("SESSION_RECORD_DB", str(tmp_path / "record.sqlite"))


def _read(capsys) -> dict:
    return json.loads(capsys.readouterr().out)


def test_file_then_refer_and_list(tmp_path, monkeypatch, capsys) -> None:
    _db(tmp_path, monkeypatch)
    transcript = tmp_path / "session.json"
    transcript.write_text(
        json.dumps(
            {
                "turns": [
                    {"ordinal": 0, "role": "user", "text": "Keep the original error."},
                    {
                        "ordinal": 1,
                        "role": "tool",
                        "tool_name": "pytest",
                        "text": "Error code TS-999",
                    },
                ],
                "sections": [
                    {
                        "slug": "licence",
                        "kind": "decision",
                        "title": "Licence",
                        "body": "Stay MIT.",
                        "source_ordinal": 0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "file",
                "alpha",
                "Licence pass",
                str(transcript),
                "--project",
                "widgets",
                "--host",
                "claude",
                "--started-at",
                "2026-04-01T00:00:00+00:00",
            ]
        )
        == 0
    )
    filed = _read(capsys)
    assert filed["address"] == "alpha"
    assert filed["sections"][0]["source"] == "alpha/turns/0"
    assert "TS-999" not in json.dumps(filed)

    assert main(["refer", "alpha/turns/1"]) == 0
    assert _read(capsys)["text"] == "Error code TS-999"

    assert main(["map", "alpha", "--outline-limit", "1"]) == 0
    mapped = _read(capsys)
    assert mapped["outline"][0]["address"] == "alpha/turns/0"
    assert mapped["outline_truncated"] is True

    assert main(["list", "--project", "widgets", "--limit", "10"]) == 0
    assert _read(capsys)["sessions"][0]["session_id"] == "alpha"


def test_file_replace_and_bad_shapes(tmp_path, monkeypatch, capsys) -> None:
    _db(tmp_path, monkeypatch)
    first = tmp_path / "first.json"
    first.write_text(
        json.dumps({"turns": [{"ordinal": 0, "role": "user", "text": "one"}]}),
        encoding="utf-8",
    )
    second = tmp_path / "second.json"
    second.write_text(
        json.dumps({"turns": [{"ordinal": 0, "role": "user", "text": "two"}]}),
        encoding="utf-8",
    )
    assert main(["file", "alpha", "First", str(first)]) == 0
    _read(capsys)
    assert main(["file", "alpha", "Second", str(second), "--replace"]) == 0
    assert _read(capsys)["title"] == "Second"
    assert main(["refer", "alpha/turns/0"]) == 0
    assert _read(capsys)["text"] == "two"

    not_turns = tmp_path / "not-turns.json"
    not_turns.write_text(json.dumps({"turns": {}}), encoding="utf-8")
    assert main(["file", "beta", "T", str(not_turns)]) == 1
    assert _read(capsys)["error"]["code"] == "bad_file"

    not_sections = tmp_path / "not-sections.json"
    not_sections.write_text(
        json.dumps({"turns": [{"ordinal": 0, "role": "user", "text": "x"}], "sections": {}}),
        encoding="utf-8",
    )
    assert main(["file", "beta", "T", str(not_sections)]) == 1
    assert _read(capsys)["error"]["code"] == "bad_file"
    assert main(["list", "--limit"]) == 1
    assert "needs a value" in _read(capsys)["error"]["message"]


def test_file_rejects_a_transcript_without_turns(tmp_path, monkeypatch, capsys) -> None:
    _db(tmp_path, monkeypatch)
    path = tmp_path / "empty.json"
    path.write_text("[]", encoding="utf-8")
    assert main(["file", "alpha", "Title", str(path)]) == 1
    assert _read(capsys)["error"]["code"] == "bad_file"


def test_file_usage_and_unknown_command(capsys) -> None:
    assert main(["file"]) == 2
    assert "usage:" in capsys.readouterr().err
    assert main(["nope"]) == 2
    assert "Unknown command" in capsys.readouterr().err
    assert main(["--help"]) == 0
    assert "session-record file" in capsys.readouterr().out
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.startswith("session-record 0.1.0")


def test_serve_starts_the_mcp_transport(monkeypatch) -> None:
    import session_record.server as server

    seen: dict[str, str] = {}

    def fake_run(transport: str = "stdio") -> None:
        seen["transport"] = transport

    monkeypatch.setattr(server.mcp, "run", fake_run)
    assert main([]) == 0
    assert main(["serve"]) == 0
    assert seen["transport"] == "stdio"


def test_tools_return_errors_as_data(tmp_path, monkeypatch) -> None:
    _db(tmp_path, monkeypatch)
    import session_record.server as server

    server._store = None
    missing = record_refer("not-filed")
    assert missing["error"]["code"] == "not_found"
    assert record_map("not-filed")["error"]["code"] == "not_found"
    assert record_section("not-filed", "a", "note", "A", "body")["error"]["code"] == "not_found"
    listed = record_list()
    assert listed["sessions"] == []


def test_default_db_path_is_under_the_home_directory(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("SESSION_RECORD_DB", raising=False)
    monkeypatch.setattr("session_record.server.Path.home", lambda: tmp_path)
    assert db_path() == tmp_path / ".session-record" / "record.sqlite"


def test_bad_option_is_a_file_error(tmp_path, monkeypatch, capsys) -> None:
    _db(tmp_path, monkeypatch)
    assert main(["list", "--nope"]) == 1
    assert _read(capsys)["error"]["code"] == "bad_file"


@pytest.mark.parametrize(
    ("args", "code"),
    [
        (["refer"], None),
        (["map"], None),
    ],
)
def test_refer_and_map_need_an_address(args, code, capsys) -> None:
    assert main(args) == 2
    assert "usage:" in capsys.readouterr().err
    assert code is None
