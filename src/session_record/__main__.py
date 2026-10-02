"""Run the session-record MCP server, or file and refer from the shell.

Usage:
    python -m session_record
    session-record
    session-record file SESSION_ID TITLE PATH [--project P] [--host H] [--replace]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from session_record.grok import file_grok_transcript
from session_record.store import RecordError, RecordStore


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args or args[0] == "serve":
        return _serve()
    if args[0] in ("--version", "-V"):
        from session_record import __version__

        print(f"session-record {__version__}")
        return 0
    if args[0] in ("--help", "-h", "help"):
        print(_HELP)
        return 0
    commands = {
        "file": _file,
        "handoff": _handoff,
        "map": _map,
        "refer": _refer,
        "list": _list,
        "find": _find,
    }
    command = commands.get(args[0])
    if command is None:
        print(f"Unknown command {args[0]!r}.\n\n{_HELP}", file=sys.stderr)
        return 2
    try:
        return command(args[1:])
    except RecordError as exc:
        return _emit(exc.to_dict(), error=True)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return _emit({"error": {"code": "bad_file", "message": str(exc)}}, error=True)


def _serve() -> int:
    from session_record.server import mcp

    mcp.run(transport="stdio")
    return 0


def _file(args: list[str]) -> int:
    if len(args) < 3:
        print(_FILE_USAGE, file=sys.stderr)
        return 2
    session_id, title, path, *rest = args
    flags = _flags(
        rest,
        valued=("--project", "--host", "--started-at"),
        switches=("--replace",),
    )
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise RecordError("bad_file", "The session file must be a JSON object.")
    turns = document.get("turns")
    sections = document.get("sections", [])
    if not isinstance(turns, list):
        raise RecordError("bad_file", "The session file needs a turns array.")
    if not isinstance(sections, list):
        raise RecordError("bad_file", "sections must be an array.")
    filed = _store().file_session(
        session_id,
        title,
        turns,
        project=str(flags.get("--project", "")),
        host=str(flags.get("--host", "")),
        started_at=flags.get("--started-at"),
        sections=sections,
        replace="--replace" in flags,
    )
    return _emit(filed)


def _handoff(args: list[str]) -> int:
    if len(args) < 4:
        print(_HANDOFF_USAGE, file=sys.stderr)
        return 2
    host, session_id, title, path, *rest = args
    if host != "grok":
        raise RecordError(
            "bad_host",
            "This version reads a Grok chat_history.jsonl. Use host grok.",
        )
    flags = _flags(rest, valued=("--project", "--sections", "--started-at"), switches=("--replace",))
    sections: list[Any] = []
    if "--sections" in flags:
        loaded = json.loads(Path(flags["--sections"]).read_text(encoding="utf-8"))
        if not isinstance(loaded, list):
            raise RecordError("bad_file", "sections must be an array.")
        sections = loaded
    filed = file_grok_transcript(
        _store(),
        session_id,
        title,
        path,
        project=str(flags.get("--project", "")),
        sections=sections,
        replace="--replace" in flags,
        started_at=flags.get("--started-at"),
    )
    return _emit(filed)


def _find(args: list[str]) -> int:
    if not args:
        print("usage: session-record find TEXT [--project NAME] [--limit N]", file=sys.stderr)
        return 2
    flags = _flags(args[1:], valued=("--project", "--limit"), switches=())
    project = flags.get("--project")
    return _emit(
        _store().find(
            args[0],
            project=None if project is None else str(project),
            limit=_integer(flags.get("--limit"), default=10),
        )
    )


def _map(args: list[str]) -> int:
    if not args:
        print("usage: session-record map SESSION_ID [--outline-limit N]", file=sys.stderr)
        return 2
    flags = _flags(args[1:], valued=("--outline-offset", "--outline-limit"), switches=())
    return _emit(
        _store().session_map(
            args[0],
            outline_offset=_integer(flags.get("--outline-offset"), default=0),
            outline_limit=_integer(flags.get("--outline-limit"), default=0),
        )
    )


def _refer(args: list[str]) -> int:
    if not args:
        print("usage: session-record refer ADDRESS [--offset N] [--limit N]", file=sys.stderr)
        return 2
    flags = _flags(args[1:], valued=("--offset", "--limit"), switches=())
    limit = flags.get("--limit")
    return _emit(
        _store().refer(
            args[0],
            offset=_integer(flags.get("--offset"), default=0),
            limit=_integer(limit, default=4000) if limit is not None else 4000,
        )
    )


def _list(args: list[str]) -> int:
    flags = _flags(args, valued=("--project", "--limit"), switches=())
    project = flags.get("--project")
    return _emit(
        _store().list_sessions(
            project=None if project is None else str(project),
            limit=_integer(flags.get("--limit"), default=50),
        )
    )


def _store() -> RecordStore:
    from session_record.server import db_path

    store = RecordStore(db_path())
    store.initialize()
    return store


def _flags(
    args: list[str],
    *,
    valued: tuple[str, ...],
    switches: tuple[str, ...],
) -> dict[str, str]:
    found: dict[str, str] = {}
    index = 0
    while index < len(args):
        flag = args[index]
        if flag in switches:
            found[flag] = ""
            index += 1
            continue
        if flag in valued:
            if index + 1 >= len(args):
                raise ValueError(f"{flag} needs a value")
            found[flag] = args[index + 1]
            index += 2
            continue
        raise ValueError(f"Unknown option {flag}")
    return found


def _integer(value: str | None, *, default: int) -> int:
    if value is None:
        return default
    return int(value)


def _emit(payload: dict[str, Any], *, error: bool = False) -> int:
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 1 if error or "error" in payload else 0


_HELP = """session-record — store a session as a record you can refer to

Usage:
  session-record                         Run the MCP server on stdio
  session-record serve                   Run the MCP server on stdio
  session-record file ID TITLE PATH      File a JSON session and print its map
  session-record handoff grok ID TITLE PATH
                                     File a Grok chat_history.jsonl
  session-record map ID                  Print the map
  session-record refer ADDRESS           Print one addressed part
  session-record find TEXT               Find addresses for an exact string
  session-record list [--project NAME]   List filed sessions
  session-record --version
  session-record --help

The JSON file has a turns array and an optional sections array.
handoff reads chat_history.jsonl. Pass --sections with a JSON array of
sections whose source_ordinal values match the turns it assigns from 0.
Pass --started-at to record when the session started. Leave it off and
that time is the moment of filing.
find returns addresses and one-line previews. refer returns the text.
Set SESSION_RECORD_DB to the sqlite file. Otherwise the server uses
.session-record/record.sqlite under the home directory.
"""

_HANDOFF_USAGE = (
    "usage: session-record handoff grok SESSION_ID TITLE PATH "
    "[--project P] [--sections PATH] [--started-at T] [--replace]"
)

_FILE_USAGE = (
    "usage: session-record file SESSION_ID TITLE PATH "
    "[--project P] [--host H] [--started-at T] [--replace]"
)


if __name__ == "__main__":
    sys.exit(main())
