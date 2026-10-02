"""Run the tests, build a wheel, and smoke the CLI.

One command for the ship gate. The wheel build uses pip's build isolation,
which may download the build backend on a cold machine.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _run(args: list[str]) -> None:
    print("+", " ".join(args), flush=True)
    result = subprocess.run(args, cwd=ROOT, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> int:
    py = sys.executable
    _run([py, "-m", "pytest"])
    with tempfile.TemporaryDirectory() as tmp:
        _run([py, "-m", "pip", "wheel", "--no-deps", "-w", tmp, str(ROOT)])
        wheels = list(Path(tmp).glob("session_record-*.whl"))
        if len(wheels) != 1:
            print(f"expected one session_record wheel, found {len(wheels)}", file=sys.stderr)
            raise SystemExit(1)
        print(f"wheel {wheels[0].name}", flush=True)
    _run([py, "-m", "session_record", "--version"])
    _run([py, "-m", "session_record", "--help"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
