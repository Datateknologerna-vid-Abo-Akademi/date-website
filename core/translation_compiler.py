from __future__ import annotations

import ast
import struct
from pathlib import Path


def _unquote(line: str) -> str:
    _, _, value = line.partition(" ")
    return ast.literal_eval(value)


def _parse_po(path: Path) -> dict[str, str]:
    messages: dict[str, str] = {}
    text = path.read_text(encoding="utf-8")

    for raw_block in text.split("\n\n"):
        block = [line for line in raw_block.splitlines() if line.strip()]
        if not block:
            continue

        is_fuzzy = "#, fuzzy" in block

        msgid = ""
        msgstr = ""
        in_msgid = False
        in_msgstr = False
        saw_msgid = False

        for line in block:
            if line.startswith("msgid "):
                saw_msgid = True
                in_msgid = True
                in_msgstr = False
                msgid = _unquote(line)
                continue
            if line.startswith("msgstr "):
                in_msgid = False
                in_msgstr = True
                msgstr = _unquote(line)
                continue
            if line.startswith('"'):
                if in_msgid:
                    msgid += ast.literal_eval(line)
                elif in_msgstr:
                    msgstr += ast.literal_eval(line)

        if not saw_msgid:
            continue

        if is_fuzzy and msgid != "":
            continue

        messages[msgid] = msgstr

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
