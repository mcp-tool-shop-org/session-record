# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project uses semantic versioning. Version 0.1.0 is the private tree. It is not a 1.0 release and it is not tagged.

## [Unreleased]

Current version: 0.1.0.

### Added

- File a session as turns and named sections, and refer to one address at a time.
- File a Grok `chat_history.jsonl`. System lines and reasoning lines are skipped.
- List filed sessions and find an exact string of at least 3 characters. Both page with `offset`.
- Page a map outline with `outline_offset`.
- Name one section from the shell with `session-record section`.
- A ship gate, this changelog, and `verify.py` (tests, a wheel, and a CLI smoke check).

### Fixed

- CI upgrades setuptools before `pip-audit`. The Python 3.11 image ships setuptools 79.0.1, which the audit flags.
