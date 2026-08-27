"""Report collisions and unintentional overrides across association static
and template trees.

Logical paths are shared between variants (e.g. date/css/homepage.css
exists in every variant with different content), which is intentional for
templates. This command flags the risky cases:

- the same logical static path with *different content* between the
  variant dirs and the shared common dir (silent override);
- the same logical template path defined in more than one variant dir
  (a variant override that also affects inheriting variants).

Usage:
    python manage.py static_overrides_report
"""

import hashlib
import os
from collections import defaultdict

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Report static/template logical-path collisions between association trees."

    def add_arguments(self, parser):
        parser.add_argument("--tree", choices=("static", "templates"), default="static")
        parser.add_argument("--fail", action="store_true", help="exit non-zero when collisions are found")

    def handle(self, *args, **options):
        tree = options["tree"]
        base = os.path.join(settings.BASE_DIR, tree)

        variants = sorted(
            name
            for name in os.listdir(base)
            if os.path.isdir(os.path.join(base, name)) and name != "common"
        )
        roots = {"common": os.path.join(base, "common"), **{v: os.path.join(base, v) for v in variants}}

        by_path = defaultdict(list)
        for root_name, root in roots.items():
            for dirpath, _, filenames in os.walk(root):
                for filename in filenames:
                    full = os.path.join(dirpath, filename)
                    rel = os.path.relpath(full, root)
                    by_path[rel].append(root_name)

        issues = 0
        for rel in sorted(by_path):
            owners = by_path[rel]
            if len(owners) == 1 and owners[0] != "common":
                continue
            if len(owners) == 1:
                continue
            content = {}
            for owner in owners:
                with open(os.path.join(roots[owner], rel), "rb") as fh:
                    content[owner] = hashlib.sha256(fh.read()).hexdigest()
            unique = set(content.values())
            if len(unique) == 1:
                continue
            if tree == "static" and "common" in owners:
                self.stdout.write(
                    self.style.WARNING(
                        f"static override (differs from common): {rel} in {sorted(owners)}"
                    )
                )
            elif tree == "static":
                self.stdout.write(
                    self.style.WARNING(f"static path differs between variants: {rel} in {sorted(owners)}")
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f"template defined in multiple variants: {rel} in {sorted(owners)}")
                )
            issues += 1

        if issues == 0:
            self.stdout.write(self.style.SUCCESS("No collisions found."))
        else:
            self.stdout.write(self.style.ERROR(f"{issues} collision(s) found."))
            if options["fail"]:
                raise SystemExit(1)
