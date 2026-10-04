from __future__ import annotations

import ast
import struct
from pathlib import Path

# GNU gettext joins a message context to its msgid with this byte, and a plural
# entry's forms with this one, in the text form and in the compiled catalog
# alike. Both Python's gettext module and Django look entries up by those keys,
# so the values written here have to match what msgfmt would have written.
CONTEXT_SEPARATOR = "\x04"
PLURAL_SEPARATOR = "\x00"


def _unquote(line: str) -> str:
    _, _, value = line.partition(" ")
    return ast.literal_eval(value)


def _parse_po(path: Path) -> dict[str, str]:
    """Return a .po file's entries in the key/value form a .mo file holds.

    A contextual entry is keyed by ``msgctxt``, a separator and the msgid, and a
    plural entry's value is its forms joined by a NUL. The header entry is kept
    even though makemessages marks it fuzzy, because the charset comes from it.
    """
    messages: dict[str, str] = {}

    for raw_block in path.read_text(encoding="utf-8").split("\n\n"):
        block = [line for line in raw_block.splitlines() if line.strip()]
        if not block:
            continue

        is_fuzzy = "#, fuzzy" in block

        fields: dict[str, str] = {}
        plurals: dict[int, str] = {}
        current: str | None = None

        for line in block:
            if line.startswith("#"):
                continue

            keyword, _, _remainder = line.partition(" ")
            if keyword in {"msgctxt", "msgid", "msgid_plural", "msgstr"}:
                current = keyword
                fields[keyword] = _unquote(line)
                continue
            if keyword.startswith("msgstr["):
                current = "plural"
                plurals[int(keyword[7:-1])] = _unquote(line)
                continue
            if line.startswith('"') and current is not None:
                if current == "plural":
                    index = max(plurals, default=0)
                    plurals[index] += ast.literal_eval(line)
                else:
                    fields[current] += ast.literal_eval(line)

        msgid = fields.get("msgid")
        if msgid is None or (is_fuzzy and msgid):
            # A fuzzy entry is not offered as a translation, but the header is:
            # it carries the charset, and makemessages marks it fuzzy too.
            continue

        context = fields.get("msgctxt", "")
        key = f"{context}{CONTEXT_SEPARATOR}{msgid}" if context else msgid
        if plurals:
            # msgfmt keys a plural entry as the singular, a NUL and the plural,
            # which is how a reader knows the value holds several forms.
            plural_id = fields.get("msgid_plural", "")
            messages[f"{key}{PLURAL_SEPARATOR}{plural_id}"] = PLURAL_SEPARATOR.join(
                plurals[index] for index in sorted(plurals)
            )
        else:
            messages[key] = fields.get("msgstr", "")

    return messages


def compile_po_to_mo(po_path: Path, mo_path: Path) -> None:
    messages = _parse_po(po_path)
    keys = sorted(messages)

    ids = [key.encode("utf-8") for key in keys]
    strs = [messages[key].encode("utf-8") for key in keys]

    keystart = 7 * 4
    valuestart = keystart + len(keys) * 8
    id_offset = valuestart + len(keys) * 8
    str_offset = id_offset + sum(len(msgid) + 1 for msgid in ids)

    output = [
        struct.pack("<Iiiiiii", 0x950412DE, 0, len(keys), keystart, valuestart, 0, 0),
    ]

    offset = id_offset
    for msgid in ids:
        output.append(struct.pack("<ii", len(msgid), offset))
        offset += len(msgid) + 1

    offset = str_offset
    for msgstr in strs:
        output.append(struct.pack("<ii", len(msgstr), offset))
        offset += len(msgstr) + 1

    output.extend(msgid + b"\0" for msgid in ids)
    output.extend(msgstr + b"\0" for msgstr in strs)

    mo_path.write_bytes(b"".join(output))


def ensure_compiled_translations(locale_root: Path | str = "locale") -> None:
    locale_root = Path(locale_root)
    for po_path in locale_root.glob("*/LC_MESSAGES/*.po"):
        mo_path = po_path.with_suffix(".mo")
        if not mo_path.exists() or mo_path.stat().st_mtime < po_path.stat().st_mtime:
            compile_po_to_mo(po_path, mo_path)
