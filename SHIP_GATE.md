# Ship Gate

> No repo is "done" until every applicable line is checked.
> Copy this into your repo root. Check items off per-release.

**Tags:** `[all]` `[pypi]` `[mcp]` `[cli]` — private Python package, MCP server, and CLI. Version 0.1.0. Not tagged. Not published.

**This run (2026-10-02):** private repository. Landing page, handbook, translations, logo, and a homepage were skipped at the user's request. The error object stays `code` and `message`.

---

## A. Security Baseline

- [x] `[all]` SECURITY.md exists (report URL, supported versions, response timeline) — `shipcheck security-docs` passed (2026-10-02)
- [x] `[all]` README includes a trust model (data touched, data not kept, no network) — `shipcheck security-docs` passed (2026-10-02)
- [ ] `[all]` SKIP: `shipcheck secrets` skips this tree because there is no npm package to pack. The identity scan of the git-tracked tree was CLEAN on 2026-10-02.
- [x] `[all]` No telemetry by default — stated in the README trust model and in SECURITY.md (2026-10-02)

### Default safety posture

- [ ] `[cli|mcp|desktop]` SKIP: there is no kill, delete, or restart. Overwriting a filed session is the existing `--replace` flag. This run does not rename it.
- [ ] `[cli|mcp|desktop]` SKIP: the caller names the file to read and the database path to write. A directory jail would block a handoff from that path. Writes are the one configured SQLite file.
- [x] `[mcp]` Network egress off by default — the package opens no network connection of its own (2026-10-02)
- [ ] `[mcp]` SKIP: `RecordError` becomes a JSON object with `code` and `message`. An unexpected exception still prints a traceback. This run does not add a catch-all.

## B. Error Handling

- [ ] `[all]` SKIP: the error object is `code` and `message`. `hint`, `cause`, and `retryable` are not in the 0.1.0 shape. This run does not add them.
- [ ] `[cli]` SKIP: success is 0, record and file errors are 1, usage and unknown commands are 2. There is no exit 3. Renumbering would break the tested CLI.
- [ ] `[cli]` SKIP: known failures print JSON. There is no `--debug` flag. An unexpected exception still prints a traceback.
- [x] `[mcp]` Tool errors return structured results — every tool returns through `_call`, which turns `RecordError` into that JSON object (2026-10-02)
- [ ] `[mcp]` SKIP: a corrupt SQLite file raises from the database library. This run does not turn that into a stale-data response.
- [ ] `[desktop]` SKIP: not a desktop app
- [ ] `[vscode]` SKIP: not a VS Code extension

## C. Operator Docs

- [x] `[all]` README is current: what it does, install, usage, Python 3.11 or newer, CI on 3.11 and 3.12 (2026-10-02)
- [x] `[all]` CHANGELOG.md (Keep a Changelog format) (2026-10-02)
- [x] `[all]` LICENSE file present and the README states MIT and private 0.1.0 support (2026-10-02)
- [x] `[cli]` `--help` names each command and flag. The CLI tests lock that text (2026-10-02)
- [ ] `[cli|mcp|desktop]` SKIP: there is no silent/normal/verbose/debug ladder. Results are JSON on stdout. The tool stores the text the caller files and does not claim to redact it.
- [x] `[mcp]` All tools documented with description and parameters — README table plus each tool docstring (2026-10-02)
- [ ] `[complex]` SKIP: not a background daemon. The handbook was skipped on this run at the user's request.

## D. Shipping Hygiene

- [x] `[all]` `verify.py` runs the tests, builds a wheel, and checks `--help` and `--version` (2026-10-02)
- [ ] `[all]` SKIP: 0.1.0 is not tagged. `shipcheck manifest` skipped the version-tag check because there is no semver tag. This run does not cut a tag.
- [x] `[all]` Dependency scanning runs in CI — `pip-audit` on the installed environment. `shipcheck ci` passed that sub-check (2026-10-02)
- [x] `[all]` Dependabot vulnerability alerts are enabled. `shipcheck deps` passed. `pip-audit` of the installed environment found no known vulnerabilities after pip itself was upgraded (2026-10-02)
- [ ] `[all]` SKIP: the dependency auto-PR bot stays off. Vulnerability alerts are on. This run does not add `dependabot.yml`.
- [ ] `[npm]` SKIP: not published to npm. `shipcheck ci` skipped the provenance check. This run does not publish.
- [ ] `[npm]` SKIP: not an npm package. `shipcheck pack` does not apply.
- [x] `[pypi]` `requires-python = ">=3.11"`. `shipcheck manifest` engines sub-check passed. There is no npm package (2026-10-02)
- [ ] `[pypi]` SKIP: no `poetry.lock`, `Pipfile.lock`, `uv.lock`, or `pdm.lock`. `shipcheck manifest` failed that sub-check. This run does not add another package manager. `verify.py` builds the wheel.
- [ ] `[vsix]` SKIP: not a VS Code extension
- [ ] `[desktop]` SKIP: not a desktop app

## E. Identity (soft gate — does not block ship)

- [ ] `[all]` SKIP: this run does not add a logo or push one to the brand repo.
- [ ] `[all]` SKIP: translations skipped at the user's request.
- [ ] `[org]` SKIP: landing page skipped at the user's request.
- [ ] `[all]` SKIP: description and topics (`mcp`, `python`, `session`, `sqlite`) are set. Homepage stays empty because this run has no landing page.

---

## Gate Rules

**Hard gate (A–D):** Must pass before any version is tagged or published.
If a section doesn't apply, mark `SKIP:` with justification — don't leave it unchecked.

**Soft gate (E):** Should be done. Product ships without it, but isn't "whole."

**Checking off:** `- [x]` with the date. **Skipping:** `- [ ]` plus `SKIP:` and the reason.
