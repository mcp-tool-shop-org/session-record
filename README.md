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
| `record_section` | Name one part of a session that is already filed. |
| `record_map` | Table of contents. Set `outline_limit` (max 20) to page through one-line turn previews. |
| `record_refer` | One address. Long text comes back in pages; pass `next_offset` to continue. |
| `record_list` | Sessions already filed, newest first. Filter with `project`. |

`record_list` is how you get back to an older session when you still know the project or the title. Finding a session by meaning, when you no longer have an address, is not in this version.

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
