# Scorecard

**Repo:** mcp-tool-shop-org/session-record
**Date:** 2026-10-02
**Type tags:** [all] [pypi] [mcp] [cli]
**Version:** 0.1.0, private, not tagged

## Audit

`npx @mcptoolshop/shipcheck audit` on 2026-10-02:

| Result | Count |
| --- | --- |
| Checked | 14 |
| Skipped | 23 |
| Unchecked | 0 |
| Exit | 0 |

Skipped lines are the ones that do not fit this private 0.1.0 tree, or that this run was asked to leave alone. They are not checked.

## What this run skipped on purpose

- Logo, translations, landing page, handbook, and a homepage.
- Promoting 0.1.0 to 1.0.0, and cutting a tag.
- Adding `hint` to the error object, and renumbering CLI exit codes.
- A poetry, uv, or pdm lockfile.
- A dependency auto-PR bot. Vulnerability alerts are on, and CI runs `pip-audit`.

## Executed gates

| Gate | Result |
| --- | --- |
| security-docs | passed |
| secrets | skipped (no npm package to pack) |
| manifest engines | passed (`requires-python`) |
| manifest lockfile | failed (no poetry/uv/pdm lock) |
| manifest version-tag | skipped (no semver tag) |
| ci dependency-scan | passed (`pip-audit`) |
| ci provenance | skipped (no npm publish) |
| deps | passed (no npm tree; Dependabot alerts enabled). The first CI run on Python 3.11 flagged the image's setuptools 79.0.1; CI upgrades setuptools before `pip-audit`. |
| identity scan of the git-tracked tree | CLEAN |

## Map

`atlas/` holds the generated map from Atlas 1.26.0. The Python 3.11 CI job runs `atlas check`. This private repository is not given a public fleet page.
