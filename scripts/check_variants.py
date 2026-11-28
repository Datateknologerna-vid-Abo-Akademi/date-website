"""Run the per-association Django checks concurrently.

`manage.py check` and `manage.py makemigrations --check` pick their settings
module from `PROJECT_NAME` at import time, so every association needs its own
process. The checks share no state, so running them in parallel makes the
slowest one the bound instead of the sum of all of them: sequentially they
were about 90s of the CI job, and four at a time brings that to roughly 30s.

Usage: python scripts/check_variants.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

MANAGE = Path(__file__).resolve().parent.parent / "manage.py"

# Every association variant gets a full settings/app check.
CHECK_VARIANTS = ("date", "kk", "biocum", "pulterit", "sf", "impuls")
# Distinct app sets only: date is the broadest, kk adds lucia, sf adds
# klotterplanket. The other variants install a subset of these.
MIGRATION_VARIANTS = ("date", "kk", "sf")

MAX_WORKERS = max(1, min(4, os.cpu_count() or 1))


@dataclass(frozen=True)
class Check:
    label: str
    variant: str
    arguments: tuple[str, ...]


CHECKS = (
    *(Check(f"check {variant}", variant, ("check",)) for variant in CHECK_VARIANTS),
    *(
        Check(f"makemigrations --check {variant}", variant, ("makemigrations", "--check", "--dry-run"))
        for variant in MIGRATION_VARIANTS
    ),
)


def run(check: Check) -> tuple[Check, subprocess.CompletedProcess[str]]:
    result = subprocess.run(
        (sys.executable, str(MANAGE), *check.arguments),
        capture_output=True,
        text=True,
        env={**os.environ, "PROJECT_NAME": check.variant},
    )
    return check, result


def main() -> int:
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        results = list(pool.map(run, CHECKS))

    failures = []
    for check, result in results:
        print(f"{check.label}: {'ok' if result.returncode == 0 else 'FAILED'}", flush=True)
        if result.returncode != 0:
            failures.append((check, result))

    for check, result in failures:
        print(f"\n== {check.label} (PROJECT_NAME={check.variant})")
        print(result.stdout, end="")
        print(result.stderr, end="")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
