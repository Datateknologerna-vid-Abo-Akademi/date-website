#!/usr/bin/env python3
"""Association-aware decoupled frontend/backend QA checks.

Runs Docker Compose with each association profile, validates `/api/v1/meta/site`,
checks landing route behavior, and verifies module route guarding behavior.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, build_opener
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


DEFAULT_ASSOCIATIONS = ["date", "kk", "biocum", "on", "demo"]
DEFAULT_COMPOSE_FILE = "docker-compose.yml"
DEFAULT_APP_ORIGIN = "http://localhost:8080"
DEFAULT_RECREATE_SERVICES = ["backend", "asgi", "celery", "frontend", "proxy"]
MODULE_ROUTE_EXCLUSIONS = {"billing", "staticpages"}


@dataclass
class AssociationResult:
    association: str
    default_landing_path: str = ""
    enabled_modules: list[str] = field(default_factory=list)
    module_route_statuses: list[tuple[str, str, bool, int]] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def run_cmd(command: list[str], env: dict[str, str] | None = None) -> None:
    print(f"$ {' '.join(command)}")
    subprocess.run(command, check=True, env=env)


def parse_env_file(env_file: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not env_file.exists():
        return values
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        values[key] = value
    return values


def resolve_env_file(explicit_env_file: str | None) -> Path | None:
    if explicit_env_file:
        candidate = Path(explicit_env_file)
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Requested env file not found: {candidate}")
    for candidate in (Path(".env"), Path(".env.example")):
        if candidate.exists():
            return candidate
    return None


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http_get(
    url: str,
    timeout_seconds: int,
    follow_redirects: bool = True,
) -> tuple[int, dict[str, str], str, str | None]:
    request = Request(url, headers={"User-Agent": "association-qa/1.0"})
    try:
        opener = build_opener() if follow_redirects else build_opener(_NoRedirectHandler())
        with opener.open(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8", errors="replace")
            return response.getcode(), dict(response.headers.items()), body, None
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, dict(exc.headers.items()) if exc.headers else {}, body, None
    except Exception as exc:  # noqa: BLE001
        return 0, {}, "", str(exc)


def wait_for_meta_site(base_url: str, timeout_seconds: int) -> tuple[dict[str, Any], str | None]:
    deadline = time.time() + timeout_seconds
    meta_url = urljoin(f"{base_url.rstrip('/')}/", "api/v1/meta/site")
    last_error = "unknown error"
    while time.time() < deadline:
        status, _headers, body, transport_error = http_get(meta_url, timeout_seconds=5)
        if transport_error:
            last_error = transport_error
            time.sleep(2)
            continue
        if status != 200:
            last_error = f"status={status}"
            time.sleep(2)
            continue
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            last_error = f"invalid json: {exc}"
            time.sleep(2)
            continue
        if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
            return payload["data"], None
        last_error = "missing data envelope"
        time.sleep(2)
    return {}, last_error


def get_header(headers: dict[str, str], header_name: str) -> str:
    for key, value in headers.items():
        if key.lower() == header_name.lower():
            return value
    return ""


def resolve_route(capability: dict[str, Any]) -> str:
    nav_route = capability.get("nav_route")
    if isinstance(nav_route, str) and nav_route.startswith("/") and "{" not in nav_route:
        return nav_route
    routes = capability.get("routes")
    if isinstance(routes, list):
        for route in routes:
            if isinstance(route, str) and route.startswith("/") and "{" not in route:
                return route
    return ""


def validate_root_route(base_url: str, default_landing_path: str, result: AssociationResult) -> None:
    root_url = urljoin(f"{base_url.rstrip('/')}/", "")
    status, headers, _body, transport_error = http_get(root_url, timeout_seconds=10, follow_redirects=False)
    if transport_error:
        result.failures.append(f"GET / failed: {transport_error}")
        return

    if default_landing_path != "/":
        if status in (301, 302, 307, 308):
            location = get_header(headers, "Location")
            location_path = urlparse(location).path if location else ""
            if location_path != default_landing_path:
                result.failures.append(
                    f"Expected redirect to {default_landing_path}, got Location={location or '<empty>'}."
                )
            return

        if status == 200:
            landing_url = urljoin(f"{base_url.rstrip('/')}/", default_landing_path.lstrip("/"))
            landing_status, _landing_headers, _landing_body, landing_transport_error = http_get(
                landing_url,
                timeout_seconds=10,
            )
            if landing_transport_error:
                result.failures.append(
                    f"GET {default_landing_path} failed while validating landing behavior: {landing_transport_error}."
                )
                return
            if landing_status >= 500:
                result.failures.append(
                    f"Expected landing path {default_landing_path} to be available, got {landing_status}."
                )
                return
            result.warnings.append(
                f"/ returned 200 instead of redirecting to {default_landing_path}; treating as inline landing render."
            )
            return

        result.failures.append(
            f"Expected / to redirect to {default_landing_path} (or return 200), got status {status}."
        )
    elif status in (301, 302, 307, 308):
        location = get_header(headers, "Location")
        location_path = urlparse(location).path if location else ""
        if location_path != "/":
            result.warnings.append(
                f"Landing path is '/', but / redirects to {location or '<empty>'}."
            )


def validate_modules(base_url: str, module_capabilities: dict[str, Any], result: AssociationResult) -> None:
    for module_key in sorted(module_capabilities.keys()):
        capability = module_capabilities.get(module_key)
        if not isinstance(capability, dict):
            result.failures.append(f"module_capabilities.{module_key} is not an object.")
            continue
        enabled = bool(capability.get("enabled"))
        if module_key in MODULE_ROUTE_EXCLUSIONS:
            continue
        route = resolve_route(capability)
        if not route:
            continue
        url = urljoin(f"{base_url.rstrip('/')}/", route.lstrip("/"))
        status, _headers, _body, transport_error = http_get(url, timeout_seconds=10)
        if transport_error:
            result.failures.append(f"{module_key} ({route}) transport failure: {transport_error}")
            continue
        result.module_route_statuses.append((module_key, route, enabled, status))
        if not enabled and status != 404:
            result.failures.append(
                f"Disabled module '{module_key}' route {route} should return 404, got {status}."
            )
        if enabled and status >= 500:
            result.failures.append(
                f"Enabled module '{module_key}' route {route} returned {status}."
            )
        elif enabled and status == 404:
            result.warnings.append(
                f"Enabled module '{module_key}' route {route} returned 404 (check data/content parity)."
            )


def run_association_checks(
    association: str,
    compose_cmd_prefix: list[str],
    app_origin: str,
    timeout_seconds: int,
    recreate_services: list[str],
) -> AssociationResult:
    result = AssociationResult(association=association)
    env = os.environ.copy()
    env["PROJECT_NAME"] = association

    backend_services = [service for service in recreate_services if service in {"backend", "asgi", "celery"}]
    edge_services = [service for service in recreate_services if service in {"frontend", "proxy"}]

    if backend_services:
        try:
            run_cmd([*compose_cmd_prefix, "up", "-d", "--build", "--force-recreate", *backend_services], env=env)
        except subprocess.CalledProcessError as exc:
            result.failures.append(
                f"Failed to recreate backend services ({' '.join(backend_services)}): exit code {exc.returncode}."
            )
    if edge_services:
        try:
            run_cmd([*compose_cmd_prefix, "up", "-d", "--build", "--force-recreate", *edge_services], env=env)
        except subprocess.CalledProcessError as exc:
            result.failures.append(
                f"Failed to recreate edge services ({' '.join(edge_services)}): exit code {exc.returncode}."
            )

    meta_data, wait_error = wait_for_meta_site(app_origin, timeout_seconds)
    if wait_error:
        result.failures.append(
            f"Could not get healthy /api/v1/meta/site within {timeout_seconds}s ({wait_error})."
        )
        return result

    project_name = meta_data.get("project_name")
    if project_name != association:
        result.failures.append(
            f"meta.site.data.project_name mismatch: expected '{association}', got '{project_name}'."
        )

    module_capabilities = meta_data.get("module_capabilities")
    if not isinstance(module_capabilities, dict):
        result.failures.append("meta.site.data.module_capabilities is missing or invalid.")
        return result

    default_landing_path = meta_data.get("default_landing_path")
    if not isinstance(default_landing_path, str) or not default_landing_path.startswith("/"):
        result.failures.append(
            f"meta.site.data.default_landing_path is invalid: {default_landing_path!r}."
        )
        default_landing_path = "/"
    result.default_landing_path = default_landing_path

    enabled_modules = [
        module_key
        for module_key, capability in sorted(module_capabilities.items())
        if isinstance(capability, dict) and capability.get("enabled") is True
    ]
    result.enabled_modules = enabled_modules

    validate_root_route(app_origin, default_landing_path, result)
    validate_modules(app_origin, module_capabilities, result)

    return result


def write_report(report_path: Path, app_origin: str, compose_file: str, results: list[AssociationResult]) -> None:
    generated_at = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    lines: list[str] = []
    lines.append("# Association QA Report")
    lines.append("")
    lines.append(f"- Generated: `{generated_at}`")
    lines.append(f"- App origin: `{app_origin}`")
    lines.append(f"- Compose file: `{compose_file}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Association | Landing | Enabled modules | Failures | Warnings |")
    lines.append("| --- | --- | ---: | ---: | ---: |")
    for result in results:
        lines.append(
            f"| `{result.association}` | `{result.default_landing_path or '-'}` | "
            f"{len(result.enabled_modules)} | {len(result.failures)} | {len(result.warnings)} |"
        )
    lines.append("")

    for result in results:
        lines.append(f"## {result.association}")
        lines.append("")
        lines.append(f"- Default landing path: `{result.default_landing_path or 'unknown'}`")
        lines.append(
            "- Enabled modules: "
            + (", ".join(f"`{module}`" for module in result.enabled_modules) if result.enabled_modules else "_none_")
        )
        lines.append("")
        if result.module_route_statuses:
            lines.append("| Module | Route | Enabled | Status |")
            lines.append("| --- | --- | --- | ---: |")
            for module_key, route, enabled, status in result.module_route_statuses:
                lines.append(f"| `{module_key}` | `{route}` | `{enabled}` | `{status}` |")
            lines.append("")
        if result.failures:
            lines.append("### Failures")
            lines.append("")
            for failure in result.failures:
                lines.append(f"- {failure}")
            lines.append("")
        if result.warnings:
            lines.append("### Warnings")
            lines.append("")
            for warning in result.warnings:
                lines.append(f"- {warning}")
            lines.append("")
        if not result.failures and not result.warnings:
            lines.append("- No issues detected.")
            lines.append("")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run multi-association QA checks for the decoupled stack.")
    parser.add_argument(
        "--associations",
        nargs="+",
        default=DEFAULT_ASSOCIATIONS,
        help=f"Association keys to validate (default: {' '.join(DEFAULT_ASSOCIATIONS)}).",
    )
    parser.add_argument(
        "--compose-file",
        default=os.environ.get("COMPOSE_FILE_PATH", DEFAULT_COMPOSE_FILE),
        help="Compose file path (default: docker-compose.yml or COMPOSE_FILE_PATH).",
    )
    parser.add_argument(
        "--env-file",
        default=None,
        help="Compose env file path. Defaults to .env, then .env.example if present.",
    )
    parser.add_argument(
        "--app-origin",
        default=os.environ.get("NEXT_PUBLIC_APP_ORIGIN", DEFAULT_APP_ORIGIN),
        help="Public app origin used for HTTP checks (default: NEXT_PUBLIC_APP_ORIGIN or http://localhost:8080).",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=180,
        help="Timeout while waiting for healthy /api/v1/meta/site per association.",
    )
    parser.add_argument(
        "--report-path",
        default="docs/association-qa-report.md",
        help="Path to write markdown report.",
    )
    parser.add_argument(
        "--recreate-services",
        nargs="+",
        default=DEFAULT_RECREATE_SERVICES,
        help="Compose services recreated per association switch.",
    )
    parser.add_argument(
        "--keep-running",
        action="store_true",
        help="Do not run 'docker compose down' after checks.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    env_file = resolve_env_file(args.env_file)
    compose_cmd_prefix = ["docker", "compose", "-f", args.compose_file]
    if env_file is not None:
        compose_cmd_prefix.extend(["--env-file", str(env_file)])

    app_origin = args.app_origin
    if app_origin == DEFAULT_APP_ORIGIN and env_file is not None:
        env_values = parse_env_file(env_file)
        app_origin = env_values.get("NEXT_PUBLIC_APP_ORIGIN", app_origin)

    run_cmd([*compose_cmd_prefix, "version"])
    run_cmd([*compose_cmd_prefix, "up", "-d", "db", "redis"])

    results: list[AssociationResult] = []
    for association in args.associations:
        print("")
        print(f"=== Checking association: {association} ===")
        try:
            result = run_association_checks(
                association=association,
                compose_cmd_prefix=compose_cmd_prefix,
                app_origin=app_origin,
                timeout_seconds=args.timeout_seconds,
                recreate_services=args.recreate_services,
            )
        except Exception as exc:  # noqa: BLE001
            result = AssociationResult(association=association)
            result.failures.append(f"Unexpected exception while checking association: {exc}")
        print(
            f"Result {association}: failures={len(result.failures)} warnings={len(result.warnings)} "
            f"enabled_modules={len(result.enabled_modules)}"
        )
        results.append(result)

    report_path = Path(args.report_path)
    write_report(report_path, app_origin, args.compose_file, results)
    print("")
    print(f"Report written: {report_path}")

    if not args.keep_running:
        run_cmd([*compose_cmd_prefix, "down"])

    total_failures = sum(len(result.failures) for result in results)
    return 1 if total_failures else 0


if __name__ == "__main__":
    sys.exit(main())
