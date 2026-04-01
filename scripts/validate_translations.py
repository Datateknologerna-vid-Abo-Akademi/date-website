from __future__ import annotations

from pathlib import Path
import sys


REQUIRED_LOCALES = ("sv", "en", "fi")


def _unquote(line: str) -> str:
    return line[1:-1] if line.startswith('"') and line.endswith('"') else ""


def parse_po(path: Path) -> tuple[int, int]:
    text = path.read_text(encoding="utf-8")
    fuzzy = 0
    untranslated = 0

    for raw_block in text.split("\n\n"):
        block = [line for line in raw_block.splitlines() if line.strip()]
        if not block:
            continue

        is_fuzzy = "#, fuzzy" in block
        msgid = ""
        msgstr = ""
        in_msgid = False
        in_msgstr = False

        for line in block:
            if line.startswith("msgid "):
                in_msgid = True
                in_msgstr = False
                msgid = line[7:-1]
                continue
            if line.startswith("msgstr "):
                in_msgid = False
                in_msgstr = True
                msgstr = line[8:-1]
                continue
            if line.startswith('"'):
                if in_msgid:
                    msgid += _unquote(line)
                elif in_msgstr:
                    msgstr += _unquote(line)

        if msgid == "":
            continue

        if is_fuzzy:
            fuzzy += 1
        if msgstr == "":
            untranslated += 1

    return fuzzy, untranslated


def main() -> int:
    failures: list[str] = []

    for locale in REQUIRED_LOCALES:
        po_path = Path("locale") / locale / "LC_MESSAGES" / "django.po"
        if not po_path.exists():
            failures.append(f"missing locale catalog: {po_path}")
            continue

        fuzzy, untranslated = parse_po(po_path)
        if fuzzy:
            failures.append(f"{po_path}: {fuzzy} fuzzy entries")
        if untranslated:
            failures.append(f"{po_path}: {untranslated} untranslated entries")

    if failures:
        print("Translation validation failed:", file=sys.stderr)
        for failure in failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    print("Translation validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
