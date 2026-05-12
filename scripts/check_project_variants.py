from __future__ import annotations

import os
import subprocess
import sys


DEFAULT_PROJECTS = ("date", "kk", "biocum", "pulterit")


def main() -> int:
    projects = tuple(sys.argv[1:]) or DEFAULT_PROJECTS
    failed_projects: list[str] = []

    for project in projects:
        env = {
            **os.environ,
            "PROJECT_NAME": project,
            "DJANGO_SETTINGS_MODULE": f"core.settings.{project}",
        }
        print(f"Checking {project}...", flush=True)
        result = subprocess.run(
            [sys.executable, "manage.py", "check"],
            env=env,
            check=False,
        )
        if result.returncode != 0:
            failed_projects.append(project)

    if failed_projects:
        print(
            "Variant checks failed for: " + ", ".join(failed_projects),
            file=sys.stderr,
        )
        return 1

    print("All variant checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
