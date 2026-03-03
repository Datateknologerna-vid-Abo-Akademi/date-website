#!/usr/bin/env python3
"""Host-routed multi-association smoke checks.

Validates that one shared frontend + host-routed backend setup returns the
expected association metadata per hostname.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


DEFAULT_APP_ORIGIN = "http://localhost:8080"
DEFAULT_HOST_MAP = {
    "date.lvh.me": "date",
    "kk.lvh.me": "kk",
    "biocum.lvh.me": "biocum",
    "on.lvh.me": "on",
    "demo.lvh.me": "demo",
}


@dataclass
class HostCheckResult:
    host: str
    expected_project: str
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def http_get(url: str, host: str, timeout_seconds: int = 10) -> tuple[int, dict[str, str], str, str | None]:
    request = Request(url, headers={"Host": host, "User-Agent": "multi-host-qa/1.0"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8", errors="replace")
            return response.getcode(), dict(response.headers.items()), body, None
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, dict(exc.headers.items()) if exc.headers else {}, body, None
    except Exception as exc:  # noqa: BLE001
        return 0, {}, "", str(exc)


def running_in_wsl() -> bool:
    release = platform.release().lower()
    return "microsoft" in release or "wsl" in release


def read_wsl_gateway_ip() -> str | None:
    resolv_conf = Path("/etc/resolv.conf")
    if not resolv_conf.exists():
        return None
    try:
        for line in resolv_conf.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line.startswith("nameserver "):
                continue
            ip = line.split(" ", 1)[1].strip()
            if ip:
                return ip
    except Exception:  # noqa: BLE001
        return None
    return None


def build_origin_candidates(primary_origin: str) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    def add(origin: str | None) -> None:
        if not origin:
            return
        normalized = origin.rstrip("/")
        if normalized in seen:
            return
        seen.add(normalized)
        candidates.append(normalized)

    add(primary_origin)

    parsed_primary = primary_origin.replace("https://", "").replace("http://", "")
    has_localhost = parsed_primary.startswith("localhost:") or parsed_primary.startswith("127.0.0.1:")
    if has_localhost:
        add("http://host.docker.internal:8080")
        if running_in_wsl():
            gateway_ip = read_wsl_gateway_ip()
            if gateway_ip:
                add(f"http://{gateway_ip}:8080")

    return candidates


def resolve_working_origin(primary_origin: str, host: str) -> tuple[str, list[str]]:
    candidates = build_origin_candidates(primary_origin)
    attempted: list[str] = []
    for candidate in candidates:
        attempted.append(candidate)
        status, _, body, error = http_get(
            urljoin(f"{candidate}/", "api/v1/meta/site"),
            host=host,
            timeout_seconds=4,
        )
        if error is not None or status != 200:
            continue
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
            return candidate, attempted
    return primary_origin.rstrip("/"), attempted


def validate_host(base_origin: str, host: str, expected_project: str) -> HostCheckResult:
    result = HostCheckResult(host=host, expected_project=expected_project)

    meta_url = urljoin(f"{base_origin.rstrip('/')}/", "api/v1/meta/site")
    status, _headers, body, transport_error = http_get(meta_url, host=host)
    if transport_error:
        result.failures.append(f"meta/site transport error: {transport_error}")
        return result
    if status != 200:
        snippet = " ".join(body.strip().split())
        if len(snippet) > 220:
            snippet = f"{snippet[:220]}..."
        extra = f" body='{snippet}'" if snippet else ""
        result.failures.append(f"meta/site expected 200, got {status}.{extra}")
        return result

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        result.failures.append(f"meta/site invalid JSON: {exc}")
        return result

    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        result.failures.append("meta/site missing data envelope")
        return result

    project_name = data.get("project_name")
    if project_name != expected_project:
        result.failures.append(
            f"project_name mismatch: expected '{expected_project}', got '{project_name}'"
        )

    default_landing_path = data.get("default_landing_path", "/")
    if not isinstance(default_landing_path, str) or not default_landing_path.startswith("/"):
        result.failures.append(f"default_landing_path invalid: {default_landing_path!r}")
        default_landing_path = "/"

    root_url = urljoin(f"{base_origin.rstrip('/')}/", "")
    root_status, _, _, root_transport_error = http_get(root_url, host=host)
    if root_transport_error:
        result.failures.append(f"root route transport error: {root_transport_error}")
    elif root_status >= 500:
        result.failures.append(f"root route failed with {root_status}")

    landing_url = urljoin(f"{base_origin.rstrip('/')}/", default_landing_path.lstrip("/"))
    landing_status, _, _, landing_transport_error = http_get(landing_url, host=host)
    if landing_transport_error:
        result.failures.append(f"landing route transport error: {landing_transport_error}")
    elif landing_status >= 500:
        result.failures.append(
            f"landing route {default_landing_path} failed with {landing_status}"
        )

    module_capabilities = data.get("module_capabilities")
    if not isinstance(module_capabilities, dict):
        result.failures.append("module_capabilities missing or invalid")
        return result

    lucia = module_capabilities.get("lucia", {})
    lucia_enabled = bool(lucia.get("enabled")) if isinstance(lucia, dict) else False
    lucia_status, _, _, lucia_transport_error = http_get(
        urljoin(f"{base_origin.rstrip('/')}/", "lucia"),
        host=host,
    )
    if lucia_transport_error:
        result.failures.append(f"/lucia transport error: {lucia_transport_error}")
    elif lucia_enabled and lucia_status >= 500:
        result.failures.append(f"/lucia expected non-500 when enabled, got {lucia_status}")
    elif not lucia_enabled and lucia_status != 404:
        result.warnings.append(f"/lucia expected 404 when disabled, got {lucia_status}")

    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run multi-host association QA checks.")
    parser.add_argument(
        "--app-origin",
        default=DEFAULT_APP_ORIGIN,
        help="Base origin where proxy is exposed (default: http://localhost:8080).",
    )
    parser.add_argument(
        "--host-map-json",
        default=json.dumps(DEFAULT_HOST_MAP),
        help='JSON map of hostname -> expected project_name (default includes *.lvh.me hosts).',
    )
    parser.add_argument(
        "--report-path",
        default="docs/multi-host-qa-report.md",
        help="Output markdown report path.",
    )
    return parser.parse_args()


def write_report(report_path: Path, app_origin: str, results: list[HostCheckResult]) -> None:
    lines: list[str] = []
    lines.append("# Multi-Host QA Report")
    lines.append("")
    lines.append(f"- App origin: `{app_origin}`")
    lines.append("")
    lines.append("| Host | Expected project | Failures | Warnings |")
    lines.append("| --- | --- | ---: | ---: |")
    for result in results:
        lines.append(
            f"| `{result.host}` | `{result.expected_project}` | {len(result.failures)} | {len(result.warnings)} |"
        )
    lines.append("")

    for result in results:
        lines.append(f"## {result.host}")
        lines.append("")
        lines.append(f"- Expected project: `{result.expected_project}`")
        if result.failures:
            lines.append("- Failures:")
            for failure in result.failures:
                lines.append(f"  - {failure}")
        if result.warnings:
            lines.append("- Warnings:")
            for warning in result.warnings:
                lines.append(f"  - {warning}")
        if not result.failures and not result.warnings:
            lines.append("- No issues detected.")
        lines.append("")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    try:
        host_map = json.loads(args.host_map_json)
    except json.JSONDecodeError as exc:
        print(f"Invalid --host-map-json: {exc}", file=sys.stderr)
        return 2
    if not isinstance(host_map, dict):
        print("--host-map-json must decode to an object", file=sys.stderr)
        return 2

    host_keys = [key for key in host_map.keys() if isinstance(key, str)]
    probe_host = host_keys[0] if host_keys else "date.lvh.me"
    resolved_origin, attempted_origins = resolve_working_origin(args.app_origin, probe_host)

    print(f"Using app origin: {resolved_origin}")
    if resolved_origin.rstrip("/") != args.app_origin.rstrip("/"):
        print(f"Fallback origin selected (attempted: {', '.join(attempted_origins)})")

    results: list[HostCheckResult] = []
    for host, expected_project in host_map.items():
        if not isinstance(host, str) or not isinstance(expected_project, str):
            print(f"Skipping invalid mapping entry: {host!r}: {expected_project!r}", file=sys.stderr)
            continue
        result = validate_host(resolved_origin, host=host, expected_project=expected_project)
        print(
            f"{host}: failures={len(result.failures)} warnings={len(result.warnings)} expected={expected_project}"
        )
        if result.failures:
            for failure in result.failures:
                print(f"  failure: {failure}")
        results.append(result)

    write_report(Path(args.report_path), resolved_origin, results)
    total_failures = sum(len(result.failures) for result in results)
    return 1 if total_failures else 0


if __name__ == "__main__":
    sys.exit(main())
