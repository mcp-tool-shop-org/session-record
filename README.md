# session-record

Store a session as a record a later turn can refer to.

When a context window fills, what usually remains is a summary. session-record keeps the session itself: the turns, verbatim, plus named sections for the decisions, files, and open items. The map is a table of contents. Referring to an address returns that one part.

This repo is the graduation of the `context-window-manager` prototype. The prototype froze vLLM KV-cache tensors. This product stores the session as text you can address. Version 0.1.0.

## Addresses

| Address | What you get |
| --- | --- |
| `alpha` | The map for that session |
| `alpha/turns/4` | Turn 4, verbatim |
| `alpha/sections/licence` | The named section |

A section has a kind (`decision`, `file`, `open`, `note`) and may point at the turn it came from.

## Tools

| Tool | What it does |
| --- | --- |
| `record_file` | File the turns, and any sections you already want to name. Returns the map. |
| `record_handoff` | File a Grok `chat_history.jsonl` from a path. Returns the map and the first page of turn previews. |
| `record_section` | Name one part of a session that is already filed. |
| `record_map` | Table of contents. Set `outline_limit` (max 20) to page through one-line turn previews. |
| `record_refer` | One address. Long text comes back in pages; pass `next_offset` to continue. |
| `record_find` | Addresses and one-line previews for an exact string. Open one with `record_refer`. |
| `record_list` | Sessions already filed, newest first. Filter with `project`. |

`record_list` returns sessions when you know the project or the title. `record_find` returns addresses when you know a string from the session: a path, an error code, a tool name, a section slug. `record_refer` opens the address.

## Handoff

At the end of a Grok session, file `chat_history.jsonl` from its path. User text, assistant text, each tool call, and each tool result become turns, numbered from 0. System lines and reasoning lines are skipped.

```bash
session-record handoff grok alpha "Licence pass" chat_history.jsonl --project widgets --sections sections.json
session-record find "ZX-404" --project widgets
session-record refer alpha/turns/3
```

`sections.json` is an array of sections. `source_ordinal` is the turn number the handoff assigns. The command prints the map and the first page of turn previews.

Filing writes one callback row per turn and per section. The row stores a situating prefix plus the verbatim text, and leaves `embedding_id` empty so a later pass can attach a vector to that same address. `record_find` searches the row and returns addresses and one-line previews. A query needs at least 3 characters.

## File a session from disk

A session file is JSON with a `turns` array and an optional `sections` array.

```bash
session-record file alpha "Licence pass" session.json --project widgets
session-record refer alpha/turns/1
session-record list --project widgets
```

With no command, `session-record` runs the MCP server.

## Run

The database file is `SESSION_RECORD_DB`. If that is unset, the server uses `.session-record/record.sqlite` under the home directory. The file stays on this machine.

```json
{
  "mcpServers": {
    "session-record": {
      "command": "session-record",
      "env": {
        "SESSION_RECORD_DB": "record.sqlite"
      }
    }
  }
}
```

## Develop

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

`pytest` fails when coverage of `session_record` drops below 90%. CI uploads the same report to Codecov, and the project and patch checks use that same 90% bar.
