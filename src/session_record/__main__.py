"""Run the session-record MCP server.

Usage:
    python -m session_record
    session-record
"""

from __future__ import annotations

import sys


def main() -> int:
    args = sys.argv[1:]
    if "--version" in args or "-V" in args:
        from session_record import __version__

        print(f"session-record {_version(__version__)}")
        return 0
    if "--help" in args or "-h" in args:
        print(
            """session-record — store a session as a record you can refer to

Usage:
  session-record           Run the MCP server on stdio
  session-record --version Show version
  session-record --help    Show this help

Set SESSION_RECORD_DB to the sqlite file. Otherwise the server uses
.session-record/record.sqlite under the home directory.
"""
        )
        return 0

    from session_record.server import mcp

    mcp.run(transport="stdio")
    return 0


def _version(value: str) -> str:
    return value


if __name__ == "__main__":
    sys.exit(main())
