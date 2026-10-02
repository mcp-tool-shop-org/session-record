# session-record: how it works

Mapped at 2026-10-02 from commit 59a3591 by Atlas 1.26.0.

## What this is

A private Python package that stores a session as addresses a later turn can open. (written by a person)

4 parts, mostly Python (11 files). Work enters through 2 doors; the busiest is CI, which reaches 2 parts. People run session-record.

## What changed since 2026-10-02 (ca71a3b)

Nothing structural changed since 2026-10-02; 3 files changed content.

## What comes in

1. **CI.** On a pull request to main; on a push to main; or by hand. Runs tests/.
2. **session-record** (a command people run). Runs src/session_record/__main__.py.

## What happens through CI

1. The workflow runs tests/ in tests.
2. That reaches src (5 files).
3. It uploads coverage to Codecov.

## Who reads the results

CI writes nothing this map can see.

## The other doors

**session-record** (a command people run) runs src/session_record/__main__.py.

## What breaks what

- **src** is run as a child process by 1 part (the repository root) and sits on the path of 2 doors.
- **tests** is run as a child process by 1 part (the repository root) and sits on the path of 1 door.

## What tends to change together

No two source files changed together often enough to name.

Window: 180 days; a pair counts from 3 shared commits, since the window holds fewer than 30 qualifying commits.

## What no test touches

Every code part is imported by at least one test.

verify.py runs in no workflow.

## Written but never read

No place this map can see is written, so none goes unread.

## Helpers that look duplicated

No two parts export a helper that looks alike.

## Generated, never hand-edited

Nothing in this repository writes to a tracked place this map can see.

## Hand-authored

People write .github/ and the repository root; 1 write with a path built at run time may land here.

## Where to start

src/session_record/__main__.py → src/session_record/server.py → src/session_record/grok.py → src/session_record/store.py

Read those in order to follow one run of session-record end to end. This path follows session-record (a command people run) from its entry, since CI runs only tests.

## What this map cannot see

- 1 write and 1 read use paths built at run time and are not named here.
- 3 reads go to a path their caller passes, not to this repository.
- Statistics confidence is low: fewer than 30 qualifying commits in the window, and fewer than 25 source files reach 10 revisions.

Regenerate with `npx --yes @dogfood-lab/atlas map`.
