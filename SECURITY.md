# Security Policy

## Supported versions

| Version | Supported |
| --- | --- |
| 0.1.0 | yes |

Python 3.11 and 3.12 are the versions CI runs. The package requires Python 3.11 or newer.

## Reporting a vulnerability

This repository is private. Report a vulnerability by opening a draft security advisory:

https://github.com/mcp-tool-shop-org/session-record/security/advisories/new

Include what you can do, the version, and how to reproduce it.

| Action | Target |
| --- | --- |
| First look | 7 days |
| Fix on the private default branch, when one is needed | 30 days |

There is no package registry release, so a fix is a commit on this repository.

## Scope

The tool stays on this machine. It reads the files you name and writes one SQLite database. It does not open a network connection of its own. It does not collect telemetry.
