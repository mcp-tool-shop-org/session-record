"""SQLite record of a session, addressed so a later turn can refer to one part.

A session holds verbatim turns and optional named sections. The map is the
table of contents: section addresses, a tool index, and how to name a turn.
Full text comes back only from refer.
"""

from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
ROLES = frozenset({"user", "assistant", "tool", "system"})
KINDS = frozenset({"decision", "file", "open", "note"})
PREVIEW_LEN = 160
REFER_PAGE = 4000
OUTLINE_MAX = 20
MAX_TEXT = 2_000_000

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    project TEXT NOT NULL DEFAULT '',
    host TEXT NOT NULL DEFAULT '',
    started_at TEXT NOT NULL,
    filed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS turns (
    session_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    role TEXT NOT NULL,
    tool_name TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL,
    PRIMARY KEY (session_id, ordinal),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sections (
    session_id TEXT NOT NULL,
    slug TEXT NOT NULL,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    source_ordinal INTEGER,
    position INTEGER NOT NULL,
    PRIMARY KEY (session_id, slug),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (session_id, source_ordinal)
        REFERENCES turns(session_id, ordinal)
);

CREATE INDEX IF NOT EXISTS idx_turns_tool
    ON turns(session_id, tool_name);
CREATE INDEX IF NOT EXISTS idx_sections_order
    ON sections(session_id, position);
"""


class RecordError(Exception):
    """A failure the caller can show to the model."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": str(self)}}


@dataclass(frozen=True)
class Address:
    session_id: str
    kind: str
    ordinal: int | None = None
    slug: str | None = None


def check_id(value: str, *, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise RecordError(
            "bad_id",
            f"{label} must be 1-64 characters: a lowercase letter or digit, "
            "then letters, digits, '_' or '-'.",
        )
    return value


def turn_address(session_id: str, ordinal: int) -> str:
    return f"{session_id}/turns/{ordinal}"


def section_address(session_id: str, slug: str) -> str:
    return f"{session_id}/sections/{slug}"


def parse_address(raw: str) -> Address:
    if not isinstance(raw, str) or not raw.strip():
        raise RecordError(
            "bad_address",
            "Pass a session id, session/turns/N, or session/sections/slug.",
        )
    parts = raw.strip().split("/")
    if len(parts) == 1:
        return Address(check_id(parts[0], label="session id"), "session")
    if len(parts) == 3 and parts[1] == "turns" and parts[2].isdigit():
        return Address(
            check_id(parts[0], label="session id"),
            "turn",
            ordinal=int(parts[2]),
        )
    if len(parts) == 3 and parts[1] == "sections":
        return Address(
            check_id(parts[0], label="session id"),
            "section",
            slug=check_id(parts[2], label="section slug"),
        )
    raise RecordError(
        "bad_address",
        "Pass a session id, session/turns/N, or session/sections/slug.",
    )


def preview(text: str, limit: int = PREVIEW_LEN) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    line = " ".join(stripped.splitlines()[0].split())
    if len(line) <= limit:
        return line
    return line[: limit - 3] + "..."


def _clean_text(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RecordError("bad_text", f"{label} needs text.")
    if len(value) > MAX_TEXT:
        raise RecordError("bad_text", f"{label} is over {MAX_TEXT} characters.")
    return value


def _clean_title(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RecordError("bad_text", f"{label} needs a title.")
    title = " ".join(value.split())
    if len(title) > 200:
        raise RecordError("bad_text", f"{label} title is over 200 characters.")
    return title


class RecordStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(SCHEMA)
            row = connection.execute("SELECT version FROM schema_version").fetchone()
            if row is None:
                connection.execute("INSERT INTO schema_version (version) VALUES (1)")

    def file_session(
        self,
        session_id: str,
        title: str,
        turns: list[dict[str, Any]],
        *,
        project: str = "",
        host: str = "",
        started_at: str | None = None,
        sections: list[dict[str, Any]] | None = None,
        replace: bool = False,
    ) -> dict[str, Any]:
        """Store one session. Returns its map."""
        session_id = check_id(session_id, label="session id")
        title = _clean_title(title, label="session")
        project = project.strip() if isinstance(project, str) else ""
        host = host.strip() if isinstance(host, str) else ""
        parsed_turns = [_parse_turn(turn) for turn in turns]
        if not parsed_turns:
            raise RecordError("bad_session", "A session needs at least one turn.")
        ordinals = [turn["ordinal"] for turn in parsed_turns]
        if len(ordinals) != len(set(ordinals)):
            raise RecordError("bad_turn", "Turn ordinals must be unique.")
        parsed_sections = [
            _parse_section(section, index, ordinals)
            for index, section in enumerate(sections or [])
        ]
        slugs = [section["slug"] for section in parsed_sections]
        if len(slugs) != len(set(slugs)):
            raise RecordError("bad_section", "Section slugs must be unique in a session.")
        when = started_at.strip() if isinstance(started_at, str) and started_at.strip() else _now()
        filed_at = _now()

        self.initialize()
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT id FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            if existing is not None and not replace:
                raise RecordError(
                    "session_exists",
                    f"Session {session_id} is already filed. Pass replace to file it again.",
                )
            if existing is not None:
                connection.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            connection.execute(
                """
                INSERT INTO sessions (id, title, project, host, started_at, filed_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, title, project, host, when, filed_at),
            )
            connection.executemany(
                """
                INSERT INTO turns (session_id, ordinal, role, tool_name, text)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (session_id, turn["ordinal"], turn["role"], turn["tool_name"], turn["text"])
                    for turn in parsed_turns
                ],
            )
            if parsed_sections:
                connection.executemany(
                    """
                    INSERT INTO sections
                        (session_id, slug, kind, title, body, source_ordinal, position)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            session_id,
                            section["slug"],
                            section["kind"],
                            section["title"],
                            section["body"],
                            section["source_ordinal"],
                            section["position"],
                        )
                        for section in parsed_sections
                    ],
                )
        return self.session_map(session_id)

    def add_section(
        self,
        session_id: str,
        slug: str,
        kind: str,
        title: str,
        body: str,
        *,
        source_ordinal: int | None = None,
    ) -> dict[str, Any]:
        """Attach one named section to a session that is already filed."""
        session_id = check_id(session_id, label="session id")
        self.initialize()
        with self._connect() as connection:
            ordinals = [
                row["ordinal"]
                for row in connection.execute(
                    "SELECT ordinal FROM turns WHERE session_id = ?",
                    (session_id,),
                )
            ]
            if not ordinals:
                raise RecordError("not_found", f"Session {session_id} is not filed.")
            position_row = connection.execute(
                "SELECT COALESCE(MAX(position), -1) + 1 AS next_pos FROM sections WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            section = _parse_section(
                {
                    "slug": slug,
                    "kind": kind,
                    "title": title,
                    "body": body,
                    "source_ordinal": source_ordinal,
                },
                int(position_row["next_pos"]),
                ordinals,
            )
            try:
                connection.execute(
                    """
                    INSERT INTO sections
                        (session_id, slug, kind, title, body, source_ordinal, position)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        section["slug"],
                        section["kind"],
                        section["title"],
                        section["body"],
                        section["source_ordinal"],
                        section["position"],
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise RecordError(
                    "section_exists",
                    f"Section {section['slug']} is already on session {session_id}.",
                ) from exc
        return {
            "address": section_address(session_id, section["slug"]),
            "source": (
                turn_address(session_id, section["source_ordinal"])
                if section["source_ordinal"] is not None
                else None
            ),
        }

    def session_map(
        self,
        session_id: str,
        *,
        outline_offset: int = 0,
        outline_limit: int = 0,
    ) -> dict[str, Any]:
        """Table of contents. Turn previews stay out unless an outline page is asked for."""
        session_id = check_id(session_id, label="session id")
        if outline_offset < 0 or outline_limit < 0:
            raise RecordError("bad_page", "outline_offset and outline_limit must be >= 0.")
        if outline_limit > OUTLINE_MAX:
            raise RecordError("bad_page", f"outline_limit must be <= {OUTLINE_MAX}.")
        self.initialize()
        with self._connect() as connection:
            session = connection.execute(
                "SELECT * FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            if session is None:
                raise RecordError("not_found", f"Session {session_id} is not filed.")
            turn_count = connection.execute(
                "SELECT COUNT(*) AS n FROM turns WHERE session_id = ?",
                (session_id,),
            ).fetchone()["n"]
            sections = connection.execute(
                """
                SELECT slug, kind, title, body, source_ordinal
                FROM sections
                WHERE session_id = ?
                ORDER BY position
                """,
                (session_id,),
            ).fetchall()
            tools = connection.execute(
                """
                SELECT tool_name, ordinal
                FROM turns
                WHERE session_id = ? AND tool_name != ''
                ORDER BY ordinal
                """,
                (session_id,),
            ).fetchall()
            outline: list[dict[str, Any]] = []
            outline_truncated = False
            if outline_limit:
                rows = connection.execute(
                    """
                    SELECT ordinal, role, tool_name, text
                    FROM turns
                    WHERE session_id = ?
                    ORDER BY ordinal
                    LIMIT ? OFFSET ?
                    """,
                    (session_id, outline_limit + 1, outline_offset),
                ).fetchall()
                outline_truncated = len(rows) > outline_limit
                outline = [_turn_preview(session_id, row) for row in rows[:outline_limit]]
        tool_index: dict[str, list[str]] = {}
        for row in tools:
            tool_index.setdefault(row["tool_name"], []).append(
                turn_address(session_id, row["ordinal"])
            )
        result: dict[str, Any] = {
            "session_id": session_id,
            "title": session["title"],
            "project": session["project"],
            "host": session["host"],
            "started_at": session["started_at"],
            "address": session_id,
            "turn_count": turn_count,
            "turn_address": f"{session_id}/turns/{{n}}",
            "sections": [_section_preview(session_id, row) for row in sections],
            "tools": tool_index,
        }
        if outline_limit:
            result["outline"] = outline
            result["outline_offset"] = outline_offset
            result["outline_truncated"] = outline_truncated
        return result

    def refer(self, address: str, *, offset: int = 0, limit: int = REFER_PAGE) -> dict[str, Any]:
        """Return one addressed part. A bare session id returns the map."""
        parsed = parse_address(address)
        if offset < 0 or limit < 1:
            raise RecordError("bad_page", "offset must be >= 0 and limit must be >= 1.")
        if limit > REFER_PAGE:
            limit = REFER_PAGE
        if parsed.kind == "session":
            return self.session_map(parsed.session_id)
        self.initialize()
        with self._connect() as connection:
            if parsed.kind == "turn":
                row = connection.execute(
                    """
                    SELECT ordinal, role, tool_name, text
                    FROM turns
                    WHERE session_id = ? AND ordinal = ?
                    """,
                    (parsed.session_id, parsed.ordinal),
                ).fetchone()
                if row is None:
                    raise RecordError("not_found", f"{address} is not in the record.")
                page, continued, next_offset = _page(row["text"], offset, limit)
                return {
                    "address": turn_address(parsed.session_id, row["ordinal"]),
                    "session_id": parsed.session_id,
                    "ordinal": row["ordinal"],
                    "role": row["role"],
                    "tool_name": row["tool_name"],
                    "text": page,
                    "offset": offset,
                    "continued": continued,
                    "next_offset": next_offset,
                }
            row = connection.execute(
                """
                SELECT slug, kind, title, body, source_ordinal
                FROM sections
                WHERE session_id = ? AND slug = ?
                """,
                (parsed.session_id, parsed.slug),
            ).fetchone()
            if row is None:
                raise RecordError("not_found", f"{address} is not in the record.")
            page, continued, next_offset = _page(row["body"], offset, limit)
            source = (
                turn_address(parsed.session_id, row["source_ordinal"])
                if row["source_ordinal"] is not None
                else None
            )
            return {
                "address": section_address(parsed.session_id, row["slug"]),
                "session_id": parsed.session_id,
                "kind": row["kind"],
                "title": row["title"],
                "body": page,
                "source": source,
                "offset": offset,
                "continued": continued,
                "next_offset": next_offset,
            }

    def list_sessions(
        self,
        *,
        project: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """List filed sessions, newest first. This is the way back to an older one."""
        if limit < 1 or limit > 100:
            raise RecordError("bad_page", "limit must be from 1 to 100.")
        self.initialize()
        query = """
            SELECT
                s.id,
                s.title,
                s.project,
                s.host,
                s.started_at,
                s.filed_at,
                (SELECT COUNT(*) FROM turns t WHERE t.session_id = s.id) AS turn_count,
                (SELECT COUNT(*) FROM sections c WHERE c.session_id = s.id) AS section_count
            FROM sessions s
        """
        parameters: list[Any] = []
        if project is not None and project != "":
            query += " WHERE s.project = ?"
            parameters.append(project)
        query += " ORDER BY s.filed_at DESC, s.id ASC LIMIT ?"
        parameters.append(limit + 1)
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        truncated = len(rows) > limit
        sessions = [
            {
                "session_id": row["id"],
                "title": row["title"],
                "project": row["project"],
                "host": row["host"],
                "started_at": row["started_at"],
                "filed_at": row["filed_at"],
                "turn_count": row["turn_count"],
                "section_count": row["section_count"],
                "address": row["id"],
            }
            for row in rows[:limit]
        ]
        return {"sessions": sessions, "truncated": truncated}


def _parse_turn(turn: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(turn, dict):
        raise RecordError("bad_turn", "Each turn must be an object.")
    ordinal = turn.get("ordinal")
    if isinstance(ordinal, bool) or not isinstance(ordinal, int) or ordinal < 0:
        raise RecordError("bad_turn", "Each turn needs an ordinal integer >= 0.")
    role = turn.get("role")
    if role not in ROLES:
        raise RecordError("bad_turn", "role must be user, assistant, tool, or system.")
    tool_name = turn.get("tool_name") or ""
    if not isinstance(tool_name, str):
        raise RecordError("bad_turn", "tool_name must be a string.")
    tool_name = tool_name.strip()
    if role == "tool" and not tool_name:
        raise RecordError("bad_turn", "A tool turn needs tool_name.")
    if role != "tool":
        tool_name = ""
    if tool_name and not re.fullmatch(r"[A-Za-z0-9_.:-]{1,80}", tool_name):
        raise RecordError(
            "bad_turn",
            "tool_name must be 1-80 characters: letters, digits, '_', '.', ':', or '-'.",
        )
    return {
        "ordinal": ordinal,
        "role": role,
        "tool_name": tool_name,
        "text": _clean_text(turn.get("text"), label=f"turn {ordinal}"),
    }


def _parse_section(
    section: dict[str, Any],
    position: int,
    ordinals: list[int],
) -> dict[str, Any]:
    if not isinstance(section, dict):
        raise RecordError("bad_section", "Each section must be an object.")
    slug = check_id(str(section.get("slug", "")), label="section slug")
    kind = section.get("kind")
    if kind not in KINDS:
        raise RecordError("bad_section", "kind must be decision, file, open, or note.")
    source = section.get("source_ordinal")
    if source is not None:
        if isinstance(source, bool) or not isinstance(source, int):
            raise RecordError("bad_section", "source_ordinal must be an integer.")
        if source not in ordinals:
            raise RecordError(
                "bad_source",
                f"Section {slug} points at turn {source}, which is not in this session.",
            )
    given = section.get("position", position)
    if isinstance(given, bool) or not isinstance(given, int) or given < 0:
        raise RecordError("bad_section", "position must be an integer >= 0.")
    return {
        "slug": slug,
        "kind": kind,
        "title": _clean_title(section.get("title"), label=f"section {slug}"),
        "body": _clean_text(section.get("body"), label=f"section {slug}"),
        "source_ordinal": source,
        "position": given,
    }


def _turn_preview(session_id: str, row: sqlite3.Row) -> dict[str, Any]:
    return {
        "address": turn_address(session_id, row["ordinal"]),
        "ordinal": row["ordinal"],
        "role": row["role"],
        "tool_name": row["tool_name"],
        "preview": preview(row["text"]),
    }


def _section_preview(session_id: str, row: sqlite3.Row) -> dict[str, Any]:
    source = (
        turn_address(session_id, row["source_ordinal"])
        if row["source_ordinal"] is not None
        else None
    )
    return {
        "address": section_address(session_id, row["slug"]),
        "kind": row["kind"],
        "title": row["title"],
        "source": source,
        "preview": preview(row["body"]),
    }


def _page(text: str, offset: int, limit: int) -> tuple[str, bool, int | None]:
    if offset > len(text):
        raise RecordError("bad_page", "offset is past the end of this part.")
    page = text[offset : offset + limit]
    continued = offset + limit < len(text)
    next_offset = offset + limit if continued else None
    return page, continued, next_offset


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()
