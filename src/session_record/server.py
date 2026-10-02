"""MCP server: file a session, read its map, refer to one address."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from session_record.grok import file_grok_transcript
from session_record.store import REFER_PAGE, RecordError, RecordStore

mcp = MCPServer(
    name="session-record",
    instructions="""
session-record stores a session as a record you can refer to later.

File the turns you still have, and name the decisions, files, and open items
as sections. Each section points at the turn it came from.

record_handoff reads a Grok chat_history.jsonl from a path. It files the
turns verbatim. System lines and reasoning lines are skipped. You still name
the sections.

record_map returns addresses and one-line previews, not the full text.
record_refer(address) returns one part:
  session id              the map
  session/turns/N         that turn, verbatim
  session/sections/slug   that named section

record_list shows sessions already filed. Use it when you know the project
or the title. record_find returns addresses for an exact string (a path, an
error code, a tool name). Open the address with record_refer.
""",
)

_store: RecordStore | None = None


def db_path() -> Path:
    configured = os.environ.get("SESSION_RECORD_DB")
    if configured:
        return Path(configured)
    return Path.home() / ".session-record" / "record.sqlite"


def get_store() -> RecordStore:
    global _store
    if _store is None:
        _store = RecordStore(db_path())
        _store.initialize()
    return _store


def _call(action) -> dict[str, Any]:
    try:
        return action()
    except RecordError as exc:
        return exc.to_dict()


@mcp.tool()
def record_file(
    session_id: str,
    title: str,
    turns: list[dict[str, Any]],
    project: str = "",
    host: str = "",
    started_at: str = "",
    sections: list[dict[str, Any]] | None = None,
    replace: bool = False,
) -> dict[str, Any]:
    """File a session.

    turns: {ordinal, role, text, tool_name?}. role is user, assistant, tool, or system.
    A tool turn needs tool_name.
    sections (optional): {slug, kind, title, body, source_ordinal?}.
    kind is decision, file, open, or note. source_ordinal is the turn it came from.
    Returns the map: addresses, not full text.
    """
    return _call(
        lambda: get_store().file_session(
            session_id,
            title,
            turns,
            project=project,
            host=host,
            started_at=started_at or None,
            sections=sections,
            replace=replace,
        )
    )


@mcp.tool()
def record_section(
    session_id: str,
    slug: str,
    kind: str,
    title: str,
    body: str,
    source_ordinal: int | None = None,
) -> dict[str, Any]:
    """Name one part of a session that is already filed.

    kind is decision, file, open, or note.
    source_ordinal points at the turn this section came from.
    """
    return _call(
        lambda: get_store().add_section(
            session_id,
            slug,
            kind,
            title,
            body,
            source_ordinal=source_ordinal,
        )
    )


@mcp.tool()
def record_map(
    session_id: str,
    outline_offset: int = 0,
    outline_limit: int = 0,
) -> dict[str, Any]:
    """Return the table of contents for one filed session.

    Sections and the tool index are always included.
    Set outline_limit (max 20) to page through one-line turn previews.
    Full text stays behind record_refer.
    """
    return _call(
        lambda: get_store().session_map(
            session_id,
            outline_offset=outline_offset,
            outline_limit=outline_limit,
        )
    )


@mcp.tool()
def record_refer(address: str, offset: int = 0, limit: int = REFER_PAGE) -> dict[str, Any]:
    """Return one addressed part of the record.

    address is a session id, session/turns/N, or session/sections/slug.
    A session id returns the map. A turn or section returns its text.
    Long text comes back in pages. Pass the next_offset to continue.
    """
    return _call(lambda: get_store().refer(address, offset=offset, limit=limit))


@mcp.tool()
def record_handoff(
    session_id: str,
    title: str,
    transcript_path: str,
    project: str = "",
    sections: list[dict[str, Any]] | None = None,
    replace: bool = False,
    started_at: str = "",
) -> dict[str, Any]:
    """File a Grok chat_history.jsonl from disk.

    The file is read as-is. User text, assistant text, tool calls, and tool
    results become turns numbered from 0. System lines and reasoning lines
    are skipped. sections use source_ordinal on those turn numbers.
    started_at records when the session started. Leave it empty and the
    filing time is used.
    Returns the map and the first page of turn previews.
    """
    return _call(
        lambda: file_grok_transcript(
            get_store(),
            session_id,
            title,
            transcript_path,
            project=project,
            sections=sections,
            replace=replace,
            started_at=started_at or None,
        )
    )


@mcp.tool()
def record_find(query: str, project: str = "", limit: int = 10) -> dict[str, Any]:
    """Find addresses that contain an exact string.

    query is at least 3 characters: a path, an error code, a tool name, or a
    short phrase. The result is addresses and one-line previews.
    Open one with record_refer.
    """
    return _call(
        lambda: get_store().find(
            query,
            project=project or None,
            limit=limit,
        )
    )


@mcp.tool()
def record_list(project: str = "", limit: int = 50) -> dict[str, Any]:
    """List filed sessions, newest first.

    Pass project to limit the list to one project. Each row has an address
    you can pass to record_map or record_refer.
    """
    return _call(
        lambda: get_store().list_sessions(
            project=project or None,
            limit=limit,
        )
    )
