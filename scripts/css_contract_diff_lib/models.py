from dataclasses import dataclass


class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"
    DIM = "\033[2m"


def style(text: str, *codes: str, use_color: bool = True) -> str:
    if not use_color or not codes:
        return text
    return "".join(codes) + text + Colors.RESET


@dataclass(frozen=True)
class ComponentContract:
    template_path: str
    css_paths: tuple[str, ...]
    css_fingerprints: tuple[str, ...]
    template_fingerprint: str
    flattened_normalized: str | None
    flattened_pretty: str | None
    combined_fingerprint: str


@dataclass(frozen=True)
class CssRenameAudit:
    old_template_ref: str
    new_template_ref: str
    rename_path_pairs: tuple[tuple[str, str], ...]
    unresolved_templates: tuple[str, ...]
    migrated_templates: tuple[str, ...]
    dropped_templates: tuple[str, ...]


@dataclass
class RenameAuditBucket:
    unresolved: set[str]
    migrated: set[str]
    dropped: set[str]
    rename_pairs: set[tuple[str, str]]
