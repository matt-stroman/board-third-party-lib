#!/usr/bin/env python3
"""Developer CLI for local workflows in the board-enthusiasts repository.

This script is the primary developer automation entry point for:
- bootstrap/setup (`bootstrap`)
- database/auth/API/web runtime profiles (`database`, `auth`, `api`, `web`)
- full-stack verification in one pass (`all-tests`)
- repository verification (`verify`)
- backend testing (`test`)
- API contract linting/testing and Postman workspace operations
  (`api-login`, `api-lint`, `api-test`, `api-mock`, `api-sync`)
- environment diagnostics (`doctor`)
- deterministic local auth/catalog sample data seeding (`seed-data`)

Use `python ./scripts/dev.py --help` and `python ./scripts/dev.py <command> --help`
for command-specific help.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import getpass
import json
import math
import os
import re
import shlex
import shutil
import signal
import socket
import ssl
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import zlib
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


@dataclass(frozen=True)
class DevConfig:
    """Configuration values used across CLI commands.

    Attributes:
        repo_root: Repository root directory.
        frontend_root: Relative path to the frontend submodule root.
        frontend_package_json: Relative path to the frontend package manifest.
        backend_base_url: Default local backend base URL.
        frontend_base_url: Default local frontend base URL.
        api_root: Relative path to the API submodule root.
        api_spec: Relative path to the OpenAPI specification file.
        api_contract_collection: Relative path to the Git-tracked contract test collection.
        api_local_environment: Relative path to the local Postman environment template.
        api_mock_environment: Relative path to the mock Postman environment template.
        api_mock_admin_environment: Relative path to the mock admin environment template.
        api_mock_provision_script: Relative path to the Node.js mock provisioning helper.
        migration_root_package_json: Relative path to the root npm workspace manifest.
        migration_spa_root: Relative path to the React SPA workspace.
        migration_spa_workspace_name: npm workspace name for the React SPA shell.
        migration_workers_root: Relative path to the Workers API workspace.
        migration_workers_workspace_name: npm workspace name for the Workers API shell.
        migration_contract_root: Relative path to the shared TypeScript contract package.
        supabase_root: Relative path to the Supabase project folder.
        local_env_example: Relative path to the local env example.
        staging_env_example: Relative path to the staging env example.
        production_env_example: Relative path to the production env example.
        local_env_file: Relative path to the local env file.
        staging_env_file: Relative path to the staging env file.
        production_env_file: Relative path to the production env file.
        cloudflare_pages_template: Relative path to the Cloudflare Pages config template.
        cloudflare_workers_template: Relative path to the Cloudflare Workers config template.
        cloudflare_fallback_pages_root: Relative path to the standalone fallback Pages content root.
        migration_spa_base_url: Default local React SPA URL.
        migration_workers_base_url: Default local Workers API URL.
    """

    repo_root: Path
    frontend_root: str
    frontend_package_json: str
    backend_base_url: str
    frontend_base_url: str
    api_root: str
    api_spec: str
    api_contract_collection: str
    api_local_environment: str
    api_mock_environment: str
    api_mock_admin_environment: str
    api_mock_provision_script: str
    migration_root_package_json: str
    migration_spa_root: str
    migration_spa_workspace_name: str
    migration_workers_root: str
    migration_workers_workspace_name: str
    migration_contract_root: str
    supabase_root: str
    local_env_example: str
    staging_env_example: str
    production_env_example: str
    local_env_file: str
    staging_env_file: str
    production_env_file: str
    cloudflare_pages_template: str
    cloudflare_workers_template: str
    cloudflare_fallback_pages_root: str
    migration_spa_base_url: str
    migration_workers_base_url: str


@dataclass(frozen=True)
class ParityStackStartupResult:
    """Tracks which local stack pieces parity launched for temporary use.

    Attributes:
        started_runtime: Whether parity had to start or repair the local Supabase runtime.
        started_backend: Whether parity launched the managed backend API process.
        started_frontend: Whether parity launched the managed frontend SPA process.
    """

    started_runtime: bool = False
    started_backend: bool = False
    started_frontend: bool = False


class DevCliError(RuntimeError):
    """Raised for expected CLI/runtime failures with user-friendly messages."""


REDOCLY_CLI_VERSION = "2.20.3"
DEPLOY_SMOKE_USER_AGENT = "Mozilla/5.0 (compatible; BoardEnthusiastsDevCli/1.0; +https://boardenthusiasts.com)"
ROUTING_DNS_RECORD_TYPES = {"A", "AAAA", "CNAME"}

SUPABASE_PROFILE_DATABASE = "database"
SUPABASE_PROFILE_AUTH = "auth"
SUPABASE_PROFILE_API = "api"
SUPABASE_PROFILE_WEB = "web"

SUPABASE_PROFILE_EXCLUDES: dict[str, tuple[str, ...]] = {
    SUPABASE_PROFILE_AUTH: (
        "studio",
        "storage-api",
        "imgproxy",
        "postgres-meta",
        "realtime",
        "postgrest",
        "edge-runtime",
        "logflare",
        "vector",
        "supavisor",
    ),
    SUPABASE_PROFILE_API: (
        "studio",
        "imgproxy",
        "postgres-meta",
        "realtime",
        "edge-runtime",
        "logflare",
        "vector",
        "supavisor",
    ),
    SUPABASE_PROFILE_WEB: (
        "studio",
        "imgproxy",
        "postgres-meta",
        "realtime",
        "edge-runtime",
        "logflare",
        "vector",
        "supavisor",
    ),
}

SUPABASE_PROFILE_DESCRIPTIONS: dict[str, str] = {
    SUPABASE_PROFILE_DATABASE: "database only",
    SUPABASE_PROFILE_AUTH: "database + auth",
    SUPABASE_PROFILE_API: "database + auth + backend dependencies",
    SUPABASE_PROFILE_WEB: "database + auth + backend dependencies",
}

LOCAL_SUPABASE_DB_HOST = "127.0.0.1"
LOCAL_SUPABASE_DB_PORT = 54322
LOCAL_SUPABASE_URL = "http://127.0.0.1:54321"
LOCAL_SUPABASE_AUTH_URL = "http://127.0.0.1:54321/auth/v1/health"
LOCAL_SUPABASE_STUDIO_PORT = 54323
LOCAL_MAILPIT_PORT = 54324
LOCAL_WORKERS_PORT = 8787
LOCAL_FRONTEND_PORT = 4173
SUPABASE_STATUS_TIMEOUT_SECONDS = 15
SUPABASE_STOP_TIMEOUT_SECONDS = 30
SUPABASE_START_TIMEOUT_SECONDS = 300
PROCESS_STOP_TIMEOUT_SECONDS = 15
PROCESS_STATUS_TIMEOUT_SECONDS = 5
SUPPORTED_ENVIRONMENT_TARGETS = ("local", "staging", "production")
DEFAULT_CLOUDFLARE_FALLBACK_PAGES_PROJECT_NAME = "board-enthusiasts-fallback"
GITHUB_ENVIRONMENT_SECRET_NAMES = frozenset(
    {
        "SUPABASE_AUTH_DISCORD_CLIENT_SECRET",
        "SUPABASE_SECRET_KEY",
        "SUPABASE_DB_PASSWORD",
        "SUPABASE_ACCESS_TOKEN",
        "SUPABASE_AUTH_GITHUB_CLIENT_SECRET",
        "SUPABASE_AUTH_GOOGLE_CLIENT_SECRET",
        "CLOUDFLARE_API_TOKEN",
        "TURNSTILE_SECRET_KEY",
        "BREVO_API_KEY",
        "DEPLOY_SMOKE_SECRET",
        "DEPLOY_SMOKE_USER_PASSWORD",
    }
)
DEPLOY_REQUIRED_ENV_NAMES = (
    "BOARD_ENTHUSIASTS_SPA_BASE_URL",
    "BOARD_ENTHUSIASTS_WORKERS_BASE_URL",
    "SUPABASE_URL",
    "SUPABASE_PROJECT_REF",
    "SUPABASE_PUBLISHABLE_KEY",
    "SUPABASE_SECRET_KEY",
    "SUPABASE_DB_PASSWORD",
    "SUPABASE_ACCESS_TOKEN",
    "SUPABASE_AVATARS_BUCKET",
    "SUPABASE_CARD_IMAGES_BUCKET",
    "SUPABASE_HERO_IMAGES_BUCKET",
    "SUPABASE_LOGO_IMAGES_BUCKET",
    "CLOUDFLARE_ACCOUNT_ID",
    "CLOUDFLARE_API_TOKEN",
    "VITE_TURNSTILE_SITE_KEY",
    "TURNSTILE_SECRET_KEY",
    "BREVO_API_KEY",
    "BREVO_SIGNUPS_LIST_ID",
    "ALLOWED_WEB_ORIGINS",
    "SUPPORT_REPORT_RECIPIENT",
    "SUPPORT_REPORT_SENDER_EMAIL",
    "SUPPORT_REPORT_SENDER_NAME",
    "DEPLOY_SMOKE_SECRET",
    "VITE_LANDING_MODE",
)
DEPLOY_SECRET_ENV_NAMES = (
    "SUPABASE_SECRET_KEY",
    "SUPABASE_DB_PASSWORD",
    "SUPABASE_ACCESS_TOKEN",
    "CLOUDFLARE_API_TOKEN",
    "TURNSTILE_SECRET_KEY",
    "BREVO_API_KEY",
    "DEPLOY_SMOKE_SECRET",
    "DEPLOY_SMOKE_USER_PASSWORD",
)
DEPLOY_BREVO_REQUIRED_ATTRIBUTES = ("SOURCE", "BE_LIFECYCLE_STATUS", "BE_ROLE_INTEREST")
FULL_MVP_DEPLOY_SMOKE_REQUIRED_ENV_NAMES = (
    "DEPLOY_SMOKE_PLAYER_EMAIL",
    "DEPLOY_SMOKE_DEVELOPER_EMAIL",
    "DEPLOY_SMOKE_MODERATOR_EMAIL",
    "DEPLOY_SMOKE_USER_PASSWORD",
)
STAGING_DEPLOY_REQUIRED_ENV_NAMES = ("DEPLOY_SMOKE_USER_PASSWORD",)
OPTIONAL_DEPLOY_ENV_NAMES = (
    "SUPABASE_AUTH_DISCORD_CLIENT_ID",
    "SUPABASE_AUTH_DISCORD_CLIENT_SECRET",
    "SUPABASE_AUTH_GITHUB_CLIENT_ID",
    "SUPABASE_AUTH_GITHUB_CLIENT_SECRET",
    "SUPABASE_AUTH_GOOGLE_CLIENT_ID",
    "SUPABASE_AUTH_GOOGLE_CLIENT_SECRET",
    "VITE_SUPABASE_AUTH_DISCORD_ENABLED",
    "VITE_SUPABASE_AUTH_GITHUB_ENABLED",
    "VITE_SUPABASE_AUTH_GOOGLE_ENABLED",
)
DEFAULT_BOOTSTRAP_SUPER_ADMIN_USER_NAME = "bootstrap-admin"
DEFAULT_BOOTSTRAP_SUPER_ADMIN_FIRST_NAME = "Bootstrap"
DEFAULT_BOOTSTRAP_SUPER_ADMIN_LAST_NAME = "Admin"
DEFAULT_BOOTSTRAP_SUPER_ADMIN_DISPLAY_NAME = "Bootstrap Admin"
LEGACY_PAGES_DRY_RUN_REQUIRED_ENV_NAMES = (
    "BOARD_ENTHUSIASTS_WORKERS_BASE_URL",
    "SUPABASE_URL",
    "SUPABASE_PUBLISHABLE_KEY",
    "VITE_TURNSTILE_SITE_KEY",
    "VITE_LANDING_MODE",
)
LEGACY_WORKERS_DRY_RUN_REQUIRED_ENV_NAMES = (
    "BOARD_ENTHUSIASTS_WORKERS_BASE_URL",
    "SUPABASE_URL",
    "SUPABASE_PUBLISHABLE_KEY",
    "SUPABASE_AVATARS_BUCKET",
    "SUPABASE_CARD_IMAGES_BUCKET",
    "SUPABASE_HERO_IMAGES_BUCKET",
    "SUPABASE_LOGO_IMAGES_BUCKET",
    "CLOUDFLARE_ACCOUNT_ID",
    "CLOUDFLARE_API_TOKEN",
    "BREVO_SIGNUPS_LIST_ID",
    "ALLOWED_WEB_ORIGINS",
    "SUPPORT_REPORT_RECIPIENT",
    "SUPPORT_REPORT_SENDER_EMAIL",
    "SUPPORT_REPORT_SENDER_NAME",
)
DEPLOY_TRANSACTIONAL_STAGES = (
    "supabase_config",
    "supabase_schema",
    "supabase_storage",
    "supabase_demo_seed",
    "pages_project",
    "workers_deploy",
    "pages_deploy",
)

LOCAL_SUPABASE_API_PORT_ENV = "BOARD_ENTHUSIASTS_LOCAL_SUPABASE_API_PORT"
LOCAL_SUPABASE_DB_PORT_ENV = "BOARD_ENTHUSIASTS_LOCAL_SUPABASE_DB_PORT"
LOCAL_SUPABASE_SHADOW_PORT_ENV = "BOARD_ENTHUSIASTS_LOCAL_SUPABASE_SHADOW_PORT"
LOCAL_SUPABASE_STUDIO_PORT_ENV = "BOARD_ENTHUSIASTS_LOCAL_SUPABASE_STUDIO_PORT"
LOCAL_MAILPIT_PORT_ENV = "BOARD_ENTHUSIASTS_LOCAL_MAILPIT_PORT"
LOCAL_WORKERS_PORT_ENV = "BOARD_ENTHUSIASTS_LOCAL_WORKERS_PORT"
LOCAL_FRONTEND_PORT_ENV = "BOARD_ENTHUSIASTS_LOCAL_FRONTEND_PORT"


def get_stack_state_path(config: DevConfig, *, stack_name: str) -> Path:
    """Return the on-disk state file used for managed local stack processes.

    Args:
        config: CLI configuration containing the repository root.
        stack_name: Logical stack name used in the state file name.

    Returns:
        State file path under the shared CLI logs directory.
    """

    return config.repo_root / ".dev-cli-logs" / f"{stack_name}-state.json"


def get_deploy_state_path(config: DevConfig, *, target: str) -> Path:
    """Return the local persisted deployment-state path for an environment target."""

    return config.repo_root / ".dev-cli-logs" / f"deploy-{target}-state.json"


def get_int_environment_override(name: str, *, default: int) -> int:
    """Return an integer environment override or the provided default."""

    raw = os.environ.get(name, "").strip()
    if not raw:
        return default

    try:
        value = int(raw)
    except ValueError as ex:
        raise DevCliError(f"Environment override {name} must be an integer port value.") from ex
    if value <= 0:
        raise DevCliError(f"Environment override {name} must be greater than zero.")
    return value


def get_local_supabase_api_port() -> int:
    """Return the effective local Supabase API port."""

    return get_int_environment_override(LOCAL_SUPABASE_API_PORT_ENV, default=54321)


def get_local_supabase_db_port() -> int:
    """Return the effective local Supabase database port."""

    return get_int_environment_override(LOCAL_SUPABASE_DB_PORT_ENV, default=LOCAL_SUPABASE_DB_PORT)


def get_local_supabase_auth_url() -> str:
    """Return the effective local Supabase auth health URL."""

    return f"{get_local_supabase_url().rstrip('/')}/auth/v1/health"


def get_local_supabase_url() -> str:
    """Return the effective local Supabase API base URL."""

    return f"http://127.0.0.1:{get_local_supabase_api_port()}"


def get_local_mailpit_port() -> int:
    """Return the effective local Mailpit port."""

    return get_int_environment_override(LOCAL_MAILPIT_PORT_ENV, default=LOCAL_MAILPIT_PORT)


def get_local_mailpit_url() -> str:
    """Return the effective local Mailpit base URL."""

    return f"http://127.0.0.1:{get_local_mailpit_port()}"


def get_local_workers_port() -> int:
    """Return the effective local Workers API port."""

    return get_int_environment_override(LOCAL_WORKERS_PORT_ENV, default=LOCAL_WORKERS_PORT)


def get_local_frontend_port() -> int:
    """Return the effective local SPA port."""

    return get_int_environment_override(LOCAL_FRONTEND_PORT_ENV, default=LOCAL_FRONTEND_PORT)


def get_local_workers_base_url() -> str:
    """Return the effective local Workers API base URL."""

    return f"http://127.0.0.1:{get_local_workers_port()}"


def get_local_frontend_base_url() -> str:
    """Return the effective local frontend base URL."""

    return f"http://127.0.0.1:{get_local_frontend_port()}"


def get_runtime_profile_state_path(config: DevConfig) -> Path:
    """Return the on-disk state file used for the active local runtime profile."""

    return get_stack_state_path(config, stack_name="runtime-profile")


def dedupe_paths(paths: Sequence[Path]) -> list[Path]:
    """Return the supplied paths without duplicates while preserving order.

    Args:
        paths: Candidate filesystem paths.

    Returns:
        Stable list with duplicate path entries removed.
    """

    seen: set[str] = set()
    unique_paths: list[Path] = []
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique_paths.append(path)
    return unique_paths


def collect_globbed_paths(base_path: Path, *patterns: str) -> list[Path]:
    """Collect existing paths that match one or more glob patterns.

    Args:
        base_path: Root path used for glob expansion.
        patterns: Glob expressions to expand beneath ``base_path``.

    Returns:
        Existing matching paths in stable order.
    """

    matches: list[Path] = []
    if not base_path.exists():
        return matches

    for pattern in patterns:
        matches.extend(path for path in base_path.glob(pattern) if path.exists() or path.is_symlink())
    return dedupe_paths(matches)


def get_clean_confirmation_notes(command_name: str) -> list[str]:
    """Return human-friendly notes describing what a local clean preserves.

    Args:
        command_name: Runtime command being cleaned.

    Returns:
        Friendly bullet text displayed in the destructive confirmation prompt.
    """

    notes = [
        "Your config secrets in /config/.env* are preserved.",
        "IDE settings folders such as .idea, .vscode, and .vs are preserved.",
        "Tracked or otherwise non-ignored working files are preserved.",
        "Local AI agent context/config files such as .codex-tmp and AGENTS.md are preserved.",
    ]
    if command_name == "web":
        notes.append(
            "This CLI does not currently provision a managed browser profile, browser cache, or trusted local HTTPS certs, so there is nothing additional to clear there today."
        )
    return notes


def confirm_clean_action(*, command_name: str, summary_lines: Sequence[str]) -> bool:
    """Prompt before performing destructive local cleanup.

    Args:
        command_name: Runtime command being cleaned.
        summary_lines: Friendly summary of what will be removed.

    Returns:
        ``True`` when the user confirmed by typing ``clean``; otherwise ``False``.
    """

    command_label = command_name if command_name == "clean-all" or " " in command_name else f"{command_name} clean"
    target_scope = "the full local maintained stack" if command_name == "clean-all" else "this area"
    print(f"Warning: `{command_label}` permanently removes local automation-managed state for {target_scope}.")
    if command_name == "clean-all":
        print("This action is intended to reset your full local maintained stack close to a fresh checkout.")
    else:
        print("This action is intended to reset your local setup close to a fresh checkout for that area.")
    print("")
    print("It will remove:")
    for line in summary_lines:
        print(f"- {line}")
    print("")
    print("It will keep:")
    for line in get_clean_confirmation_notes(command_name):
        print(f"- {line}")
    print("")
    response = input("Continue? [y/N]: ").strip().lower()
    if response != "y":
        print("Clean cancelled. No files were removed.")
        return False
    return True


def remove_path(path: Path) -> bool:
    """Remove a file, symlink, or directory when it exists.

    Args:
        path: Filesystem path to remove.

    Returns:
        ``True`` when a filesystem entry was removed; otherwise ``False``.
    """

    if not path.exists() and not path.is_symlink():
        return False

    if path.is_symlink() or path.is_file():
        path.unlink()
        return True

    shutil.rmtree(path)
    return True


def remove_paths(paths: Sequence[Path]) -> list[Path]:
    """Remove the supplied filesystem paths when they exist.

    Args:
        paths: Candidate files/directories to delete.

    Returns:
        Paths that were actually removed.
    """

    removed: list[Path] = []
    for path in dedupe_paths(paths):
        if remove_path(path):
            removed.append(path)
    return removed


def get_database_clean_paths(config: DevConfig) -> list[Path]:
    """Return automation-managed local artifacts removed by `database clean`.

    Args:
        config: CLI configuration containing repository paths.

    Returns:
        Existing database/runtime cleanup paths.
    """

    logs_dir = config.repo_root / ".dev-cli-logs"
    paths = [
        get_runtime_profile_state_path(config),
        get_stack_state_path(config, stack_name="api"),
        get_stack_state_path(config, stack_name="web"),
        logs_dir / "workers-api.log",
        logs_dir / "migration-spa.log",
        config.repo_root / config.supabase_root / ".branches",
        config.repo_root / config.supabase_root / ".temp",
        config.repo_root / "supabase" / ".temp",
    ]
    return dedupe_paths(paths)


def get_api_clean_paths(config: DevConfig) -> list[Path]:
    """Return automation-managed local artifacts removed by `api clean`.

    Args:
        config: CLI configuration containing repository paths.

    Returns:
        Existing backend/runtime cleanup paths.
    """

    backend_root = config.repo_root / "backend"
    worker_root = config.repo_root / config.migration_workers_root
    paths = get_database_clean_paths(config) + [
        get_stack_state_path(config, stack_name="api"),
        get_stack_state_path(config, stack_name="web"),
        worker_root / ".dev.vars",
        worker_root / ".wrangler",
        config.repo_root / ".wrangler",
        backend_root / "node_modules",
        backend_root / "logs",
        backend_root / ".tmp",
    ]
    paths.extend(collect_globbed_paths(backend_root / "apps", "*/node_modules", "*/dist", "*/*.tsbuildinfo"))
    paths.extend(collect_globbed_paths(backend_root, "*.tsbuildinfo", "*.log"))
    return dedupe_paths(paths)


def get_web_clean_paths(config: DevConfig) -> list[Path]:
    """Return automation-managed local artifacts removed by `web clean`.

    Args:
        config: CLI configuration containing repository paths.

    Returns:
        Existing full-stack cleanup paths.
    """

    frontend_root = config.repo_root / "frontend"
    packages_root = config.repo_root / "packages"
    paths = get_api_clean_paths(config) + [
        config.repo_root / ".dev-cli-logs",
        config.repo_root / "node_modules",
        config.repo_root / "artifacts",
        config.repo_root / "test-results",
        config.repo_root / "playwright-report",
        frontend_root / "node_modules",
        frontend_root / "dist",
        frontend_root / "coverage",
        config.repo_root / "tests" / "parity" / ".auth",
        config.repo_root / "tests" / "parity" / "test-results",
        config.repo_root / "tests" / "parity" / "playwright-report",
    ]
    paths.extend(collect_globbed_paths(config.repo_root, "*.tsbuildinfo"))
    paths.extend(collect_globbed_paths(frontend_root, "*.tsbuildinfo"))
    paths.extend(collect_globbed_paths(packages_root, "*/node_modules", "*/dist", "*/*.tsbuildinfo"))
    return dedupe_paths(paths)


def write_step(message: str) -> None:
    """Print a visible step marker for long-running actions.

    Args:
        message: Human-readable step description to print.

    Returns:
        None.
    """

    print(f"==> {message}", flush=True)


def print_console_text(text: str) -> None:
    """Print text while tolerating Windows console encoding limitations."""

    try:
        print(text)
    except UnicodeEncodeError:
        if hasattr(sys.stdout, "buffer"):
            sys.stdout.buffer.write(text.encode(sys.stdout.encoding or "utf-8", errors="replace"))
            sys.stdout.buffer.write(b"\n")
            sys.stdout.buffer.flush()
        else:
            print(text.encode("utf-8", errors="replace").decode("utf-8"))


def quote_cmd(parts: Sequence[str]) -> str:
    """Render a subprocess command as a shell-like string for error messages.

    Args:
        parts: Command tokens to quote and join.

    Returns:
        A shell-safe string representation of the command.
    """

    return " ".join(shlex.quote(p) for p in parts)


def get_environment_file_path(config: DevConfig, *, target: str) -> Path:
    """Resolve the root-managed environment file path for a named environment."""

    if target == "local":
        return config.repo_root / config.local_env_file
    if target == "staging":
        return config.repo_root / config.staging_env_file
    if target == "production":
        return config.repo_root / config.production_env_file
    raise DevCliError(f"Unsupported environment target: {target}")


def get_environment_example_path(config: DevConfig, *, target: str) -> Path:
    """Resolve the checked-in example environment file path for a named environment."""

    if target == "local":
        return config.repo_root / config.local_env_example
    if target == "staging":
        return config.repo_root / config.staging_env_example
    if target == "production":
        return config.repo_root / config.production_env_example
    raise DevCliError(f"Unsupported environment target: {target}")


def apply_environment_file(path: Path, *, preserve_existing: bool = True) -> dict[str, str]:
    """Load a root-managed ``.env`` file into the current process environment."""

    if not path.exists():
        return {}

    parsed = parse_env_assignments(path.read_text(encoding="utf-8"))
    original_keys = set(os.environ)
    for key, value in parsed.items():
        if preserve_existing and key in original_keys:
            continue
        os.environ[key] = value
    return parsed


def infer_supabase_url_from_environment() -> str | None:
    """Infer the default hosted Supabase URL when only the project ref is available.

    Returns:
        The inferred hosted Supabase URL when safe, otherwise ``None``.
    """

    explicit_url = os.environ.get("SUPABASE_URL", "").strip()
    if explicit_url:
        return explicit_url

    app_env = os.environ.get("BOARD_ENTHUSIASTS_APP_ENV", "").strip().lower()
    if app_env == "local":
        return None

    project_ref = os.environ.get("SUPABASE_PROJECT_REF", "").strip()
    if not project_ref:
        return None

    return f"https://{project_ref}.supabase.co"


def get_supabase_project_ref_from_url(supabase_url: str) -> str | None:
    """Extract the default Supabase project ref from a hosted project URL when possible."""

    hostname = (urllib.parse.urlparse(supabase_url).hostname or "").strip().lower()
    if not hostname.endswith(".supabase.co"):
        return None

    project_ref = hostname[: -len(".supabase.co")].strip()
    return project_ref or None


def normalize_supabase_environment() -> None:
    """Normalize derived Supabase environment values for the current CLI process."""

    inferred_url = infer_supabase_url_from_environment()
    if inferred_url:
        os.environ["SUPABASE_URL"] = inferred_url


def resolve_deploy_target(*, staging: bool) -> str:
    """Resolve the logical deployment target from CLI flags."""

    return "staging" if staging else "production"


def auto_load_command_environment(
    config: DevConfig,
    *,
    command_name: str,
    deploy_target: str | None = None,
) -> Path | None:
    """Load the root-managed environment file relevant to the current CLI command."""

    if command_name in {"deploy-staging", "deploy", "deploy-fallback-pages", "bootstrap-super-admin"}:
        env_path = get_environment_file_path(config, target=deploy_target or "staging")
        apply_environment_file(env_path)
        normalize_supabase_environment()
        return env_path if env_path.exists() else None

    if command_name == "env":
        return None

    env_path = get_environment_file_path(config, target="local")
    apply_environment_file(env_path)
    normalize_supabase_environment()
    return env_path if env_path.exists() else None


def require_environment_values(*names: str, context: str) -> dict[str, str]:
    """Resolve required environment variables or raise a user-friendly error."""

    def normalize_environment_value(value: str) -> str:
        trimmed = value.strip()
        normalized = trimmed.lower()
        if normalized.startswith("optional-for-") or normalized == "replace-me" or normalized.startswith("replace-with-"):
            return ""
        return trimmed

    resolved: dict[str, str] = {}
    missing: list[str] = []
    for name in names:
        value = normalize_environment_value(os.environ.get(name, ""))
        if not value:
            missing.append(name)
            continue
        resolved[name] = value

    if missing:
        raise DevCliError(
            f"{context} requires the following environment values:\n- " + "\n- ".join(missing)
        )

    return resolved


def collect_present_environment_values(*names: str) -> dict[str, str]:
    """Collect optional non-placeholder environment values for the current process."""

    collected: dict[str, str] = {}
    for name in names:
        value = os.environ.get(name, "").strip()
        normalized = value.lower()
        if not value or normalized == "replace-me" or normalized.startswith("replace-with-") or normalized.startswith("optional-for-"):
            continue
        collected[name] = value
    return collected


def get_frontend_oauth_enabled_value(
    values: dict[str, str] | os._Environ[str],
    *,
    provider: str,
) -> str:
    """Resolve the frontend-visible OAuth enablement flag for a provider.

    The maintained stack keeps provider client IDs in the root-managed environment
    file, so the SPA can infer whether to show a provider button without exposing
    the secret or requiring a second manual toggle.
    """

    explicit_key = f"VITE_SUPABASE_AUTH_{provider.upper()}_ENABLED"
    explicit_value = values.get(explicit_key, "").strip()
    if explicit_value:
        return explicit_value

    client_id_key = f"SUPABASE_AUTH_{provider.upper()}_CLIENT_ID"
    return "true" if values.get(client_id_key, "").strip() else ""


def open_environment_file(path: Path) -> None:
    """Open an environment file in the platform default application."""

    if os.name == "nt":
        os.startfile(path)  # type: ignore[attr-defined]
        return

    if sys.platform == "darwin":
        run_command(["open", str(path)], check=False)
        return

    run_command(["xdg-open", str(path)], check=False)


def run_command(
    cmd: Sequence[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
    capture_output: bool = False,
    text: bool = True,
    stdin=None,
    stdout=None,
    stderr=None,
    env: dict[str, str] | None = None,
    timeout_seconds: float | None = None,
    input_data: str | None = None,
) -> subprocess.CompletedProcess:
    """Run a subprocess command with consistent error handling.

    Args:
        cmd: Command and arguments to execute.
        cwd: Optional working directory for the subprocess.
        check: When True, raise an error on non-zero exit code.
        capture_output: When True, capture stdout/stderr into the result.
        text: When True, use text mode for subprocess I/O.
        stdin: Optional stdin stream or data source for the subprocess.
        stdout: Optional stdout destination override.
        stderr: Optional stderr destination override.
        env: Optional environment variables for the subprocess.
        timeout_seconds: Optional timeout applied to the subprocess execution.
        input_data: Optional text-mode stdin payload passed directly to the subprocess.

    Returns:
        The completed subprocess result.

    Raises:
        DevCliError: If ``check`` is True and the command exits non-zero.
    """

    resolved_cmd = list(cmd)
    executable = resolved_cmd[0]
    if os.path.dirname(executable) == "":
        resolved_executable = shutil.which(executable)
        if resolved_executable:
            resolved_cmd[0] = resolved_executable

    result = subprocess.run(
        resolved_cmd,
        cwd=str(cwd) if cwd else None,
        check=False,
        capture_output=capture_output,
        text=text,
        encoding="utf-8" if text else None,
        errors="replace" if text else None,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        env=env,
        timeout=timeout_seconds,
        input=input_data,
    )
    if check and result.returncode != 0:
        raise DevCliError(f"Command failed ({result.returncode}): {quote_cmd(resolved_cmd)}")
    return result


def assert_command_available(name: str) -> None:
    """Ensure a required executable exists on PATH.

    Args:
        name: Executable name to look up on ``PATH``.

    Returns:
        None.

    Raises:
        DevCliError: If the command is not available on ``PATH``.
    """

    if shutil.which(name) is None:
        raise DevCliError(f"Required command '{name}' was not found on PATH.")


def resolve_github_cli_executable() -> str:
    """Resolve the official GitHub CLI executable.

    On Windows, prefer ``gh.exe`` so npm-installed ``gh.cmd`` / ``gh.ps1`` shims do
    not shadow the official GitHub CLI.

    Returns:
        Absolute path to the resolved GitHub CLI executable.

    Raises:
        DevCliError: If GitHub CLI is unavailable or a non-official shim shadows it.
    """

    if os.name == "nt":
        github_cli_executable = shutil.which("gh.exe")
        if github_cli_executable:
            return github_cli_executable

    github_cli_executable = shutil.which("gh")
    if github_cli_executable is None:
        raise DevCliError("Required command 'gh' was not found on PATH.")

    if os.name == "nt" and Path(github_cli_executable).suffix.lower() != ".exe":
        gh_candidates: list[str] = []
        try:
            where_result = subprocess.run(
                ["where.exe", "gh"],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            where_result = None

        if where_result and where_result.stdout:
            gh_candidates = [line.strip() for line in where_result.stdout.splitlines() if line.strip()]

        detail = ""
        if gh_candidates:
            detail = "\nAvailable gh candidates:\n- " + "\n- ".join(gh_candidates)

        raise DevCliError(
            "Resolved 'gh' to a non-GitHub CLI wrapper on PATH.\n"
            f"Found: {github_cli_executable}\n"
            "This usually means the npm 'gh' package is shadowing the official GitHub CLI.\n"
            "Install GitHub CLI and ensure 'gh.exe' is available on PATH, or move the GitHub CLI directory ahead of the Node shim directory."
            f"{detail}"
        )

    return github_cli_executable


def get_repo_root(script_path: Path) -> Path:
    """Resolve the repository root from this script path.

    Args:
        script_path: Path to this script file.

    Returns:
        The resolved repository root path.
    """

    return script_path.resolve().parent.parent


def test_submodule_initialized(path: Path) -> bool:
    """Return whether a git submodule appears initialized.

    Args:
        path: Submodule directory path.

    Returns:
        ``True`` when the submodule contains a `.git` entry, else ``False``.
    """

    return (path / ".git").exists()


def get_maintained_submodule_paths(config: DevConfig) -> tuple[tuple[str, Path], ...]:
    """Return the maintained top-level submodule paths tracked by the repository.

    Args:
        config: CLI configuration containing the repository root.

    Returns:
        Stable `(label, path)` pairs for each maintained submodule.
    """

    return (
        ("API", config.repo_root / "api"),
        ("Backend", config.repo_root / "backend"),
        ("Frontend", config.repo_root / "frontend"),
        ("BE Home", config.repo_root / "be-home"),
    )


def get_submodule_tracking_branch(config: DevConfig, path: Path) -> str:
    """Return the configured branch a submodule should track locally.

    Args:
        config: CLI configuration containing the repository root.
        path: Submodule directory path.

    Returns:
        The configured tracking branch name, defaulting to ``main``.
    """

    result = run_command(
        ["git", "config", "--file", ".gitmodules", "--get", f"submodule.{path.name}.branch"],
        cwd=config.repo_root,
        check=False,
        capture_output=True,
    )
    branch = result.stdout.strip() if result.returncode == 0 else ""
    return branch or "main"


def get_current_git_branch(path: Path) -> str | None:
    """Return the current checked out Git branch, if any.

    Args:
        path: Repository path to inspect.

    Returns:
        The current branch name, or ``None`` when ``HEAD`` is detached.
    """

    result = run_command(
        ["git", "symbolic-ref", "-q", "--short", "HEAD"],
        cwd=path,
        check=False,
        capture_output=True,
    )
    branch = result.stdout.strip() if result.returncode == 0 else ""
    return branch or None


def git_ref_exists(path: Path, ref_name: str) -> bool:
    """Return whether a Git ref exists in the repository.

    Args:
        path: Repository path to inspect.
        ref_name: Fully-qualified ref name to test.

    Returns:
        ``True`` when the ref exists, else ``False``.
    """

    result = run_command(
        ["git", "show-ref", "--verify", "--quiet", ref_name],
        cwd=path,
        check=False,
    )
    return result.returncode == 0


def get_git_ref_sha(path: Path, ref_name: str) -> str | None:
    """Return the commit SHA for a Git ref when available.

    Args:
        path: Repository path to inspect.
        ref_name: Git ref or revision expression to resolve.

    Returns:
        The resolved SHA string, or ``None`` when the ref cannot be resolved.
    """

    result = run_command(
        ["git", "rev-parse", ref_name],
        cwd=path,
        check=False,
        capture_output=True,
    )
    sha = result.stdout.strip() if result.returncode == 0 else ""
    return sha or None


def git_ref_is_ancestor(path: Path, ancestor_ref: str, descendant_ref: str) -> bool:
    """Return whether one Git ref is an ancestor of another.

    Args:
        path: Repository path to inspect.
        ancestor_ref: Candidate ancestor revision.
        descendant_ref: Candidate descendant revision.

    Returns:
        ``True`` when ``ancestor_ref`` is an ancestor of ``descendant_ref``.
    """

    result = run_command(
        ["git", "merge-base", "--is-ancestor", ancestor_ref, descendant_ref],
        cwd=path,
        check=False,
    )
    return result.returncode == 0


def reattach_maintained_submodule_heads(config: DevConfig) -> None:
    """Reattach maintained submodules to their tracked branches when safe.

    Git submodules naturally land in detached ``HEAD`` state after ``git submodule update``.
    For local development in this workspace we prefer branch checkouts, so this helper
    switches maintained submodules back to their configured tracking branches whenever the
    current detached commit already matches the branch tip or can be reached by a simple
    fast-forward of the local branch.

    Args:
        config: CLI configuration containing the repository root.

    Returns:
        None.
    """

    for label, path in get_maintained_submodule_paths(config):
        if not test_submodule_initialized(path):
            continue

        current_branch = get_current_git_branch(path)
        if current_branch:
            continue

        target_branch = get_submodule_tracking_branch(config, path)
        head_sha = get_git_ref_sha(path, "HEAD")
        local_ref = f"refs/heads/{target_branch}"
        remote_ref = f"refs/remotes/origin/{target_branch}"

        if not head_sha:
            print(f"{label}: unable to resolve detached HEAD commit; leaving current checkout as-is.")
            continue

        if git_ref_exists(path, local_ref):
            local_sha = get_git_ref_sha(path, local_ref)
            if local_sha != head_sha:
                if git_ref_is_ancestor(path, local_ref, "HEAD"):
                    run_command(["git", "branch", "-f", target_branch, "HEAD"], cwd=path)
                else:
                    print(
                        f"{label}: detached HEAD at {head_sha[:7]} was not a fast-forward of local '{target_branch}', "
                        "so it was left detached to avoid rewriting branch history."
                    )
                    continue

            switch_result = run_command(["git", "switch", target_branch], cwd=path, check=False, capture_output=True)
            if switch_result.returncode != 0:
                detail = switch_result.stderr.strip() or switch_result.stdout.strip() or "Git refused to switch branches."
                print(f"{label}: could not switch back to '{target_branch}': {detail}")
            continue

        if git_ref_exists(path, remote_ref):
            if not git_ref_is_ancestor(path, remote_ref, "HEAD"):
                print(
                    f"{label}: detached HEAD at {head_sha[:7]} did not fast-forward the tracked remote branch "
                    f"'{target_branch}', so it was left detached."
                )
                continue

            run_command(["git", "branch", "--track", target_branch, f"origin/{target_branch}"], cwd=path)
            run_command(["git", "branch", "-f", target_branch, "HEAD"], cwd=path)
            switch_result = run_command(["git", "switch", target_branch], cwd=path, check=False, capture_output=True)
            if switch_result.returncode != 0:
                detail = switch_result.stderr.strip() or switch_result.stdout.strip() or "Git refused to switch branches."
                print(f"{label}: could not switch back to '{target_branch}': {detail}")
            continue

        print(f"{label}: tracked branch '{target_branch}' was not available locally or on origin; leaving detached HEAD in place.")


def find_docker_desktop_executable() -> Path | None:
    """Return the expected Docker Desktop executable path on Windows when available.

    Returns:
        Path to ``Docker Desktop.exe`` when found, else ``None``.
    """

    if os.name != "nt":
        return None

    candidates = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Docker" / "Docker" / "Docker Desktop.exe",
        Path(os.environ.get("ProgramW6432", r"C:\Program Files")) / "Docker" / "Docker" / "Docker Desktop.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def probe_docker_daemon() -> tuple[bool, str | None]:
    """Check whether the local Docker daemon is reachable.

    Returns:
        Tuple of ``(reachable, detail)`` where ``detail`` contains failure output when unreachable.
    """

    assert_command_available("docker")
    try:
        result = run_command(
            ["docker", "info"],
            check=False,
            capture_output=True,
            text=True,
            timeout_seconds=SUPABASE_STATUS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return False, "docker info timed out while waiting for the Docker daemon."
    if result.returncode == 0:
        return True, None

    detail = ((result.stderr or "").strip() or (result.stdout or "").strip()) or None
    return False, detail


def ensure_docker_daemon_available() -> None:
    """Ensure the local Docker daemon is reachable before compose-dependent work.

    Returns:
        None.

    Raises:
        DevCliError: If Docker is unavailable or the daemon is not running.
    """

    reachable, detail = probe_docker_daemon()
    if reachable:
        return

    attempted_autostart = False
    docker_desktop_executable = find_docker_desktop_executable()
    if docker_desktop_executable is not None:
        attempted_autostart = True
        write_step("Starting Docker Desktop")
        try:
            subprocess.Popen(
                [str(docker_desktop_executable)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            attempted_autostart = False

        if attempted_autostart:
            write_step("Waiting for Docker daemon readiness (up to 90 seconds)")
            deadline = time.time() + 90
            while time.time() < deadline:
                reachable, detail = probe_docker_daemon()
                if reachable:
                    print("Docker daemon is ready.")
                    return
                time.sleep(3)

    if attempted_autostart:
        message = (
            "Docker daemon is not reachable. Docker Desktop was launched but did not become ready in time. "
            "Wait for Docker Desktop to finish starting, then retry."
        )
    else:
        message = "Docker daemon is not reachable. Start Docker Desktop (or the local Docker Engine) and retry."
    if detail:
        raise DevCliError(f"{message}\n{detail}")
    raise DevCliError(message)


def get_url_host_port(url: str) -> tuple[str, int]:
    """Resolve the host and port for a URL.

    Args:
        url: URL to inspect.

    Returns:
        Tuple of ``(host, port)``.

    Raises:
        DevCliError: If the URL omits a host or uses an unsupported scheme.
    """

    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").strip()
    if not host:
        raise DevCliError(f"URL does not include a host: {url}")

    if parsed.port is not None:
        return host, parsed.port

    scheme = parsed.scheme.lower()
    if scheme == "https":
        return host, 443
    if scheme == "http":
        return host, 80

    raise DevCliError(f"Unsupported URL scheme '{parsed.scheme}' for local port inspection: {url}")


def can_connect_to_tcp_port(*, host: str, port: int, timeout_seconds: float = 0.5) -> bool:
    """Return whether a TCP listener accepts connections at the host and port.

    Args:
        host: Host name or IP address to probe.
        port: TCP port to probe.
        timeout_seconds: Socket connect timeout.

    Returns:
        ``True`` when a listener accepts the connection, else ``False``.
    """

    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return True
    except OSError:
        return False


def get_local_listening_pids(*, port: int) -> list[int]:
    """Return process IDs currently listening on the supplied TCP port.

    Args:
        port: TCP port number to inspect.

    Returns:
        List of unique process IDs bound in LISTEN state.
    """

    if os.name == "nt":
        result = run_command(["netstat", "-ano", "-p", "tcp"], check=False, capture_output=True, text=True)
        pids: set[int] = set()
        for line in (result.stdout or "").splitlines():
            columns = line.split()
            if len(columns) < 5:
                continue
            protocol, local_address, _foreign_address, state, pid_text = columns[:5]
            if protocol.upper() != "TCP" or state.upper() != "LISTENING":
                continue
            if not local_address.endswith(f":{port}"):
                continue
            if pid_text.isdigit():
                pids.add(int(pid_text))
        return sorted(pids)

    lsof_path = shutil.which("lsof")
    if not lsof_path:
        return []

    result = run_command(
        [lsof_path, "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
        check=False,
        capture_output=True,
        text=True,
    )
    pids: set[int] = set()
    for line in (result.stdout or "").splitlines():
        value = line.strip()
        if value.isdigit():
            pids.add(int(value))
    return sorted(pids)


def clear_local_listener_port(*, url: str, description: str) -> None:
    """Terminate processes listening on a dedicated local development port.

    Args:
        url: Local URL whose port should be reclaimed.
        description: Human-readable service description for log output.

    Returns:
        None.
    """

    if not is_local_http_url(url):
        return

    host, port = get_url_host_port(url)
    if not can_connect_to_tcp_port(host=host, port=port):
        return

    stale_pids = get_local_listening_pids(port=port)
    if not stale_pids:
        return

    write_step(f"Stopping stale {description} listeners on port {port}")
    for pid in stale_pids:
        stop_process_by_pid(pid)


def ensure_local_url_port_available(*, url: str, description: str) -> None:
    """Ensure a local URL target port is not already occupied.

    Args:
        url: Local URL to inspect.
        description: Human-readable service description used in the failure message.

    Returns:
        None.

    Raises:
        DevCliError: If another local process is already listening on the URL port.
    """

    if not is_local_http_url(url):
        return

    host, port = get_url_host_port(url)
    if not can_connect_to_tcp_port(host=host, port=port):
        return

    raise DevCliError(
        f"Cannot start {description}: {url} is already in use by another local process. "
        f"Stop the existing process bound to port {port}, or reuse that existing instance instead."
    )


def ensure_tcp_port_bindable(*, host: str, port: int, description: str) -> None:
    """Ensure a host TCP port can be bound before delegating to Docker.

    Args:
        host: Host interface Docker will publish on.
        port: TCP port to test.
        description: Human-readable service description used in failure messages.

    Returns:
        None.

    Raises:
        DevCliError: If the host port cannot be bound locally.
    """

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host, port))
    except OSError as ex:
        detail = str(ex).strip() or ex.__class__.__name__
        raise DevCliError(
            f"Cannot start {description}: TCP port {port} on {host} is not available for binding ({detail})."
        ) from ex
    finally:
        sock.close()


def wait_for_background_process_http_ready(
    *,
    process: subprocess.Popen,
    url: str,
    description: str,
    log_path: Path | None = None,
    timeout_seconds: int = 90,
) -> None:
    """Wait until a spawned background process serves HTTP successfully.

    Args:
        process: Spawned background process expected to serve the URL.
        url: URL to poll for readiness.
        description: Human-readable service description for log output.
        log_path: Optional log file written by the background process.
        timeout_seconds: Maximum time to wait before failing.

    Returns:
        None.

    Raises:
        DevCliError: If the process exits before the URL becomes ready or the URL
            never becomes ready before timeout.
    """

    write_step(f"Waiting for {description} readiness (up to {timeout_seconds} seconds)")
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if process.poll() is not None:
            exit_code = process.returncode if process.returncode is not None else "unknown"
            log_excerpt = ""
            if log_path is not None and log_path.exists():
                log_excerpt = log_path.read_text(encoding="utf-8", errors="replace").strip()
                if len(log_excerpt) > 4000:
                    log_excerpt = log_excerpt[-4000:]

            message = (
                f"{description} exited before becoming ready (exit code {exit_code}). "
                f"Review log: {log_path or 'n/a'}"
            )
            if log_excerpt:
                message = f"{message}\nRecent log output:\n{log_excerpt}"
            raise DevCliError(message)

        reachable, _detail = probe_http_url(url)
        if reachable:
            print(f"{description} is ready.")
            return
        time.sleep(2)

    raise DevCliError(f"Timed out waiting for {description} readiness at {url}.")


def is_local_http_url(url: str) -> bool:
    """Return whether the URL targets a local loopback host.

    Args:
        url: URL to inspect.

    Returns:
        ``True`` when the URL host is local, else ``False``.
    """

    host = (urllib.parse.urlparse(url).hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "::1"}


def is_https_url(url: str) -> bool:
    """Return whether the URL uses HTTPS.

    Args:
        url: URL to inspect.

    Returns:
        ``True`` when the URL scheme is HTTPS, else ``False``.
    """

    return urllib.parse.urlparse(url).scheme.lower() == "https"


def get_curl_executable() -> str | None:
    """Return the preferred curl executable when available.

    Returns:
        Full path to ``curl``/``curl.exe`` when found, else ``None``.
    """

    return shutil.which("curl.exe") or shutil.which("curl")


def get_powershell_executable() -> str | None:
    """Return the preferred PowerShell executable when available.

    Returns:
        Full path to ``pwsh``/``powershell`` when found, else ``None``.
    """

    return shutil.which("pwsh.exe") or shutil.which("pwsh") or shutil.which("powershell.exe") or shutil.which("powershell")


def probe_http_url(url: str, *, timeout_seconds: int = 5) -> tuple[bool, str | None]:
    """Check whether an HTTP endpoint is reachable.

    Args:
        url: URL to probe.
        timeout_seconds: Request timeout in seconds.

    Returns:
        Tuple of ``(reachable, detail)`` where ``detail`` is a failure reason when unreachable.
    """

    request = urllib.request.Request(url, method="GET")
    context = None
    if is_local_http_url(url) and is_https_url(url):
        context = ssl._create_unverified_context()

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds, context=context):
            return True, None
    except urllib.error.HTTPError:
        return True, None
    except (
        ConnectionAbortedError,
        ConnectionError,
        OSError,
        http.client.RemoteDisconnected,
        urllib.error.URLError,
        TimeoutError,
    ) as ex:
        python_detail = str(ex)

    powershell_executable = get_powershell_executable()
    if powershell_executable and os.name == "nt" and is_local_http_url(url) and is_https_url(url):
        powershell_script = (
            "$ProgressPreference='SilentlyContinue'; "
            "try { "
            f"$response = Invoke-WebRequest -Uri '{url}' -Method Get -SkipCertificateCheck -HttpVersion 2.0 -MaximumRedirection 0 -TimeoutSec {timeout_seconds}; "
            "Write-Output $response.StatusCode; exit 0 "
            "} catch { "
            "if ($_.Exception.Response) { "
            "$statusCode = [int]$_.Exception.Response.StatusCode; "
            "if ($statusCode -gt 0) { Write-Output $statusCode; exit 0 } "
            "} "
            "Write-Error $_.Exception.Message; exit 1 "
            "}"
        )

        result = run_command(
            [powershell_executable, "-NoProfile", "-Command", powershell_script],
            check=False,
            capture_output=True,
            text=True,
        )
        status_text = (result.stdout or "").strip()
        if result.returncode == 0 and status_text.isdigit():
            status_code = int(status_text)
            if 200 <= status_code < 400:
                return True, None
            return False, f"HTTP {status_code}"

        detail = ((result.stderr or "").strip() or (result.stdout or "").strip())
        return False, detail or python_detail or f"PowerShell probe exited with code {result.returncode}"

    curl_executable = get_curl_executable()
    if curl_executable and is_local_http_url(url):
        curl_args = [
            curl_executable,
            "--silent",
            "--show-error",
            "--output",
            os.devnull,
            "--write-out",
            "%{http_code}",
            "--max-time",
            str(timeout_seconds),
        ]
        if is_https_url(url):
            curl_args.append("--http2")
            curl_args.append("--insecure")
        curl_args.append(url)

        result = run_command(curl_args, check=False, capture_output=True, text=True)
        status_text = (result.stdout or "").strip()
        if result.returncode == 0 and status_text.isdigit():
            status_code = int(status_text)
            if 200 <= status_code < 400:
                return True, None
            return False, f"HTTP {status_code}"

        detail = ((result.stderr or "").strip() or (result.stdout or "").strip())
        return False, detail or python_detail or f"curl exited with code {result.returncode}"

    return False, python_detail


def stop_background_process(process: subprocess.Popen) -> None:
    """Terminate a background process started by the developer CLI.

    Args:
        process: Process to stop.

    Returns:
        None.
    """

    if process.poll() is not None:
        return

    if os.name == "nt":
        run_command(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            capture_output=True,
            text=True,
        )
        return

    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def save_stack_state(config: DevConfig, *, stack_name: str, state: dict[str, object]) -> Path:
    """Persist locally launched stack process metadata.

    Args:
        config: CLI configuration containing the repository root.
        stack_name: Logical stack name used for the state file.
        state: Serializable process metadata to write.

    Returns:
        The written state file path.
    """

    state_path = get_stack_state_path(config, stack_name=stack_name)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state_path


def load_stack_state(config: DevConfig, *, stack_name: str) -> dict[str, object] | None:
    """Load a persisted stack state file if present and valid.

    Args:
        config: CLI configuration containing the repository root.
        stack_name: Logical stack name used for the state file.

    Returns:
        Parsed state mapping, or ``None`` when the file is absent.

    Raises:
        DevCliError: If the file exists but cannot be parsed.
    """

    state_path = get_stack_state_path(config, stack_name=stack_name)
    if not state_path.exists():
        return None

    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as ex:
        raise DevCliError(f"Stack state file is invalid JSON: {state_path}") from ex


def clear_stack_state(config: DevConfig, *, stack_name: str) -> None:
    """Delete a persisted stack state file when present.

    Args:
        config: CLI configuration containing the repository root.
        stack_name: Logical stack name used for the state file.

    Returns:
        None.
    """

    get_stack_state_path(config, stack_name=stack_name).unlink(missing_ok=True)


def save_deploy_state(config: DevConfig, *, target: str, state: dict[str, object]) -> Path:
    """Persist deployment stage state for an environment target."""

    state_path = get_deploy_state_path(config, target=target)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state_path


def load_deploy_state(config: DevConfig, *, target: str) -> dict[str, object] | None:
    """Load persisted deployment state for an environment target when present."""

    state_path = get_deploy_state_path(config, target=target)
    if not state_path.exists():
        return None

    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as ex:
        raise DevCliError(f"Deployment state file is invalid JSON: {state_path}") from ex

    if not isinstance(payload, dict):
        raise DevCliError(f"Deployment state file is invalid JSON: {state_path}")

    return payload


def clear_deploy_state(config: DevConfig, *, target: str) -> None:
    """Delete persisted deployment state for an environment target."""

    get_deploy_state_path(config, target=target).unlink(missing_ok=True)


def save_runtime_profile_state(config: DevConfig, *, profile: str) -> Path:
    """Persist the active local runtime profile."""

    state_path = get_runtime_profile_state_path(config)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"profile": profile}, indent=2), encoding="utf-8")
    return state_path


def load_runtime_profile_state(config: DevConfig) -> str | None:
    """Return the last known active local runtime profile when present."""

    state_path = get_runtime_profile_state_path(config)
    if not state_path.exists():
        return None

    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as ex:
        raise DevCliError(f"Runtime profile state file is invalid JSON: {state_path}") from ex

    profile = payload.get("profile")
    if isinstance(profile, str) and profile:
        return profile
    return None


def clear_runtime_profile_state(config: DevConfig) -> None:
    """Delete the persisted local runtime profile state when present."""

    get_runtime_profile_state_path(config).unlink(missing_ok=True)


def is_process_running(pid: int) -> bool:
    """Return whether the given process ID currently exists.

    Args:
        pid: Process ID to inspect.

    Returns:
        ``True`` when the process appears to be alive, else ``False``.
    """

    if pid <= 0:
        return False

    if os.name == "nt":
        try:
            result = run_command(
                ["tasklist", "/FI", f"PID eq {pid}"],
                check=False,
                capture_output=True,
                text=True,
                timeout_seconds=PROCESS_STATUS_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return False
        stdout = (result.stdout or "").lower()
        return result.returncode == 0 and f" {pid} " in f" {stdout} "

    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def stop_process_by_pid(pid: int) -> None:
    """Terminate a process by PID without requiring the original ``Popen`` handle.

    Args:
        pid: Process ID to stop.

    Returns:
        None.
    """

    if not is_process_running(pid):
        return

    if os.name == "nt":
        try:
            run_command(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                check=False,
                capture_output=True,
                text=True,
                timeout_seconds=PROCESS_STOP_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            raise DevCliError(
                "Timed out while stopping a tracked local process. "
                "The process record may be stale or Windows may still be reconciling the process tree. "
                "Rerun the command, or use 'python ./scripts/dev.py web clean' if the local web stack remains stuck."
            )
        return

    os.kill(pid, signal.SIGTERM)
    deadline = time.time() + 10
    while time.time() < deadline:
        if not is_process_running(pid):
            return
        time.sleep(0.5)
    os.kill(pid, signal.SIGKILL)


def start_background_command(
    *,
    cmd: Sequence[str],
    cwd: Path,
    log_path: Path,
    env: dict[str, str] | None = None,
) -> subprocess.Popen:
    """Start a background process and redirect combined output to a log file.

    Args:
        cmd: Command tokens to execute.
        cwd: Working directory for the process.
        log_path: Output log file path.
        env: Optional environment overrides.

    Returns:
        Background process handle.
    """

    resolved_cmd = list(cmd)
    executable = resolved_cmd[0]
    if os.path.dirname(executable) == "":
        resolved_executable = shutil.which(executable)
        if resolved_executable:
            resolved_cmd[0] = resolved_executable
        else:
            raise DevCliError(f"Required command '{executable}' was not found on PATH.")

    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_handle = log_path.open("w", encoding="utf-8")

    process = subprocess.Popen(
        resolved_cmd,
        cwd=str(cwd),
        stdin=subprocess.DEVNULL,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    log_handle.close()
    return process


def ensure_api_base_url_reachable(base_url: str) -> None:
    """Ensure the target API base URL is reachable before contract execution.

    Args:
        base_url: Runtime base URL used by the contract collection.

    Returns:
        None.

    Raises:
        DevCliError: If the base URL cannot be reached.
    """

    reachable, detail = probe_http_url(base_url)
    if reachable:
        return

    detail_suffix = f" ({detail})" if detail else ""
    if is_local_http_url(base_url):
        raise DevCliError(
            f"API base URL is not reachable: {base_url}{detail_suffix}\n"
            "Start the maintained backend in another terminal with 'python ./scripts/dev.py api' "
            "or rerun this command with '--start-workers'."
        )

    raise DevCliError(f"API base URL is not reachable: {base_url}{detail_suffix}")


def ensure_submodules(config: DevConfig) -> None:
    """Initialize maintained top-level submodules when needed.

    Args:
        config: CLI configuration containing the repository root.

    Returns:
        None.

    Raises:
        DevCliError: If Git is unavailable or submodule initialization fails.
    """

    assert_command_available("git")
    if all(test_submodule_initialized(path) for _, path in get_maintained_submodule_paths(config)):
        print("Submodules appear initialized.")
        reattach_maintained_submodule_heads(config)
        return

    write_step("Initializing submodules")
    run_command(["git", "submodule", "update", "--init", "--recursive"], cwd=config.repo_root)
    reattach_maintained_submodule_heads(config)


def restore_backend(config: DevConfig) -> None:
    """Prepare the maintained backend workspace dependencies.

    Args:
        config: CLI configuration containing workspace paths.

    Returns:
        None.

    Raises:
        DevCliError: If npm is unavailable or workspace install fails.
    """

    assert_command_available("npm")
    ensure_migration_workspace_scaffolding(config)
    install_migration_workspace_dependencies(config)


def stop_managed_stack_processes(config: DevConfig, *, stack_name: str) -> bool:
    """Stop any tracked managed application processes for the supplied stack."""

    state = load_stack_state(config, stack_name=stack_name)
    if state is None:
        return False

    for key, label in (
        ("frontend", "frontend web UI"),
        ("backend", "backend API"),
    ):
        entry = state.get(key)
        if not isinstance(entry, dict):
            continue

        pid = int(entry.get("pid", 0))
        if pid <= 0:
            continue

        if is_process_running(pid):
            write_step(f"Stopping {label}")
            stop_process_by_pid(pid)
        else:
            print(f"{label} is already stopped (PID {pid}).")

    clear_stack_state(config, stack_name=stack_name)
    return True


def stop_all_managed_application_processes(config: DevConfig) -> None:
    """Stop any tracked managed API/web application processes."""

    stop_managed_stack_processes(config, stack_name="web")
    stop_managed_stack_processes(config, stack_name="api")


def start_runtime_profile(config: DevConfig, *, profile: str) -> None:
    """Start the maintained local runtime for the supplied profile."""

    ensure_migration_workspace_scaffolding(config)
    ensure_docker_daemon_available()
    prefix = resolve_supabase_command_prefix()

    write_step(f"Starting local {SUPABASE_PROFILE_DESCRIPTIONS[profile]} runtime")
    run_command(
        build_supabase_profile_start_command(prefix=prefix, profile=profile),
        cwd=config.repo_root / config.supabase_root,
    )
    save_runtime_profile_state(config, profile=profile)


def restart_runtime_profile(config: DevConfig, *, profile: str) -> None:
    """Restart the maintained local runtime using the supplied profile."""

    stop_runtime_profile(config)
    start_runtime_profile(config, profile=profile)


def ensure_runtime_profile(config: DevConfig, *, profile: str) -> None:
    """Ensure the maintained local runtime matches the supplied profile."""

    active_profile = load_runtime_profile_state(config)
    reusable_profiles = {profile}
    if profile in (SUPABASE_PROFILE_API, SUPABASE_PROFILE_WEB):
        reusable_profiles = {SUPABASE_PROFILE_API, SUPABASE_PROFILE_WEB, None}

    if active_profile not in reusable_profiles:
        restart_runtime_profile(config, profile=profile)
        return

    write_step(f"Reusing local {SUPABASE_PROFILE_DESCRIPTIONS[profile]} runtime")
    stop_all_managed_application_processes(config)
    try:
        runtime_env = get_local_supabase_runtime(config)
        wait_for_local_supabase_http_ready(runtime_env=runtime_env)
    except DevCliError:
        print("Existing local runtime was unavailable; restarting local services.")
        restart_runtime_profile(config, profile=profile)
        return

    save_runtime_profile_state(config, profile=profile)


def stop_runtime_profile(config: DevConfig) -> None:
    """Stop the maintained local runtime profile and clear tracked process state."""

    stop_all_managed_application_processes(config)
    run_supabase_stack_command(config, action="stop")
    clear_runtime_profile_state(config)


def show_runtime_status(config: DevConfig, *, expected_profile: str | None = None) -> None:
    """Show the current maintained local runtime status."""

    active_profile = load_runtime_profile_state(config)
    if active_profile:
        print(f"Tracked runtime profile: {active_profile}")
    else:
        print("Tracked runtime profile: none")

    if expected_profile is not None and active_profile not in (None, expected_profile):
        print(f"Requested profile: {expected_profile}")

    run_supabase_stack_command(config, action="status")


def is_managed_service_running(config: DevConfig, *, stack_name: str, service_key: str) -> bool:
    """Return whether a tracked managed service process is currently running."""

    state = load_stack_state(config, stack_name=stack_name)
    if not isinstance(state, dict):
        return False

    entry = state.get(service_key)
    if not isinstance(entry, dict):
        return False

    pid = int(entry.get("pid", 0))
    return is_process_running(pid)


def print_frontend_service_status(config: DevConfig) -> None:
    """Print status for the maintained frontend service only."""

    state = load_stack_state(config, stack_name="web")
    if state is None:
        print("web: not running")
        return

    entry = state.get("frontend")
    if not isinstance(entry, dict):
        print("web: not running")
        return

    pid = int(entry.get("pid", 0))
    running = is_process_running(pid)
    print(f"web: {'running' if running else 'not running'}")
    if pid > 0:
        print(f"  pid: {pid}")
    url = entry.get("url")
    if isinstance(url, str) and url:
        print(f"  url: {url}")


def print_backend_service_status(config: DevConfig) -> None:
    """Print status for the maintained backend service only."""

    state = load_stack_state(config, stack_name="api")
    if state is None:
        print("api: not running")
        return

    entry = state.get("backend")
    if not isinstance(entry, dict):
        print("api: not running")
        return

    pid = int(entry.get("pid", 0))
    running = is_process_running(pid)
    print(f"api: {'running' if running else 'not running'}")
    if pid > 0:
        print(f"  pid: {pid}")
    url = entry.get("url")
    if isinstance(url, str) and url:
        print(f"  url: {url}")


def print_auth_service_status() -> None:
    """Print status for the local auth service only."""

    reachable, detail = probe_http_url(get_local_supabase_auth_url())
    detail_suffix = f" ({detail})" if detail else ""
    print(f"auth: {'running' if reachable else 'not running'}{detail_suffix}")


def print_database_service_status() -> None:
    """Print status for the local PostgreSQL service only."""

    resolved_db_port = get_local_supabase_db_port()
    running = can_connect_to_tcp_port(host=LOCAL_SUPABASE_DB_HOST, port=resolved_db_port)
    print(f"database: {'running' if running else 'not running'}")
    if running:
        print(f"  host: {LOCAL_SUPABASE_DB_HOST}")
        print(f"  port: {resolved_db_port}")


def stop_frontend_service(config: DevConfig) -> bool:
    """Stop the maintained frontend service only."""

    return stop_managed_stack_processes(config, stack_name="web")


def stop_backend_service(config: DevConfig) -> bool:
    """Stop the maintained backend service only."""

    return stop_managed_stack_processes(config, stack_name="api")


def run_full_local_web_stack(
    config: DevConfig,
    *,
    bootstrap: bool,
    install_dependencies: bool,
    hot_reload: bool,
    landing_mode: bool,
    open_browser_on_ready: bool,
) -> None:
    """Run the maintained local web stack together.

    Args:
        config: CLI configuration containing repository paths and defaults.
        bootstrap: Whether to initialize submodules before running.
        install_dependencies: Whether to install/update shared npm workspace dependencies before launch.
        hot_reload: Whether to run the frontend/backend through their watch-based local dev servers.
        landing_mode: Whether to start the SPA in landing-page-only mode.
        open_browser_on_ready: Whether to open the system browser when the frontend is reachable.
    Returns:
        None.

    Raises:
        DevCliError: If required tools are unavailable or any launched process exits unexpectedly.
    """

    backend_url = config.migration_workers_base_url
    frontend_url = config.migration_spa_base_url

    if bootstrap:
        ensure_submodules(config)

    assert_command_available("npm")
    ensure_migration_workspace_scaffolding(config)
    if install_dependencies:
        install_migration_workspace_dependencies(config)

    if hot_reload:
        print("Hot reload enabled via Vite and Wrangler dev mode.")
    if landing_mode:
        print("Landing mode enabled for the local SPA runtime.")

    ensure_runtime_profile(config, profile=SUPABASE_PROFILE_WEB)

    backend_process: subprocess.Popen | None = None
    frontend_process: subprocess.Popen | None = None
    backend_log_path: Path | None = None
    frontend_log_path: Path | None = None

    try:
        ensure_local_url_port_available(url=backend_url, description="backend API")
        ensure_local_url_port_available(url=frontend_url, description="frontend web UI")

        runtime_env = get_local_supabase_runtime(config)
        ensure_local_demo_seed_data(config, runtime_env=runtime_env)

        write_step("Starting maintained backend API in the background")
        backend_process, backend_log_path = start_migration_workers_process(config, runtime_env=runtime_env)
        print(f"Backend log: {backend_log_path}")
        write_step("Starting SPA in the background")
        frontend_process, frontend_log_path = start_background_command_with_log(
            cmd=build_workspace_npm_command(script_name="dev", workspace_name=config.migration_spa_workspace_name),
            cwd=config.repo_root,
            log_name="migration-spa.log",
            config=config,
            env=build_migration_frontend_environment(config, runtime_env=runtime_env, landing_mode=landing_mode),
        )
        print(f"Frontend log: {frontend_log_path}")
        wait_for_background_process_http_ready(
            process=frontend_process,
            url=frontend_url,
            description="SPA",
            log_path=frontend_log_path,
        )

        frontend_state: dict[str, object] = {
            "started_at_utc": datetime.now(timezone.utc).isoformat(),
            "frontend": {
                "pid": frontend_process.pid,
                "url": frontend_url,
                "log_path": str(frontend_log_path),
            },
        }
        backend_state: dict[str, object] = {
            "started_at_utc": datetime.now(timezone.utc).isoformat(),
            "backend": {
                "pid": backend_process.pid,
                "url": backend_url,
                "log_path": str(backend_log_path),
            },
        }

        api_state_path = save_stack_state(config, stack_name="api", state=backend_state)
        web_state_path = save_stack_state(config, stack_name="web", state=frontend_state)
        print(f"Backend API ready at {backend_url}", flush=True)
        print(f"Frontend web UI ready at {frontend_url}", flush=True)
        print(f"API stack state: {api_state_path}", flush=True)
        print(f"Web stack state: {web_state_path}", flush=True)

        if open_browser_on_ready:
            write_step(f"Opening browser to {frontend_url}")
            open_browser_in_background(frontend_url)

        print("Local web stack is running. Press Ctrl+C to stop backend and frontend.", flush=True)
        while True:
            time.sleep(2)

            if backend_process.poll() is not None:
                raise DevCliError(
                    f"Backend API exited unexpectedly. Review log: {backend_log_path}"
                )

            if frontend_process.poll() is not None:
                raise DevCliError(
                    f"Frontend web UI exited unexpectedly (exit code {frontend_process.returncode or 0}). "
                    f"Review log: {frontend_log_path}"
                )
    except KeyboardInterrupt:
        print("\nStopping local web stack.")
    finally:
        clear_stack_state(config, stack_name="web")
        clear_stack_state(config, stack_name="api")
        if frontend_process is not None:
            write_step("Stopping frontend web UI")
            stop_background_process(frontend_process)
        if backend_process is not None:
            write_step("Stopping backend API")
            stop_background_process(backend_process)
        run_supabase_stack_command(config, action="stop")
        clear_runtime_profile_state(config)


def run_local_api_stack(
    config: DevConfig,
    *,
    bootstrap: bool,
    install_dependencies: bool,
) -> None:
    """Run the maintained local API stack together."""

    backend_url = config.migration_workers_base_url

    if bootstrap:
        ensure_submodules(config)

    assert_command_available("npm")
    ensure_migration_workspace_scaffolding(config)
    if install_dependencies:
        install_migration_workspace_dependencies(config)

    ensure_runtime_profile(config, profile=SUPABASE_PROFILE_API)

    backend_process: subprocess.Popen | None = None
    backend_log_path: Path | None = None

    try:
        ensure_local_url_port_available(url=backend_url, description="backend API")
        runtime_env = get_local_supabase_runtime(config)
        ensure_local_demo_seed_data(config, runtime_env=runtime_env)

        write_step("Starting maintained backend API in the background")
        backend_process, backend_log_path = start_migration_workers_process(config, runtime_env=runtime_env)
        print(f"Backend log: {backend_log_path}")

        state: dict[str, object] = {
            "started_at_utc": datetime.now(timezone.utc).isoformat(),
            "backend": {
                "pid": backend_process.pid,
                "url": backend_url,
                "log_path": str(backend_log_path),
            },
        }
        state_path = save_stack_state(config, stack_name="api", state=state)
        print(f"API stack state: {state_path}")
        print("Local API stack is running. Press Ctrl+C to stop backend and local services.")

        while True:
            time.sleep(2)
            if backend_process.poll() is not None:
                raise DevCliError(f"Backend API exited unexpectedly. Review log: {backend_log_path}")
    except KeyboardInterrupt:
        print("\nStopping local API stack.")
    finally:
        clear_stack_state(config, stack_name="api")
        if backend_process is not None:
            write_step("Stopping backend API")
            stop_background_process(backend_process)
        run_supabase_stack_command(config, action="stop")
        clear_runtime_profile_state(config)


def show_database_command_status(config: DevConfig, *, include_dependencies: bool) -> None:
    """Show status for the database command."""

    del config, include_dependencies
    print_database_service_status()


def show_auth_command_status(config: DevConfig, *, include_dependencies: bool) -> None:
    """Show status for the auth command."""

    del config
    print_auth_service_status()
    if include_dependencies:
        print_database_service_status()


def show_api_command_status(config: DevConfig, *, include_dependencies: bool) -> None:
    """Show status for the api command."""

    print_backend_service_status(config)
    if include_dependencies:
        print_auth_service_status()
        print_database_service_status()


def show_web_command_status(config: DevConfig, *, include_dependencies: bool) -> None:
    """Show status for the web command."""

    print_frontend_service_status(config)
    if include_dependencies:
        print_backend_service_status(config)
        print_auth_service_status()
        print_database_service_status()


def handle_database_down(config: DevConfig, *, include_dependencies: bool) -> None:
    """Handle `database down`."""

    del include_dependencies
    stop_runtime_profile(config)
    print("Database runtime stopped.")


def handle_auth_down(config: DevConfig, *, include_dependencies: bool) -> None:
    """Handle `auth down`."""

    stop_frontend_service(config)
    stop_backend_service(config)
    if include_dependencies:
        stop_runtime_profile(config)
        print("Auth runtime and dependencies stopped.")
        return

    try:
        restart_runtime_profile(config, profile=SUPABASE_PROFILE_DATABASE)
    except DevCliError as ex:
        clear_runtime_profile_state(config)
        print("Auth runtime stopped.")
        print("Database availability could not be refreshed because the local Docker/Supabase runtime was not reachable.")
        print(str(ex))
        return

    print("Auth runtime stopped. Database remains available.")


def handle_api_down(config: DevConfig, *, include_dependencies: bool) -> None:
    """Handle `api down`."""

    stop_frontend_service(config)
    stop_backend_service(config)
    if include_dependencies:
        stop_runtime_profile(config)
        print("API runtime and dependencies stopped.")
        return

    try:
        restart_runtime_profile(config, profile=SUPABASE_PROFILE_AUTH)
    except DevCliError as ex:
        clear_runtime_profile_state(config)
        print("API runtime stopped.")
        print("Auth/database availability could not be refreshed because the local Docker/Supabase runtime was not reachable.")
        print(str(ex))
        return

    print("API runtime stopped. Auth and database remain available.")


def handle_web_down(config: DevConfig, *, include_dependencies: bool) -> None:
    """Handle `web down`."""

    stop_frontend_service(config)
    if include_dependencies:
        stop_backend_service(config)
        stop_runtime_profile(config)
        print("Web runtime and dependencies stopped.")
        return

    if is_managed_service_running(config, stack_name="api", service_key="backend"):
        save_runtime_profile_state(config, profile=SUPABASE_PROFILE_API)
    print("Web runtime stopped. API, auth, and database remain available.")


def summarize_removed_paths(paths: Sequence[Path], *, repo_root: Path) -> None:
    """Print a friendly summary of removed local artifacts.

    Args:
        paths: Paths removed during cleanup.
        repo_root: Repository root for relative display.

    Returns:
        None.
    """

    if not paths:
        print("No removable local files were found for this clean operation.")
        return

    print("Removed local files and directories:")
    for path in paths:
        try:
            display_path = path.relative_to(repo_root)
        except ValueError:
            display_path = path
        print(f"- {display_path}")


def clean_supabase_local_state(config: DevConfig) -> None:
    """Stop and remove local Supabase runtime state for a clean reset.

    Args:
        config: CLI configuration containing repository paths.

    Returns:
        None.
    """

    stop_runtime_profile(config)
    try:
        ensure_docker_daemon_available()
    except DevCliError:
        print("Docker daemon is not reachable; skipping direct Docker volume cleanup.")
        return

    removed_any = force_remove_supabase_project_containers(config)
    removed_any = force_remove_supabase_project_volumes(config) or removed_any
    if not removed_any:
        print("No lingering local Supabase containers or volumes were found.")


def run_clean_operation(
    config: DevConfig,
    *,
    command_name: str,
    summary_lines: Sequence[str],
    paths: Sequence[Path],
) -> None:
    """Run a confirmed destructive local cleanup for one runtime area.

    Args:
        config: CLI configuration containing repository paths.
        command_name: Runtime area being cleaned.
        summary_lines: Friendly prompt lines describing what will be removed.
        paths: Filesystem paths to remove after runtime shutdown.

    Returns:
        None.
    """

    if not confirm_clean_action(command_name=command_name, summary_lines=summary_lines):
        return

    perform_clean_operation(config, command_name=command_name, paths=paths)


def handle_database_clean(config: DevConfig) -> None:
    """Handle `database clean`."""

    run_clean_operation(
        config,
        command_name="database",
        summary_lines=(
            "Local Supabase runtime state, containers, and project volumes for this repository",
            "Supabase temp/branch folders created under backend/supabase",
            "Managed runtime state files and local service logs created by the CLI",
        ),
        paths=get_database_clean_paths(config),
    )


def handle_auth_clean(config: DevConfig) -> None:
    """Handle `auth clean`."""

    run_clean_operation(
        config,
        command_name="auth",
        summary_lines=(
            "Everything removed by `database clean`",
            "Local auth/profile runtime state created for the maintained stack",
            "Managed runtime logs created while auth-backed local services were running",
        ),
        paths=get_database_clean_paths(config),
    )


def handle_api_clean(config: DevConfig) -> None:
    """Handle `api clean`."""

    run_clean_operation(
        config,
        command_name="api",
        summary_lines=(
            "Everything removed by `auth clean`",
            "Backend-generated Wrangler dev files and local backend temp/cache folders",
            "Backend-only node_modules, dist outputs, tsbuildinfo files, and local logs",
        ),
        paths=get_api_clean_paths(config),
    )


def handle_web_clean(config: DevConfig) -> None:
    """Handle `web clean`."""

    run_clean_operation(
        config,
        command_name="web",
        summary_lines=(
            "Everything removed by `api clean`",
            "Root/frontend workspace installs and generated build/test artifacts",
            "Playwright auth snapshots, reports, and other local web automation outputs",
        ),
        paths=get_web_clean_paths(config),
    )


def handle_clean_all(config: DevConfig) -> None:
    """Handle `clean-all` by running each runtime cleanup from top to bottom.

    Args:
        config: CLI configuration containing repository paths.

    Returns:
        None.
    """

    summary_lines = (
        "Everything removed by `web clean`, `api clean`, `auth clean`, and `database clean`",
        "The clean steps run in this order: web, api, auth, database",
        "Repeated lower-level clean steps will no-op once the higher-level cleanup already removed their artifacts",
    )
    if not confirm_clean_action(command_name="clean-all", summary_lines=summary_lines):
        return

    ordered_cleanups = (
        ("web", get_web_clean_paths(config)),
        ("api", get_api_clean_paths(config)),
        ("auth", get_database_clean_paths(config)),
        ("database", get_database_clean_paths(config)),
    )
    for command_name, paths in ordered_cleanups:
        perform_clean_operation(config, command_name=command_name, paths=paths)
    print("`clean-all` completed.")


def perform_clean_operation(
    config: DevConfig,
    *,
    command_name: str,
    paths: Sequence[Path],
) -> None:
    """Perform the non-interactive portion of a clean operation.

    Args:
        config: CLI configuration containing repository paths.
        command_name: Runtime area being cleaned.
        paths: Filesystem paths to remove after runtime shutdown.

    Returns:
        None.
    """

    clean_supabase_local_state(config)
    removed_paths = remove_paths(paths)
    summarize_removed_paths(removed_paths, repo_root=config.repo_root)
    print(f"`{command_name} clean` completed.")


def start_background_command_with_log(
    *,
    cmd: Sequence[str],
    cwd: Path,
    log_name: str,
    config: DevConfig,
    env: dict[str, str] | None = None,
) -> tuple[subprocess.Popen, Path]:
    """Start a background command and return the process together with its log path.

    Args:
        cmd: Command tokens to execute.
        cwd: Working directory for the process.
        log_name: Log file name created under the shared CLI logs directory.
        config: CLI configuration containing the repository root.
        env: Optional environment overrides.

    Returns:
        Tuple of the launched process and the log path.
    """

    logs_dir = config.repo_root / ".dev-cli-logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / log_name
    process = start_background_command(cmd=cmd, cwd=cwd, log_path=log_path, env=env)
    return process, log_path


def run_tests(config: DevConfig, *, run_integration: bool, restore: bool = True) -> None:
    """Run maintained backend verification and optionally integration coverage.

    Args:
        config: CLI configuration containing backend workspace paths.
        run_integration: Whether to run backend integration coverage after typecheck.
        restore: Whether to install root npm workspace dependencies first.

    Returns:
        None.

    Raises:
        DevCliError: If required workspace commands fail.
    """
    assert_command_available("npm")
    ensure_migration_workspace_scaffolding(config)
    if restore:
        install_migration_workspace_dependencies(config)

    write_step("Running maintained backend typecheck")
    run_command(build_workspace_npm_command(script_name="typecheck", workspace_name=config.migration_workers_workspace_name), cwd=config.repo_root)

    if run_integration:
        run_workers_flow_smoke_command(
            config,
            start_stack=True,
            base_url=config.migration_workers_base_url,
            player_email=LOCAL_SEED_PLAYER_EMAIL,
            moderator_email=LOCAL_SEED_MODERATOR_EMAIL,
            developer_email=LOCAL_SEED_DEVELOPER_EMAIL,
            seed_password=LOCAL_SEED_DEFAULT_PASSWORD,
        )
    else:
        print("Skipping integration tests.")


def restore_frontend(config: DevConfig) -> None:
    """Ensure maintained frontend workspace dependencies are installed.

    Args:
        config: CLI configuration containing maintained frontend paths.

    Returns:
        None.
    """

    assert_command_available("npm")
    ensure_migration_workspace_scaffolding(config)
    install_migration_workspace_dependencies(config)


def run_frontend_tests(config: DevConfig, *, restore: bool = True) -> None:
    """Run maintained frontend tests.

    Args:
        config: CLI configuration containing maintained frontend paths.
        restore: Whether to install root npm workspace dependencies before running tests.

    Returns:
        None.
    """

    assert_command_available("npm")
    ensure_migration_workspace_scaffolding(config)
    if restore:
        install_migration_workspace_dependencies(config)

    write_step("Running frontend tests")
    run_command(build_workspace_npm_command(script_name="test", workspace_name=config.migration_spa_workspace_name), cwd=config.repo_root)


def run_migration_typecheck(config: DevConfig, *, restore: bool = True) -> None:
    """Run the maintained workspace-wide TypeScript typecheck.

    Args:
        config: CLI configuration containing the root workspace path.
        restore: Whether to install root npm workspace dependencies before running typecheck.

    Returns:
        None.
    """

    assert_command_available("npm")
    ensure_migration_workspace_scaffolding(config)
    if restore:
        install_migration_workspace_dependencies(config)

    write_step("Running maintained workspace typecheck")
    run_command(["npm", "run", "typecheck:migration"], cwd=config.repo_root)


def build_subprocess_env(*, extra: dict[str, str] | None = None) -> dict[str, str]:
    """Build a subprocess environment, optionally overlaying additional variables.

    Args:
        extra: Optional environment variable overrides/additions.

    Returns:
        Environment dictionary suitable for subprocess execution.
    """

    env = os.environ.copy()
    if extra:
        env.update({key: value for key, value in extra.items() if value is not None})
    return env


def build_migration_frontend_environment(
    config: DevConfig,
    *,
    runtime_env: dict[str, str],
    landing_mode: bool = False,
) -> dict[str, str]:
    """Build the Vite runtime environment for the maintained frontend workspace.

    Args:
        config: CLI configuration containing maintained local URLs.
        runtime_env: Local Supabase runtime values resolved from the CLI.
        landing_mode: Whether to force the SPA into landing-page-only mode.

    Returns:
        Environment mapping with the Vite runtime values injected.
    """

    return build_subprocess_env(
        extra={
            "VITE_APP_ENV": os.environ.get("BOARD_ENTHUSIASTS_APP_ENV", "local"),
            "VITE_API_BASE_URL": config.migration_workers_base_url,
            "VITE_SUPABASE_URL": runtime_env["SUPABASE_URL"],
            "VITE_SUPABASE_PUBLISHABLE_KEY": runtime_env["SUPABASE_PUBLISHABLE_KEY"],
            "VITE_SUPABASE_AUTH_DISCORD_ENABLED": get_frontend_oauth_enabled_value(os.environ, provider="discord"),
            "VITE_SUPABASE_AUTH_GITHUB_ENABLED": get_frontend_oauth_enabled_value(os.environ, provider="github"),
            "VITE_SUPABASE_AUTH_GOOGLE_ENABLED": get_frontend_oauth_enabled_value(os.environ, provider="google"),
            "VITE_TURNSTILE_SITE_KEY": os.environ.get("VITE_TURNSTILE_SITE_KEY", ""),
            "VITE_LANDING_MODE": "true" if landing_mode else os.environ.get("VITE_LANDING_MODE", ""),
        }
    )


def build_workspace_npm_command(*, script_name: str, workspace_name: str) -> list[str]:
    """Build an ``npm run`` command scoped to a single npm workspace.

    Args:
        script_name: Workspace script name to invoke.
        workspace_name: npm workspace package name.

    Returns:
        Command token list.
    """

    return ["npm", "run", script_name, "--workspace", workspace_name]


def build_workers_wrangler_command(*, action: str) -> list[str]:
    """Build the direct Wrangler command used for the maintained Workers runtime.

    Args:
        action: `dev`, `build`, or `deploy`.

    Returns:
        Command token list.

    Raises:
        DevCliError: If the requested action is unsupported.
    """

    base_command = ["npm", "exec", "--", "wrangler"]
    if action == "dev":
        return [
            *base_command,
            "dev",
            "--config",
            "wrangler.jsonc",
            "src/worker.ts",
            "--ip",
            "127.0.0.1",
            "--port",
            str(get_local_workers_port()),
        ]
    if action == "build":
        return [*base_command, "deploy", "--config", "wrangler.jsonc", "src/worker.ts", "--dry-run"]
    if action == "deploy":
        return [*base_command, "deploy", "--config", "wrangler.jsonc", "src/worker.ts"]

    raise DevCliError(f"Unsupported Workers Wrangler action: {action}")


def get_root_workspace_manifest_path(config: DevConfig) -> Path:
    """Return the root workspace package manifest path."""

    return config.repo_root / config.migration_root_package_json


def ensure_migration_workspace_scaffolding(config: DevConfig) -> None:
    """Ensure the maintained workspace files exist before running commands.

    Args:
        config: CLI configuration containing workspace paths.

    Returns:
        None.

    Raises:
        DevCliError: If required workspace files are missing.
    """

    required_paths = [
        ("root workspace package manifest", config.repo_root / config.migration_root_package_json),
        ("SPA workspace", config.repo_root / config.migration_spa_root),
        ("Workers workspace", config.repo_root / config.migration_workers_root),
        ("shared contract package", config.repo_root / config.migration_contract_root),
        ("Supabase project root", config.repo_root / config.supabase_root),
        ("local env example", config.repo_root / config.local_env_example),
        ("staging env example", config.repo_root / config.staging_env_example),
        ("production env example", config.repo_root / config.production_env_example),
        ("Cloudflare Pages template", config.repo_root / config.cloudflare_pages_template),
        ("Cloudflare Workers template", config.repo_root / config.cloudflare_workers_template),
        ("Cloudflare fallback Pages content root", config.repo_root / config.cloudflare_fallback_pages_root),
    ]

    missing = [f"{label}: {path}" for label, path in required_paths if not path.exists()]
    if missing:
        preview = "\n".join(missing)
        raise DevCliError(f"Workspace scaffolding is incomplete:\n{preview}")


def get_migration_workspace_install_state_path(config: DevConfig) -> Path:
    """Return the state file used to track the current npm workspace install.

    Args:
        config: CLI configuration containing the repository root.

    Returns:
        State file path under the shared CLI logs directory.
    """

    return config.repo_root / ".dev-cli-logs" / "migration-workspace-install.sha256"


def get_migration_workspace_install_fingerprint(config: DevConfig) -> str:
    """Build a fingerprint for the current root npm workspace dependency graph.

    Args:
        config: CLI configuration containing the repository root.

    Returns:
        SHA-256 fingerprint for the active dependency manifest/lock state.
    """

    manifest_path = get_root_workspace_manifest_path(config)
    lock_path = manifest_path.with_name("package-lock.json")
    fingerprint_source = lock_path if lock_path.exists() else manifest_path
    return hashlib.sha256(fingerprint_source.read_bytes()).hexdigest()


def has_current_migration_workspace_dependencies(config: DevConfig) -> bool:
    """Return whether the installed root npm workspace matches the current lock state.

    Args:
        config: CLI configuration containing the repository root.

    Returns:
        ``True`` when ``node_modules`` exists and the recorded install fingerprint
        matches the current dependency manifest state.
    """

    node_modules_path = config.repo_root / "node_modules"
    if not node_modules_path.exists():
        return False

    required_paths = (
        node_modules_path / "tsx" / "package.json",
        node_modules_path / "@supabase" / "supabase-js" / "package.json",
        node_modules_path / "@playwright" / "test" / "package.json",
        node_modules_path / "@board-enthusiasts" / "migration-contract" / "package.json",
        node_modules_path / "@board-enthusiasts" / "spa" / "package.json",
        node_modules_path / "@board-enthusiasts" / "workers-api" / "package.json",
    )
    if any(not path.exists() for path in required_paths):
        return False

    required_binaries = (
        (node_modules_path / ".bin" / "tsx").exists() or (node_modules_path / ".bin" / "tsx.cmd").exists(),
        (node_modules_path / ".bin" / "playwright").exists() or (node_modules_path / ".bin" / "playwright.cmd").exists(),
    )
    if not all(required_binaries):
        return False

    state_path = get_migration_workspace_install_state_path(config)
    if not state_path.exists():
        return False

    recorded_fingerprint = state_path.read_text(encoding="utf-8").strip()
    if not recorded_fingerprint:
        return False

    return recorded_fingerprint == get_migration_workspace_install_fingerprint(config)


def record_migration_workspace_dependencies(config: DevConfig) -> None:
    """Record the current npm workspace install fingerprint after a successful install.

    Args:
        config: CLI configuration containing the repository root.

    Returns:
        None.
    """

    state_path = get_migration_workspace_install_state_path(config)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(get_migration_workspace_install_fingerprint(config), encoding="utf-8")


def install_migration_workspace_dependencies(config: DevConfig) -> None:
    """Install root npm workspace dependencies for the maintained stack.

    Args:
        config: CLI configuration containing the repository root.

    Returns:
        None.
    """

    assert_command_available("npm")
    ensure_migration_workspace_scaffolding(config)
    if has_current_migration_workspace_dependencies(config):
        print("Workspace npm dependencies are already current.")
        return

    write_step("Installing workspace npm dependencies")
    run_command(["npm", "install"], cwd=config.repo_root)
    record_migration_workspace_dependencies(config)


def run_root_python_tests(config: DevConfig) -> None:
    """Run root-level Python unit tests for developer automation helpers.

    Args:
        config: CLI configuration containing the repository root.

    Returns:
        None.
    """

    assert_command_available("python")
    tests_root = config.repo_root / "tests" / "root_cli"
    if not tests_root.exists():
        print("No root Python tests were found.")
        return

    write_step("Running root Python tests")
    run_command(
        ["python", "-m", "unittest", "discover", "-s", str(tests_root), "-p", "test_*.py"],
        cwd=config.repo_root,
    )


def ensure_playwright_browser_installed(config: DevConfig) -> None:
    """Install the Chromium browser for Playwright-based parity tests.

    Args:
        config: CLI configuration containing the repository root.

    Returns:
        None.
    """

    assert_command_available("npx")
    write_step("Ensuring Playwright Chromium browser is installed")
    run_command(["npx", "playwright", "install", "chromium"], cwd=config.repo_root)


def resolve_supabase_command_prefix() -> list[str]:
    """Return the preferred command prefix for invoking the Supabase CLI.

    Returns:
        Command token prefix.

    Raises:
        DevCliError: If neither the standalone CLI nor ``npx`` is available.
    """

    if shutil.which("supabase") is not None:
        return ["supabase"]
    if shutil.which("npx") is not None:
        # Keep the fallback non-interactive so captured calls cannot block on the
        # npm install confirmation prompt when Supabase CLI is not installed globally.
        return ["npx", "--yes", "supabase"]
    raise DevCliError("Supabase CLI was not found. Install `supabase` or ensure `npx` is available.")


def open_browser_in_background(url: str) -> None:
    """Open a URL in the system browser without blocking the CLI main thread."""

    def _open() -> None:
        try:
            webbrowser.open(url)
        except Exception:
            return

    threading.Thread(
        target=_open,
        name="dev-cli-browser-open",
        daemon=True,
    ).start()


def build_supabase_profile_start_command(*, prefix: Sequence[str], profile: str) -> list[str]:
    """Build the Supabase CLI command used to start a specific local runtime profile."""

    if profile == SUPABASE_PROFILE_DATABASE:
        return [*prefix, "db", "start"]

    if profile not in SUPABASE_PROFILE_EXCLUDES:
        raise DevCliError(f"Unsupported Supabase runtime profile: {profile}")

    command = [*prefix, "start"]
    for service in SUPABASE_PROFILE_EXCLUDES[profile]:
        command.extend(["-x", service])
    return command


def parse_env_assignments(text: str) -> dict[str, str]:
    """Parse ``KEY=value`` lines into a dictionary.

    Args:
        text: Newline-delimited environment assignment text.

    Returns:
        Parsed environment mapping.
    """

    parsed: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        normalized_value = value.strip()
        if len(normalized_value) >= 2 and normalized_value[0] == normalized_value[-1] == '"':
            normalized_value = normalized_value[1:-1]
        parsed[key.strip()] = normalized_value
    return parsed


def get_supabase_status_env(config: DevConfig) -> dict[str, str]:
    """Return local Supabase runtime environment details from the CLI.

    Args:
        config: CLI configuration containing the Supabase project path.

    Returns:
        Parsed environment mapping emitted by ``supabase status -o env``.

    Raises:
        DevCliError: If Supabase is not running or status output is incomplete.
    """

    prefix = resolve_supabase_command_prefix()
    try:
        result = run_command(
            [*prefix, "status", "-o", "env"],
            cwd=config.repo_root / config.supabase_root,
            check=False,
            capture_output=True,
            timeout_seconds=SUPABASE_STATUS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as ex:
        raise DevCliError(
            "Supabase status command timed out while checking the local runtime. "
            "The local Docker/Supabase state may be partial; rerun "
            "'python ./scripts/dev.py database down' and then start the stack again."
        ) from ex
    if result.returncode != 0:
        output = "\n".join(
            part.strip()
            for part in ((result.stdout or ""), (result.stderr or ""))
            if part and part.strip()
        )
        if "No such container" in output or "failed to inspect container health" in output:
            raise DevCliError("Local Supabase services are not running. Start them with 'python ./scripts/dev.py database up'.")
        raise DevCliError("Supabase status command failed." + (f"\n{output}" if output else ""))

    parsed = parse_env_assignments(result.stdout or "")
    normalized = dict(parsed)
    if not normalized.get("API_URL"):
        normalized["API_URL"] = get_local_supabase_url()
    if not normalized.get("ANON_KEY") and normalized.get("PUBLISHABLE_KEY"):
        normalized["ANON_KEY"] = normalized["PUBLISHABLE_KEY"]

    required = ("API_URL", "ANON_KEY", "SERVICE_ROLE_KEY")
    missing = [name for name in required if not normalized.get(name)]
    if missing:
        raise DevCliError(
            "Supabase status output did not include the expected runtime keys: "
            + ", ".join(missing)
        )
    return normalized


def get_local_supabase_runtime(config: DevConfig) -> dict[str, str]:
    """Build the normalized local Supabase runtime environment mapping.

    Args:
        config: CLI configuration containing the Supabase project path.

    Returns:
        Mapping containing the API URL plus publishable and secret keys.
    """

    attempts = 5
    last_error: DevCliError | None = None
    for attempt in range(1, attempts + 1):
        try:
            status_env = get_supabase_status_env(config)
            break
        except DevCliError as ex:
            last_error = ex
            if attempt < attempts and is_transient_local_supabase_runtime_error(ex):
                time.sleep(2)
                continue
            raise
    else:
        if last_error is not None:
            raise last_error
        raise DevCliError("Unable to determine the local Supabase runtime.")

    return {
        "SUPABASE_URL": status_env["API_URL"],
        "SUPABASE_PUBLISHABLE_KEY": status_env.get("PUBLISHABLE_KEY", status_env["ANON_KEY"]),
        "SUPABASE_SECRET_KEY": status_env["SERVICE_ROLE_KEY"],
        "SUPABASE_AVATARS_BUCKET": "avatars",
        "SUPABASE_CARD_IMAGES_BUCKET": "card-images",
        "SUPABASE_HERO_IMAGES_BUCKET": "hero-images",
        "SUPABASE_LOGO_IMAGES_BUCKET": "logo-images",
    }


def build_supabase_bearer_headers(*, api_key: str) -> dict[str, str]:
    """Build the standard Supabase API headers for a bearer-authenticated request.

    Args:
        api_key: Supabase publishable or secret API key.

    Returns:
        Header mapping suitable for admin/storage/rest API probes.
    """

    return {
        "apikey": api_key,
        "authorization": f"Bearer {api_key}",
        "accept": "application/json",
    }


def probe_http_endpoint(
    *,
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    timeout_seconds: int = 10,
) -> tuple[bool, str | None]:
    """Probe an HTTP endpoint and report whether it returned a success status.

    Args:
        url: Endpoint URL to probe.
        method: HTTP method to use.
        headers: Optional request headers.
        data: Optional request body.
        timeout_seconds: Request timeout in seconds.

    Returns:
        Tuple of ``(reachable, detail)`` where ``detail`` contains a failure
        description when the probe was unsuccessful.
    """

    request = urllib.request.Request(url, method=method, data=data, headers=headers or {})
    context = None
    if is_local_http_url(url) and is_https_url(url):
        context = ssl._create_unverified_context()

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds, context=context) as response:
            status_code = getattr(response, "status", 200)
            if 200 <= status_code < 400:
                return True, None
            return False, f"HTTP {status_code}"
    except urllib.error.HTTPError as ex:
        detail = ex.read().decode("utf-8", errors="replace").strip()
        message = f"HTTP {ex.code} {ex.reason}"
        if detail:
            message = f"{message}: {detail}"
        return False, message
    except (
        ConnectionAbortedError,
        ConnectionError,
        OSError,
        http.client.RemoteDisconnected,
        urllib.error.URLError,
        TimeoutError,
    ) as ex:
        return False, str(ex)


def wait_for_local_supabase_http_ready(
    *,
    runtime_env: dict[str, str],
    timeout_seconds: int = 180,
) -> None:
    """Wait until the core local Supabase REST and storage endpoints are ready.

    Args:
        runtime_env: Resolved local Supabase runtime environment values.
        timeout_seconds: Maximum time to wait before failing.

    Returns:
        None.

    Raises:
        DevCliError: If the local Supabase HTTP surface does not become ready.
    """

    service_headers = build_supabase_bearer_headers(api_key=runtime_env["SUPABASE_SECRET_KEY"])
    base_url = runtime_env["SUPABASE_URL"].rstrip("/")
    checks = (
        (
            "Supabase Auth API",
            f"{base_url}/auth/v1/health",
            None,
        ),
        (
            "Supabase REST API",
            f"{base_url}/rest/v1/migration_wave_state?select=key&limit=1",
            service_headers,
        ),
        (
            "Supabase Storage API",
            f"{base_url}/storage/v1/bucket",
            service_headers,
        ),
    )

    write_step(f"Waiting for local Supabase HTTP readiness (up to {timeout_seconds} seconds)")
    deadline = time.time() + timeout_seconds
    last_failures: list[str] = []
    while time.time() < deadline:
        failures: list[str] = []
        for description, url, headers in checks:
            ready, detail = probe_http_endpoint(url=url, headers=headers)
            if not ready:
                failures.append(f"{description}: {detail or 'not ready'}")

        if not failures:
            print("Local Supabase HTTP services are ready.")
            return

        last_failures = failures
        time.sleep(2)

    detail = "; ".join(last_failures)
    raise DevCliError(
        "Timed out waiting for local Supabase HTTP services to become ready."
        + (f"\nLast probe failures: {detail}" if detail else "")
    )


def is_transient_supabase_seed_readiness_failure(error: DevCliError) -> bool:
    """Return whether a local seed failure looks like a transient Supabase restart issue."""

    message = str(error).lower()
    return (
        "timed out waiting for local supabase http services to become ready" in message
        and (
            "supabase storage api" in message
            or "invalid response was received from the upstream server" in message
            or "connection refused" in message
        )
    )


def is_local_supabase_not_running_error(error: DevCliError) -> bool:
    """Return whether a local seed failure indicates the Supabase stack is currently down."""

    return "local supabase services are not running" in str(error).lower()


def is_partial_local_supabase_runtime_error(error: DevCliError) -> bool:
    """Return whether a local Supabase runtime probe found only a partial service profile."""

    return "supabase status output did not include the expected runtime keys" in str(error).lower()


def is_transient_local_supabase_runtime_error(error: DevCliError) -> bool:
    """Return whether a local Supabase runtime probe looks temporarily incomplete during startup."""

    message = str(error).lower()
    return (
        is_partial_local_supabase_runtime_error(error)
        or (
            "supabase status command failed" in message
            and (
                "container is not ready: starting" in message
                or "failed to inspect container health" in message
                or "no such container" in message
            )
        )
    )


def has_local_demo_seed_data(*, runtime_env: dict[str, str]) -> bool:
    """Return whether the local Supabase stack already contains demo catalog data.

    Args:
        runtime_env: Resolved local Supabase runtime values.

    Returns:
        ``True`` when at least one catalog title row exists, else ``False``.

    Raises:
        DevCliError: If the local REST probe fails unexpectedly.
    """

    base_url = runtime_env["SUPABASE_URL"].rstrip("/")
    request = urllib.request.Request(
        f"{base_url}/rest/v1/titles?select=id&limit=1",
        headers=build_supabase_bearer_headers(api_key=runtime_env["SUPABASE_SECRET_KEY"]),
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8") or "[]")
    except urllib.error.HTTPError as ex:
        detail = ex.read().decode("utf-8", errors="replace").strip()
        message = f"Failed to probe local demo catalog seed state (HTTP {ex.code})."
        if detail:
            message = f"{message}\n{detail}"
        raise DevCliError(message) from ex
    except (OSError, urllib.error.URLError, TimeoutError) as ex:
        raise DevCliError(f"Failed to probe local demo catalog seed state.\n{ex}") from ex

    return isinstance(payload, list) and len(payload) > 0


def has_local_required_schema(runtime_env: dict[str, str]) -> bool:
    """Return whether required maintained local tables are present in PostgREST.

    Args:
        runtime_env: Resolved local Supabase runtime values.

    Returns:
        ``True`` when the required maintained tables can be queried, else ``False``.
    """

    required_tables = (
        "titles",
        "genres",
        "age_rating_authorities",
        "marketing_contacts",
        "catalog_media_type_definitions",
        "catalog_media_entries",
    )
    base_url = runtime_env["SUPABASE_URL"].rstrip("/")
    headers = build_supabase_bearer_headers(api_key=runtime_env["SUPABASE_SECRET_KEY"])

    for table_name in required_tables:
        request = urllib.request.Request(
            f"{base_url}/rest/v1/{table_name}?select=*&limit=1",
            headers=headers,
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=10):
                continue
        except urllib.error.HTTPError:
            return False
        except (OSError, urllib.error.URLError, TimeoutError) as ex:
            raise DevCliError(f"Failed to probe local schema readiness for '{table_name}'.\n{ex}") from ex

    return True


def apply_local_supabase_migrations(config: DevConfig) -> None:
    """Apply any outstanding checked-in migrations to the running local Supabase stack.

    Args:
        config: CLI configuration containing the Supabase project path.

    Returns:
        None.

    Raises:
        DevCliError: If the local migration application fails.
    """

    ensure_migration_workspace_scaffolding(config)
    ensure_docker_daemon_available()
    supabase_root = config.repo_root / config.supabase_root
    prefix = resolve_supabase_command_prefix()

    write_step("Applying outstanding local Supabase migrations")
    result = run_command(
        [*prefix, "migration", "up"],
        cwd=supabase_root,
        check=False,
        capture_output=True,
    )

    output = "\n".join(
        part.strip()
        for part in ((result.stdout or ""), (result.stderr or ""))
        if part and part.strip()
    )
    if result.returncode != 0:
        normalized_output = output.lower()
        if "cannot connect to the docker daemon" in normalized_output or "no such container" in normalized_output:
            raise DevCliError(
                "Local Supabase services are not running. Start them with 'python ./scripts/dev.py database up'."
            )
        raise DevCliError("Applying local Supabase migrations failed." + (f"\n{output}" if output else ""))

    if output:
        print_console_text(output)


def ensure_local_demo_seed_data(config: DevConfig, *, runtime_env: dict[str, str]) -> None:
    """Ensure the local Supabase stack contains deterministic demo data.

    Args:
        config: CLI configuration containing repository paths.
        runtime_env: Resolved local Supabase runtime values.

    Returns:
        None.
    """

    wait_for_local_supabase_http_ready(runtime_env=runtime_env)
    apply_local_supabase_migrations(config)
    wait_for_local_supabase_http_ready(runtime_env=runtime_env)
    if not has_local_required_schema(runtime_env):
        raise DevCliError(
            "Local runtime is still missing required maintained schema after applying checked-in migrations. "
            "Review the local Supabase migration state and rerun 'python ./scripts/dev.py web'. "
            "If you intentionally want a fresh local rebuild, run 'python ./scripts/dev.py seed-data --reset'."
        )

    if has_local_demo_seed_data(runtime_env=runtime_env):
        return

    write_step("Local runtime has no seeded catalog data; seeding deterministic demo fixtures")
    seed_migration_data(config, seed_password=LOCAL_SEED_DEFAULT_PASSWORD)


def get_workers_dev_vars_path(config: DevConfig) -> Path:
    """Return the local Wrangler dev vars file path for the Workers workspace."""

    return config.repo_root / config.migration_workers_root / ".dev.vars"


def write_workers_local_dev_vars(config: DevConfig, *, runtime_env: dict[str, str]) -> Path:
    """Write local Workers runtime bindings for Wrangler dev.

    Args:
        config: CLI configuration containing the Workers workspace path.
        runtime_env: Supabase runtime environment values.

    Returns:
        Path to the written ``.dev.vars`` file.
    """

    dev_vars_path = get_workers_dev_vars_path(config)
    lines = [
        "APP_ENV=local",
        f"SUPABASE_URL={runtime_env['SUPABASE_URL']}",
        f"SUPABASE_PUBLISHABLE_KEY={runtime_env['SUPABASE_PUBLISHABLE_KEY']}",
        f"SUPABASE_SECRET_KEY={runtime_env['SUPABASE_SECRET_KEY']}",
        f"SUPABASE_AVATARS_BUCKET={runtime_env['SUPABASE_AVATARS_BUCKET']}",
        f"SUPABASE_CARD_IMAGES_BUCKET={runtime_env['SUPABASE_CARD_IMAGES_BUCKET']}",
        f"SUPABASE_HERO_IMAGES_BUCKET={runtime_env['SUPABASE_HERO_IMAGES_BUCKET']}",
        f"SUPABASE_LOGO_IMAGES_BUCKET={runtime_env['SUPABASE_LOGO_IMAGES_BUCKET']}",
        "SUPPORT_REPORT_RECIPIENT=support@boardenthusiasts.com",
        "SUPPORT_REPORT_SENDER_EMAIL=noreply@boardenthusiasts.com",
        "SUPPORT_REPORT_SENDER_NAME=Board Enthusiasts",
        f"MAILPIT_BASE_URL={get_local_mailpit_url()}",
    ]
    dev_vars_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dev_vars_path


def get_supabase_project_id(config: DevConfig) -> str:
    """Return the configured local Supabase project identifier."""

    config_path = config.repo_root / config.supabase_root / "config.toml"
    if not config_path.exists():
        raise DevCliError(f"Supabase config was not found: {config_path}")

    match = re.search(r'^\s*project_id\s*=\s*"([^"]+)"\s*$', config_path.read_text(encoding="utf-8"), re.MULTILINE)
    if not match:
        raise DevCliError(f"Supabase config did not define project_id: {config_path}")
    return match.group(1)


def list_supabase_project_containers(config: DevConfig) -> list[tuple[str, str]]:
    """Return Docker container names and statuses for the local Supabase project."""

    project_id = get_supabase_project_id(config)
    result = run_command(
        ["docker", "ps", "-a", "--format", "{{.Names}}\t{{.Status}}"],
        cwd=config.repo_root,
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        output = "\n".join(
            part.strip()
            for part in ((result.stdout or ""), (result.stderr or ""))
            if part and part.strip()
        )
        raise DevCliError("Failed to inspect Docker containers for local Supabase state." + (f"\n{output}" if output else ""))

    containers: list[tuple[str, str]] = []
    for line in (result.stdout or "").splitlines():
        if "\t" not in line:
            continue
        name, status = line.split("\t", 1)
        normalized_name = name.strip()
        normalized_status = status.strip().lower()
        if not normalized_name.startswith("supabase_") or not normalized_name.endswith(project_id):
            continue
        containers.append((normalized_name, normalized_status))

    return containers


def remove_stale_supabase_project_containers(config: DevConfig) -> None:
    """Remove exited/created/dead Docker containers for the local Supabase project."""

    removable_names = [
        name
        for name, status in list_supabase_project_containers(config)
        if status.startswith(("exited", "created", "dead"))
    ]

    if not removable_names:
        return

    write_step("Removing stale local Supabase containers")
    run_command(["docker", "rm", "-f", *removable_names], cwd=config.repo_root)


def force_remove_supabase_project_containers(config: DevConfig) -> bool:
    """Force-remove all Docker containers for the local Supabase project."""

    removable_names = [name for name, _status in list_supabase_project_containers(config)]
    if not removable_names:
        return False

    write_step("Force-removing local Supabase containers")
    run_command(["docker", "rm", "-f", *removable_names], cwd=config.repo_root)
    return True


def list_supabase_project_volumes(config: DevConfig) -> list[str]:
    """Return Docker volume names associated with the local Supabase project.

    Args:
        config: CLI configuration containing repository paths.

    Returns:
        Matching Docker volume names.
    """

    project_id = get_supabase_project_id(config)
    result = run_command(
        [
            "docker",
            "volume",
            "ls",
            "--filter",
            f"label=com.docker.compose.project={project_id}",
            "--format",
            "{{.Name}}",
        ],
        cwd=config.repo_root,
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        output = "\n".join(
            part.strip()
            for part in ((result.stdout or ""), (result.stderr or ""))
            if part and part.strip()
        )
        raise DevCliError("Failed to inspect Docker volumes for local Supabase state." + (f"\n{output}" if output else ""))

    return [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]


def force_remove_supabase_project_volumes(config: DevConfig) -> bool:
    """Force-remove all Docker volumes for the local Supabase project.

    Args:
        config: CLI configuration containing repository paths.

    Returns:
        ``True`` when one or more volumes were removed; otherwise ``False``.
    """

    removable_names = list_supabase_project_volumes(config)
    if not removable_names:
        return False

    write_step("Force-removing local Supabase volumes")
    run_command(["docker", "volume", "rm", "-f", *removable_names], cwd=config.repo_root)
    return True


def run_supabase_stack_command(config: DevConfig, *, action: str, seed_password: str | None = None) -> None:
    """Run a Supabase local workflow command from the repository root.

    Args:
        config: CLI configuration containing the Supabase project path.
        action: Supported action name.
        seed_password: Optional password override used when reseeding after a local db reset.

    Returns:
        None.
    """

    ensure_migration_workspace_scaffolding(config)
    supabase_root = config.repo_root / config.supabase_root
    prefix = resolve_supabase_command_prefix()

    if action == "start":
        ensure_docker_daemon_available()
        ensure_tcp_port_bindable(
            host="0.0.0.0",
            port=get_local_supabase_db_port(),
            description="local Supabase database",
        )
        write_step("Starting local Supabase services")
        start_command = build_supabase_profile_start_command(
            prefix=prefix,
            profile=SUPABASE_PROFILE_WEB,
        )
        attempts = 3
        for attempt in range(1, attempts + 1):
            try:
                result = run_command(
                    start_command,
                    cwd=supabase_root,
                    check=False,
                    capture_output=True,
                    timeout_seconds=SUPABASE_START_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired as ex:
                print(
                    "Supabase start timed out after "
                    f"{SUPABASE_START_TIMEOUT_SECONDS} seconds; attempting to stop any partial local runtime."
                )
                try:
                    run_supabase_stack_command(config, action="stop")
                except DevCliError:
                    print("Automatic cleanup of the partial local runtime did not complete cleanly.")
                raise DevCliError(
                    "Supabase start timed out while launching the local runtime. "
                    "A partial local stack may have started (for example, the database without auth/gateway). "
                    "Rerun 'python ./scripts/dev.py database down' and try again. "
                    "If the problem continues, run 'python ./scripts/dev.py database clean' before retrying."
                ) from ex
            if result.returncode == 0:
                combined_output = "\n".join(
                    part.strip()
                    for part in ((result.stdout or ""), (result.stderr or ""))
                    if part and part.strip()
                )
                try:
                    runtime_env = get_local_supabase_runtime(config)
                    wait_for_local_supabase_http_ready(runtime_env=runtime_env)
                except DevCliError as ex:
                    if attempt < attempts and (
                        is_partial_local_supabase_runtime_error(ex)
                        or is_local_supabase_not_running_error(ex)
                        or is_transient_supabase_seed_readiness_failure(ex)
                    ):
                        print("Local Supabase services were only partially available; restarting the full local profile.")
                        run_supabase_stack_command(config, action="stop")
                        time.sleep(2)
                        continue
                    raise
                if combined_output:
                    print_console_text(combined_output)
                return

            output = "\n".join(
                part.strip()
                for part in ((result.stdout or ""), (result.stderr or ""))
                if part and part.strip()
            )
            if (
                "supabase start is already running." in output.lower()
                or "container is not ready: starting" in output.lower()
            ):
                runtime_env = get_local_supabase_runtime(config)
                wait_for_local_supabase_http_ready(runtime_env=runtime_env)
                if output:
                    print_console_text(output)
                return
            if "The container name " in output and "is already in use" in output and attempt < attempts:
                remove_stale_supabase_project_containers(config)
                print("Removed stale local Supabase containers. Retrying Supabase start.")
                continue
            if (
                ("a prune operation is already running" in output.lower() or "no such container:" in output.lower())
                and attempt < attempts
            ):
                print("Docker is still reconciling local Supabase containers; retrying Supabase start.")
                time.sleep(2)
                continue

            raise DevCliError("Supabase start failed." + (f"\n{output}" if output else ""))
        return

    if action == "stop":
        try:
            ensure_docker_daemon_available()
        except DevCliError:
            print("Docker daemon is not reachable; treating local Supabase services as already stopped.")
            return

        write_step("Stopping local Supabase services")
        attempts = 3
        for attempt in range(1, attempts + 1):
            try:
                result = run_command(
                    [*prefix, "stop"],
                    cwd=supabase_root,
                    check=False,
                    capture_output=True,
                    timeout_seconds=SUPABASE_STOP_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired:
                print(
                    "Supabase CLI stop timed out after "
                    f"{SUPABASE_STOP_TIMEOUT_SECONDS} seconds; forcing local container cleanup."
                )
                if force_remove_supabase_project_containers(config):
                    print("Forced local Supabase container cleanup completed.")
                    return
                print("No local Supabase containers were found. Treating services as stopped.")
                return

            if result.returncode == 0:
                return

            output = "\n".join(
                part.strip()
                for part in ((result.stdout or ""), (result.stderr or ""))
                if part and part.strip()
            )
            if "No such container" in output or "Cannot connect to the Docker daemon" in output:
                print("Local Supabase services are already stopped.")
                return

            if "a prune operation is already running" in output and attempt < attempts:
                print("Docker is still finishing a previous prune operation; retrying Supabase stop.")
                time.sleep(2)
                continue

            raise DevCliError("Supabase stop failed." + (f"\n{output}" if output else ""))
        return

    if action == "status":
        write_step("Showing local Supabase service status")
        try:
            result = run_command(
                [*prefix, "status", "-o", "env"],
                cwd=supabase_root,
                check=False,
                capture_output=True,
                timeout_seconds=SUPABASE_STATUS_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as ex:
            raise DevCliError(
                "Supabase status command timed out while checking local services. "
                "The local Docker/Supabase state may be partial; rerun "
                "'python ./scripts/dev.py database down' before starting again."
            ) from ex
        if result.returncode == 0:
            output = (result.stdout or "").strip()
            if output:
                print(output)
            return

        output = "\n".join(
            part.strip()
            for part in ((result.stdout or ""), (result.stderr or ""))
            if part and part.strip()
        )
        if "No such container" in output or "failed to inspect container health" in output:
            print("Local Supabase services are not running.")
            return
        raise DevCliError(
            "Supabase status command failed."
            + (f"\n{output}" if output else "")
        )
        return

    if action == "db-reset":
        ensure_docker_daemon_available()
        write_step("Resetting local Supabase database and reseeding")
        resolved_seed_password = seed_password or LOCAL_SEED_DEFAULT_PASSWORD
        attempts = 3
        for attempt in range(1, attempts + 1):
            result = run_command(
                [*prefix, "db", "reset", "--local"],
                cwd=supabase_root,
                check=False,
                capture_output=True,
            )
            if result.returncode == 0:
                try:
                    seed_migration_data(config, seed_password=resolved_seed_password)
                    return
                except DevCliError as ex:
                    if attempt < attempts and is_transient_supabase_seed_readiness_failure(ex):
                        print("Local Supabase services were still settling after reset; restarting services and retrying.")
                        run_supabase_stack_command(config, action="stop")
                        run_supabase_stack_command(config, action="start")
                        continue
                    raise

            output = "\n".join(
                part.strip()
                for part in ((result.stdout or ""), (result.stderr or ""))
                if part and part.strip()
            )
            normalized_output = output.lower()
            if (
                "failed to remove container" in normalized_output
                and "already in progress" in normalized_output
                and attempt < attempts
            ):
                print("Docker is still finishing a previous container removal; retrying Supabase db reset.")
                time.sleep(2)
                run_supabase_stack_command(config, action="start")
                continue

            if (
                "schema_migrations_pkey" in normalized_output
                and "duplicate key value violates unique constraint" in normalized_output
                and attempt < attempts
            ):
                print("Local Supabase migration state was inconsistent after reset; restarting services and retrying.")
                run_supabase_stack_command(config, action="stop")
                run_supabase_stack_command(config, action="start")
                continue

            if "Error status 502" in output:
                get_supabase_status_env(config)
                print("Supabase db reset completed with a transient 502 during service restart; continuing.")
            else:
                raise DevCliError("Supabase db reset failed." + (f"\n{output}" if output else ""))

            try:
                seed_migration_data(config, seed_password=resolved_seed_password)
                return
            except DevCliError as ex:
                if attempt < attempts and (
                    is_transient_supabase_seed_readiness_failure(ex)
                    or is_local_supabase_not_running_error(ex)
                ):
                    print("Local Supabase services were still settling after reset; restarting services and retrying.")
                    run_supabase_stack_command(config, action="stop")
                    run_supabase_stack_command(config, action="start")
                    continue
                raise
        raise DevCliError("Supabase db reset failed after multiple recovery attempts.")

    raise DevCliError(f"Unsupported Supabase action: {action}")


def seed_migration_data(config: DevConfig, *, seed_password: str, additive: bool = False) -> None:
    """Seed deterministic Supabase auth, data, and storage fixtures for the maintained stack.

    Args:
        config: CLI configuration containing workspace paths.
        seed_password: Password assigned to seeded local Supabase auth users.
        additive: Whether to preserve existing local data and only add missing maintained fixtures.

    Returns:
        None.
    """

    assert_command_available("npm")
    ensure_migration_workspace_scaffolding(config)
    install_migration_workspace_dependencies(config)
    try:
        runtime_env = get_local_supabase_runtime(config)
    except DevCliError as ex:
        if is_partial_local_supabase_runtime_error(ex) or is_local_supabase_not_running_error(ex):
            print("Local Supabase services were not fully available for seeding; restarting the full local profile.")
            run_supabase_stack_command(config, action="stop")
            run_supabase_stack_command(config, action="start")
            runtime_env = get_local_supabase_runtime(config)
        else:
            raise
    wait_for_local_supabase_http_ready(runtime_env=runtime_env)
    asset_root = (
        config.repo_root
        / "frontend"
        / "public"
        / "seed-catalog"
    ).resolve()
    if not asset_root.exists():
        raise DevCliError(f"Migration seed asset root was not found: {asset_root}")

    write_step("Seeding local Supabase auth, storage, and relational demo data")
    command = [
        "npm",
        "run",
        "seed:migration",
        "--",
    ]
    if additive:
        command.append("--additive")
    command.extend(
        [
            "--supabase-url",
            runtime_env["SUPABASE_URL"],
            "--secret-key",
            runtime_env["SUPABASE_SECRET_KEY"],
            "--password",
            seed_password,
            "--asset-root",
            str(asset_root),
            "--avatars-bucket",
            runtime_env["SUPABASE_AVATARS_BUCKET"],
            "--card-images-bucket",
            runtime_env["SUPABASE_CARD_IMAGES_BUCKET"],
            "--hero-images-bucket",
            runtime_env["SUPABASE_HERO_IMAGES_BUCKET"],
            "--logo-images-bucket",
            runtime_env["SUPABASE_LOGO_IMAGES_BUCKET"],
        ]
    )
    run_command(command, cwd=config.repo_root)


def fetch_supabase_access_token(*, supabase_url: str, publishable_key: str, email: str, password: str) -> str:
    """Exchange email/password credentials for a Supabase access token.

    Args:
        supabase_url: Supabase API base URL.
        publishable_key: Supabase publishable key.
        email: Seeded user email.
        password: Seeded user password.

    Returns:
        Access token string.
    """

    request = urllib.request.Request(
        f"{supabase_url.rstrip('/')}/auth/v1/token?grant_type=password",
        data=json.dumps({"email": email, "password": password}).encode("utf-8"),
        headers={
            "apikey": publishable_key,
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, context=ssl._create_unverified_context()) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as ex:
        detail = ex.read().decode("utf-8", errors="replace")
        raise DevCliError(
            f"Failed to fetch a Supabase access token for '{email}'.\n{detail}"
        ) from ex

    access_token = str(payload.get("access_token") or "").strip()
    if not access_token:
        raise DevCliError(f"Supabase auth response for '{email}' did not include an access token.")
    return access_token


def start_migration_workers_process(config: DevConfig, *, runtime_env: dict[str, str]) -> tuple[subprocess.Popen, Path]:
    """Start the local Workers API in the background.

    Args:
        config: CLI configuration containing workspace paths.
        runtime_env: Resolved local Supabase runtime environment values.

    Returns:
        Tuple of process handle and log path.
    """

    clear_local_listener_port(url=config.migration_workers_base_url, description="Workers API")
    ensure_local_url_port_available(url=config.migration_workers_base_url, description="Workers API")
    dev_vars_path = write_workers_local_dev_vars(config, runtime_env=runtime_env)
    print(f"Workers dev bindings file: {dev_vars_path}")
    command = build_workers_wrangler_command(action="dev")
    process, log_path = start_background_command_with_log(
        cmd=command,
        cwd=config.repo_root / config.migration_workers_root,
        log_name="workers-api.log",
        config=config,
    )
    wait_for_background_process_http_ready(
        process=process,
        url=f"{config.migration_workers_base_url.rstrip('/')}/health/ready",
        description="Workers API",
        log_path=log_path,
        timeout_seconds=120,
    )
    return process, log_path


def run_workers_smoke(
    config: DevConfig,
    *,
    base_url: str,
    player_token: str,
    moderator_token: str,
    developer_token: str,
) -> None:
    """Run the maintained Workers flow smoke suite.

    Args:
        config: CLI configuration containing repository paths.
        base_url: Target Workers API base URL.
        player_token: Bearer token for the seeded player user.
        moderator_token: Bearer token for the seeded moderator user.
        developer_token: Bearer token for the seeded developer user.

    Returns:
        None.
    """

    env = build_subprocess_env(
        extra={
            "WORKERS_SMOKE_BASE_URL": base_url,
            "WORKERS_SMOKE_PLAYER_TOKEN": player_token,
            "WORKERS_SMOKE_MODERATOR_TOKEN": moderator_token,
            "WORKERS_SMOKE_DEVELOPER_TOKEN": developer_token,
            "NODE_TLS_REJECT_UNAUTHORIZED": "0" if is_local_http_url(base_url) and is_https_url(base_url) else None,
        }
    )
    write_step("Running maintained Workers flow smoke suite")
    run_command(["npm", "run", "test:workers-smoke"], cwd=config.repo_root, env=env)


def run_workers_flow_smoke_command(
    config: DevConfig,
    *,
    start_stack: bool,
    base_url: str,
    player_email: str,
    moderator_email: str,
    developer_email: str,
    seed_password: str,
) -> None:
    """Run the maintained end-to-end Workers smoke suite.

    Args:
        config: CLI configuration containing repository paths.
        start_stack: Whether to start and seed the local Supabase + Workers stack.
        base_url: Target Workers API base URL.
        player_email: Seeded player account email.
        moderator_email: Seeded moderator account email.
        developer_email: Seeded developer account email.
        seed_password: Password assigned to seeded auth users.

    Returns:
        None.
    """

    ensure_migration_workspace_scaffolding(config)
    install_migration_workspace_dependencies(config)

    workers_process: subprocess.Popen | None = None
    resolved_base_url = base_url
    try:
        if start_stack:
            run_supabase_stack_command(config, action="start")
            run_supabase_stack_command(config, action="db-reset")
            runtime_env = get_local_supabase_runtime(config)
            resolved_base_url = config.migration_workers_base_url
            write_step("Starting Workers API in the background for Workers smoke")
            workers_process, workers_log_path = start_migration_workers_process(config, runtime_env=runtime_env)
            print(f"Workers API log: {workers_log_path}")
        else:
            ensure_api_base_url_reachable(resolved_base_url)
            runtime_env = get_local_supabase_runtime(config)

        player_token = fetch_supabase_access_token(
            supabase_url=runtime_env["SUPABASE_URL"],
            publishable_key=runtime_env["SUPABASE_PUBLISHABLE_KEY"],
            email=player_email,
            password=seed_password,
        )
        moderator_token = fetch_supabase_access_token(
            supabase_url=runtime_env["SUPABASE_URL"],
            publishable_key=runtime_env["SUPABASE_PUBLISHABLE_KEY"],
            email=moderator_email,
            password=seed_password,
        )
        developer_token = fetch_supabase_access_token(
            supabase_url=runtime_env["SUPABASE_URL"],
            publishable_key=runtime_env["SUPABASE_PUBLISHABLE_KEY"],
            email=developer_email,
            password=seed_password,
        )
        run_workers_smoke(
            config,
            base_url=resolved_base_url,
            player_token=player_token,
            moderator_token=moderator_token,
            developer_token=developer_token,
        )
    finally:
        if workers_process is not None:
            write_step("Stopping background Workers API")
            stop_background_process(workers_process)


def run_contract_smoke(
    config: DevConfig,
    *,
    base_url: str,
    start_workers: bool,
    token: str | None,
    player_token: str | None,
    moderator_token: str | None,
    developer_token: str | None,
    player_email: str | None,
    seed_user_email: str | None,
    moderator_email: str | None,
    seed_user_password: str | None,
) -> None:
    """Run the maintained API contract smoke harness.

    Args:
        config: CLI configuration containing workspace paths.
        base_url: Target API base URL.
        start_workers: Whether to start the Workers stack automatically.
        token: Optional bearer token for authenticated smoke checks.
        player_token: Optional player bearer token for role-specific smoke checks.
        moderator_token: Optional moderator bearer token for role-specific smoke checks.
        developer_token: Optional developer bearer token for role-specific smoke checks.
        player_email: Optional seeded player email used to fetch an auth token.
        seed_user_email: Optional seeded user email used to fetch an auth token.
        moderator_email: Optional seeded moderator email used to fetch an auth token.
        seed_user_password: Optional seeded user password used to fetch auth tokens.

    Returns:
        None.
    """

    assert_command_available("npm")
    ensure_migration_workspace_scaffolding(config)
    install_migration_workspace_dependencies(config)

    workers_process: subprocess.Popen | None = None
    runtime_env: dict[str, str] | None = None
    resolved_base_url = base_url
    resolved_token = token or ""
    resolved_player_token = player_token or ""
    resolved_moderator_token = moderator_token or ""
    resolved_developer_token = developer_token or ""

    if start_workers:
        if base_url != config.migration_workers_base_url and not is_local_http_url(base_url):
            raise DevCliError("--start-workers can only be used with the local Workers base URL.")
        run_supabase_stack_command(config, action="start")
        run_supabase_stack_command(config, action="db-reset")
        runtime_env = get_local_supabase_runtime(config)
        resolved_base_url = config.migration_workers_base_url
        write_step("Starting Workers API in the background for contract smoke")
        workers_process, workers_log_path = start_migration_workers_process(config, runtime_env=runtime_env)
        print(f"Workers API log: {workers_log_path}")
    else:
        ensure_api_base_url_reachable(resolved_base_url)

    if runtime_env is None and is_local_http_url(resolved_base_url):
        runtime_env = get_local_supabase_runtime(config)

    if runtime_env is not None:
        resolved_player_email = player_email or (LOCAL_SEED_PLAYER_EMAIL if start_workers else None)
        developer_email = seed_user_email or (LOCAL_SEED_DEVELOPER_EMAIL if start_workers else None)
        resolved_moderator_email = moderator_email or (LOCAL_SEED_MODERATOR_EMAIL if start_workers else None)
        seed_password = seed_user_password or LOCAL_SEED_DEFAULT_PASSWORD

        if resolved_player_email and not resolved_player_token:
            resolved_player_token = fetch_supabase_access_token(
                supabase_url=runtime_env["SUPABASE_URL"],
                publishable_key=runtime_env["SUPABASE_PUBLISHABLE_KEY"],
                email=resolved_player_email,
                password=seed_password,
            )

        if developer_email and not resolved_developer_token:
            resolved_developer_token = fetch_supabase_access_token(
                supabase_url=runtime_env["SUPABASE_URL"],
                publishable_key=runtime_env["SUPABASE_PUBLISHABLE_KEY"],
                email=developer_email,
                password=seed_password,
            )

        if resolved_moderator_email and not resolved_moderator_token:
            resolved_moderator_token = fetch_supabase_access_token(
                supabase_url=runtime_env["SUPABASE_URL"],
                publishable_key=runtime_env["SUPABASE_PUBLISHABLE_KEY"],
                email=resolved_moderator_email,
                password=seed_password,
            )

        if not resolved_token:
            resolved_token = resolved_player_token or resolved_developer_token or resolved_moderator_token

    env = build_subprocess_env(
        extra={
            "CONTRACT_SMOKE_BASE_URL": resolved_base_url,
            "CONTRACT_SMOKE_TOKEN": resolved_token,
            "CONTRACT_SMOKE_PLAYER_TOKEN": resolved_player_token or resolved_token,
            "CONTRACT_SMOKE_DEVELOPER_TOKEN": resolved_developer_token or resolved_token,
            "CONTRACT_SMOKE_MODERATOR_TOKEN": resolved_moderator_token or resolved_token,
            "NODE_TLS_REJECT_UNAUTHORIZED": "0" if is_local_http_url(resolved_base_url) and is_https_url(resolved_base_url) else None,
        }
    )

    try:
        write_step("Running maintained API contract smoke harness")
        run_command(["npm", "run", "test:contract-smoke"], cwd=config.repo_root, env=env)
    finally:
        if workers_process is not None:
            write_step("Stopping background Workers API")
            stop_background_process(workers_process)


def run_parity_suite(
    config: DevConfig,
    *,
    update_snapshots: bool,
) -> None:
    """Run the browser smoke and screenshot parity suite against the current app.

    Args:
        config: CLI configuration containing repository paths.
        update_snapshots: Whether to refresh committed screenshot baselines.

    Returns:
        None.
    """

    assert_command_available("npm")
    ensure_migration_workspace_scaffolding(config)
    install_migration_workspace_dependencies(config)
    ensure_playwright_browser_installed(config)
    startup_result = ensure_local_web_stack_for_parity(config)

    env = build_subprocess_env(
        extra={
            "PARITY_BASE_URL": config.frontend_base_url,
            "PARITY_ADMIN_EMAIL": LOCAL_SEED_MODERATOR_EMAIL,
            "PARITY_ADMIN_PASSWORD": LOCAL_SEED_DEFAULT_PASSWORD,
            "NODE_TLS_REJECT_UNAUTHORIZED": "0" if is_https_url(config.frontend_base_url) else None,
        }
    )
    command = ["npm", "run", "capture:parity-baseline" if update_snapshots else "test:parity"]
    try:
        write_step("Running parity browser baseline suite")
        run_command(command, cwd=config.repo_root, env=env)
    finally:
        cleanup_local_web_stack_after_parity(config, startup_result=startup_result)


def ensure_local_web_stack_for_parity(config: DevConfig) -> ParityStackStartupResult:
    """Ensure the maintained local web stack is reachable for parity tests.

    Args:
        config: CLI configuration containing repository paths and URLs.

    Returns:
        Summary of which local services parity started for temporary use.

    Raises:
        DevCliError: If the frontend still is not reachable after attempting startup.
    """

    frontend_ready, detail = probe_http_url(config.frontend_base_url)
    if frontend_ready:
        return ParityStackStartupResult()

    write_step("Frontend was not running; starting the maintained local web stack for parity")
    started_runtime = False
    try:
        runtime_env = get_local_supabase_runtime(config)
        wait_for_local_supabase_http_ready(runtime_env=runtime_env)
    except DevCliError:
        ensure_runtime_profile(config, profile=SUPABASE_PROFILE_WEB)
        runtime_env = get_local_supabase_runtime(config)
        wait_for_local_supabase_http_ready(runtime_env=runtime_env)
        started_runtime = True

    ensure_local_demo_seed_data(config, runtime_env=runtime_env)

    started_backend = False
    backend_ready, _backend_detail = probe_http_url(f"{config.migration_workers_base_url.rstrip('/')}/health/ready")
    if not backend_ready:
        write_step("Starting maintained backend API in the background for parity")
        backend_process, backend_log_path = start_migration_workers_process(config, runtime_env=runtime_env)
        print(f"Backend log: {backend_log_path}")
        save_stack_state(
            config,
            stack_name="api",
            state={
                "started_at_utc": datetime.now(timezone.utc).isoformat(),
                "backend": {
                    "pid": backend_process.pid,
                    "url": config.migration_workers_base_url,
                    "log_path": str(backend_log_path),
                },
            },
        )
        started_backend = True

    frontend_ready, _detail = probe_http_url(config.frontend_base_url)
    started_frontend = False
    if not frontend_ready:
        write_step("Starting SPA in the background for parity")
        frontend_process, frontend_log_path = start_background_command_with_log(
            cmd=build_workspace_npm_command(script_name="dev", workspace_name=config.migration_spa_workspace_name),
            cwd=config.repo_root,
            log_name="migration-spa.log",
            config=config,
            env=build_migration_frontend_environment(config, runtime_env=runtime_env, landing_mode=False),
        )
        print(f"Frontend log: {frontend_log_path}")
        wait_for_background_process_http_ready(
            process=frontend_process,
            url=config.frontend_base_url,
            description="SPA",
            log_path=frontend_log_path,
        )
        save_stack_state(
            config,
            stack_name="web",
            state={
                "started_at_utc": datetime.now(timezone.utc).isoformat(),
                "frontend": {
                    "pid": frontend_process.pid,
                    "url": config.frontend_base_url,
                    "log_path": str(frontend_log_path),
                },
            },
        )
        started_frontend = True

    frontend_ready, detail = probe_http_url(config.frontend_base_url)
    if not frontend_ready:
        raise DevCliError(
            f"Frontend base URL is not reachable: {config.frontend_base_url}"
            + (f" ({detail})" if detail else "")
        )
    return ParityStackStartupResult(
        started_runtime=started_runtime,
        started_backend=started_backend,
        started_frontend=started_frontend,
    )


def cleanup_local_web_stack_after_parity(
    config: DevConfig,
    *,
    startup_result: ParityStackStartupResult,
) -> None:
    """Stop only the local services parity started for itself.

    Args:
        config: CLI configuration containing repository paths and URLs.
        startup_result: Summary of which services parity launched.

    Returns:
        None.
    """

    if startup_result.started_runtime:
        write_step("Stopping parity-started local runtime")
        stop_runtime_profile(config)
        return

    if startup_result.started_frontend:
        write_step("Stopping parity-started SPA")
        stop_frontend_service(config)

    if startup_result.started_backend:
        write_step("Stopping parity-started backend API")
        stop_backend_service(config)


def get_deploy_pages_project_name(*, target: str) -> str:
    """Return the Cloudflare Pages project name for a deployment target."""

    return "board-enthusiasts-staging" if target == "staging" else "board-enthusiasts"


def get_deploy_worker_name(*, target: str) -> str:
    """Return the Cloudflare Worker script name for a deployment target."""

    return "board-enthusiasts-api-staging" if target == "staging" else "board-enthusiasts-api"


def get_worker_custom_domain_hostname(*, worker_base_url: str) -> str | None:
    """Return the Worker custom-domain hostname when the deploy target is not workers.dev."""

    parsed = urllib.parse.urlparse(worker_base_url)
    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        raise DevCliError(f"Worker base URL is not a valid URL: {worker_base_url}")
    if is_local_http_url(worker_base_url) or hostname.endswith(".workers.dev"):
        return None
    return hostname


def build_worker_custom_domain_routes(*, worker_base_url: str) -> list[dict[str, object]]:
    """Build Wrangler custom-domain routes for the hosted Worker deployment."""

    hostname = get_worker_custom_domain_hostname(worker_base_url=worker_base_url)
    if hostname is None:
        return []
    return [{"pattern": hostname, "custom_domain": True}]


def get_deploy_worker_config_path(config: DevConfig, *, target: str, env_values: dict[str, str]) -> Path:
    """Render a temporary wrangler config file for the target deployment environment."""

    template_path = config.repo_root / config.cloudflare_workers_template
    rendered_path = config.repo_root / ".dev-cli-logs" / f"wrangler-{target}.generated.jsonc"
    rendered_path.parent.mkdir(parents=True, exist_ok=True)
    worker_entry_path = config.repo_root / config.migration_workers_root / "src" / "worker.ts"
    worker_entry_relative_path = os.path.relpath(worker_entry_path, start=rendered_path.parent).replace("\\", "/")

    rendered = template_path.read_text(encoding="utf-8")
    rendered = re.sub(
        r'"name":\s*"[^"]+"',
        f'"name": "{get_deploy_worker_name(target=target)}"',
        rendered,
        count=1,
    )
    rendered = re.sub(
        r'"APP_ENV":\s*"[^"]+"',
        f'"APP_ENV": "{target}"',
        rendered,
        count=1,
    )
    rendered = re.sub(
        r'"dataset":\s*"board_enthusiasts_events_[^"]+"',
        f'"dataset": "board_enthusiasts_events_{target}"',
        rendered,
        count=1,
    )
    rendered = re.sub(
        r'"main":\s*"[^"]+"',
        f'"main": "{worker_entry_relative_path}"',
        rendered,
        count=1,
    )
    rendered = re.sub(
        r'"routes":\s*\[[^\]]*\]',
        f'"routes": {json.dumps(build_worker_custom_domain_routes(worker_base_url=env_values["BOARD_ENTHUSIASTS_WORKERS_BASE_URL"]))}',
        rendered,
        count=1,
        flags=re.DOTALL,
    )

    def replace_env_placeholder(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in env_values:
            raise DevCliError(
                f"Wrangler deploy template references environment value '{key}', but no deploy value was provided."
            )
        return json.dumps(env_values[key])

    rendered = re.sub(r'"env\(([A-Z0-9_]+)\)"', replace_env_placeholder, rendered)
    rendered_path.write_text(rendered, encoding="utf-8")
    return rendered_path


def build_deploy_frontend_environment(env_values: dict[str, str]) -> dict[str, str]:
    """Build the public frontend runtime environment for deployment builds."""

    resolved_app_env = env_values.get("BOARD_ENTHUSIASTS_APP_ENV", "").strip().lower()
    if not resolved_app_env:
        base_url = (
            env_values.get("BOARD_ENTHUSIASTS_SPA_BASE_URL", "").strip()
            or env_values.get("BOARD_ENTHUSIASTS_WORKERS_BASE_URL", "").strip()
        )
        hostname = urllib.parse.urlparse(base_url).hostname or ""
        if hostname in {"127.0.0.1", "localhost", "::1"}:
            resolved_app_env = "local"
        elif hostname.startswith("staging.") or ".staging." in hostname:
            resolved_app_env = "staging"
        else:
            resolved_app_env = "production"

    return build_subprocess_env(
        extra={
            "VITE_APP_ENV": resolved_app_env,
            "VITE_API_BASE_URL": env_values["BOARD_ENTHUSIASTS_WORKERS_BASE_URL"],
            "VITE_SUPABASE_URL": env_values["SUPABASE_URL"],
            "VITE_SUPABASE_PUBLISHABLE_KEY": env_values["SUPABASE_PUBLISHABLE_KEY"],
            "VITE_SUPABASE_AUTH_DISCORD_ENABLED": get_frontend_oauth_enabled_value(env_values, provider="discord"),
            "VITE_SUPABASE_AUTH_GITHUB_ENABLED": get_frontend_oauth_enabled_value(env_values, provider="github"),
            "VITE_SUPABASE_AUTH_GOOGLE_ENABLED": get_frontend_oauth_enabled_value(env_values, provider="google"),
            "VITE_TURNSTILE_SITE_KEY": env_values["VITE_TURNSTILE_SITE_KEY"],
            "VITE_LANDING_MODE": env_values["VITE_LANDING_MODE"],
        }
    )


def build_deploy_subprocess_environment(env_values: dict[str, str]) -> dict[str, str]:
    """Build the shared subprocess environment for hosted deployment commands."""

    return build_subprocess_env(
        extra={
            "SUPABASE_ACCESS_TOKEN": env_values["SUPABASE_ACCESS_TOKEN"],
            "SUPABASE_AUTH_DISCORD_CLIENT_ID": env_values.get("SUPABASE_AUTH_DISCORD_CLIENT_ID", ""),
            "SUPABASE_AUTH_DISCORD_CLIENT_SECRET": env_values.get("SUPABASE_AUTH_DISCORD_CLIENT_SECRET", ""),
            "SUPABASE_AUTH_GITHUB_CLIENT_ID": env_values.get("SUPABASE_AUTH_GITHUB_CLIENT_ID", ""),
            "SUPABASE_AUTH_GITHUB_CLIENT_SECRET": env_values.get("SUPABASE_AUTH_GITHUB_CLIENT_SECRET", ""),
            "SUPABASE_AUTH_GOOGLE_CLIENT_ID": env_values.get("SUPABASE_AUTH_GOOGLE_CLIENT_ID", ""),
            "SUPABASE_AUTH_GOOGLE_CLIENT_SECRET": env_values.get("SUPABASE_AUTH_GOOGLE_CLIENT_SECRET", ""),
            "CLOUDFLARE_API_TOKEN": env_values["CLOUDFLARE_API_TOKEN"],
            "CLOUDFLARE_ACCOUNT_ID": env_values["CLOUDFLARE_ACCOUNT_ID"],
        }
    )


def build_supabase_auth_redirect_urls(env_values: dict[str, str]) -> list[str]:
    """Build the hosted auth redirect URLs allowed for the current deploy target."""

    urls: list[str] = []

    def append_redirects(origin: str) -> None:
        normalized = origin.strip().rstrip("/")
        if not normalized:
            return

        parsed = urllib.parse.urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path not in {"", "/"}:
            return

        for candidate in (
            normalized,
            f"{normalized}/auth/signin",
            f"{normalized}/auth/signin?mode=recovery",
        ):
            if candidate not in urls:
                urls.append(candidate)

    append_redirects(env_values["BOARD_ENTHUSIASTS_SPA_BASE_URL"])
    for origin in env_values.get("ALLOWED_WEB_ORIGINS", "").split(","):
        append_redirects(origin)

    return urls


def render_supabase_deploy_config(config: DevConfig, *, env_values: dict[str, str]) -> str:
    """Render a target-specific Supabase config for hosted auth/provider deployment."""

    config_path = config.repo_root / config.supabase_root / "config.toml"
    if not config_path.exists():
        raise DevCliError(f"Supabase config was not found: {config_path}")

    rendered = config_path.read_text(encoding="utf-8")
    site_url = env_values["BOARD_ENTHUSIASTS_SPA_BASE_URL"].strip().rstrip("/")
    redirect_urls = build_supabase_auth_redirect_urls(env_values)
    redirect_block = "additional_redirect_urls = [\n" + "".join(f'  "{url}",\n' for url in redirect_urls) + "]"

    rendered, site_url_count = re.subn(
        r'(?m)^site_url = ".*"$',
        f'site_url = "{site_url}"',
        rendered,
        count=1,
    )
    if site_url_count != 1:
        raise DevCliError(f"Unable to render hosted Supabase site_url from {config_path}.")

    rendered, redirect_count = re.subn(
        r"(?ms)^additional_redirect_urls = \[[^\]]*\]",
        redirect_block,
        rendered,
        count=1,
    )
    if redirect_count != 1:
        raise DevCliError(f"Unable to render hosted Supabase additional_redirect_urls from {config_path}.")

    for provider in ("github", "discord", "google"):
        enabled_value = "true" if env_values.get(f"SUPABASE_AUTH_{provider.upper()}_CLIENT_ID", "").strip() else "false"
        rendered, provider_count = re.subn(
            rf"(\[auth\.external\.{provider}\]\s+enabled = )(?:true|false)",
            rf"\1{enabled_value}",
            rendered,
            count=1,
            flags=re.DOTALL,
        )
        if provider_count != 1:
            raise DevCliError(f"Unable to render hosted Supabase {provider} provider configuration from {config_path}.")

    return rendered


def get_git_repository_fingerprint(repo_root: Path) -> dict[str, object]:
    """Return a lightweight fingerprint of a Git worktree."""

    revision = run_command(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        capture_output=True,
    ).stdout.strip()
    status = run_command(
        ["git", "status", "--short"],
        cwd=repo_root,
        capture_output=True,
    ).stdout.strip()
    return {
        "revision": revision,
        "dirty": bool(status),
        "status_hash": hashlib.sha256(status.encode("utf-8")).hexdigest()[:16] if status else None,
    }


def build_deploy_fingerprint(
    config: DevConfig,
    *,
    target: str,
    source_branch: str,
    env_values: dict[str, str],
) -> str:
    """Build a deterministic fingerprint for the current deploy intent."""

    fingerprint_payload = {
        "target": target,
        "source_branch": source_branch,
        "root": get_git_repository_fingerprint(config.repo_root),
        "frontend": get_git_repository_fingerprint(config.repo_root / "frontend"),
        "backend": get_git_repository_fingerprint(config.repo_root / "backend"),
        "api": get_git_repository_fingerprint(config.repo_root / "api"),
        "env": {
            key: env_values[key]
            for key in (
                "BOARD_ENTHUSIASTS_SPA_BASE_URL",
                "BOARD_ENTHUSIASTS_WORKERS_BASE_URL",
                "SUPABASE_URL",
                "SUPABASE_PROJECT_REF",
                "SUPABASE_PUBLISHABLE_KEY",
                "SUPABASE_AVATARS_BUCKET",
                "SUPABASE_CARD_IMAGES_BUCKET",
                "SUPABASE_HERO_IMAGES_BUCKET",
                "SUPABASE_LOGO_IMAGES_BUCKET",
                "BREVO_SIGNUPS_LIST_ID",
                "ALLOWED_WEB_ORIGINS",
                "SUPPORT_REPORT_RECIPIENT",
                "SUPPORT_REPORT_SENDER_EMAIL",
                "SUPPORT_REPORT_SENDER_NAME",
                "VITE_LANDING_MODE",
            )
        },
        "secrets": {
            key: hashlib.sha256(env_values[key].encode("utf-8")).hexdigest()[:16]
            for key in DEPLOY_SECRET_ENV_NAMES
            if key in env_values
        },
    }
    return hashlib.sha256(json.dumps(fingerprint_payload, sort_keys=True).encode("utf-8")).hexdigest()


def request_json(
    *,
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    payload: dict[str, object] | list[object] | None = None,
    data: bytes | None = None,
    timeout_seconds: int = 15,
) -> object:
    """Issue an HTTP request and parse the JSON response."""

    request_data = data
    merged_headers = {"accept": "application/json", **(headers or {})}
    if payload is not None:
        request_data = json.dumps(payload).encode("utf-8")
        merged_headers.setdefault("content-type", "application/json")

    request = urllib.request.Request(url, method=method, headers=merged_headers, data=request_data)
    context = None
    if is_local_http_url(url) and is_https_url(url):
        context = ssl._create_unverified_context()

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds, context=context) as response:
            body = response.read().decode("utf-8", errors="replace").strip()
    except urllib.error.HTTPError as ex:
        detail = ex.read().decode("utf-8", errors="replace").strip()
        raise DevCliError(f"HTTP {ex.code} {ex.reason} for {url}: {detail or 'no detail'}") from ex
    except urllib.error.URLError as ex:
        raise DevCliError(f"Request failed for {url}: {ex.reason}") from ex
    except (TimeoutError, socket.timeout) as ex:
        raise DevCliError(
            f"Request timed out for {url} after {timeout_seconds} seconds. "
            "Check your network connection and verify the target service is reachable."
        ) from ex

    if not body:
        return {}

    try:
        return json.loads(body)
    except json.JSONDecodeError as ex:
        raise DevCliError(f"Expected JSON from {url} but received invalid content.") from ex


def collect_named_entries(payload: object) -> set[str]:
    """Collect every nested ``name`` field from a JSON payload."""

    discovered: set[str] = set()
    if isinstance(payload, dict):
        name = payload.get("name")
        if isinstance(name, str) and name.strip():
            discovered.add(name.strip())
        for value in payload.values():
            discovered.update(collect_named_entries(value))
    elif isinstance(payload, list):
        for entry in payload:
            discovered.update(collect_named_entries(entry))
    return discovered


def get_cloudflare_pages_projects(env_values: dict[str, str]) -> list[dict[str, object]]:
    """Return the accessible Cloudflare Pages projects for the authenticated account.

    This intentionally uses Cloudflare's direct API rather than Wrangler so deploy
    preflight can fail with a clearer account/token error before any publish stage
    begins.
    """

    request_url = (
        "https://api.cloudflare.com/client/v4/accounts/"
        f"{urllib.parse.quote(env_values['CLOUDFLARE_ACCOUNT_ID'])}/pages/projects"
    )
    last_error: DevCliError | None = None
    for attempt in range(2):
        try:
            payload = request_json(
                url=request_url,
                headers=build_cloudflare_api_headers(env_values),
                timeout_seconds=30,
            )
            return extract_cloudflare_result_list(payload, context="Pages project listing")
        except DevCliError as ex:
            last_error = ex
            if "timed out" in str(ex).lower() and attempt == 0:
                write_step("Cloudflare Pages listing timed out; retrying once")
                time.sleep(2)
                continue
            break

    assert last_error is not None
    ex = last_error
    if "timed out" in str(ex).lower():
        raise DevCliError(
            "Cloudflare Pages project listing timed out even after retrying. "
            "Confirm the Cloudflare API is reachable from this machine and retry. "
            "If this keeps happening in CI, verify the account id/token are correct and that the token has Pages read access.\n"
            f"Original error: {ex}"
        ) from ex
    raise DevCliError(
        "Cloudflare Pages project listing failed. "
        "Confirm the configured Cloudflare account id is correct and the API token includes Pages read access "
        "for that account.\n"
        f"Original error: {ex}"
    ) from ex


def get_cloudflare_pages_project(env_values: dict[str, str], *, project_name: str) -> dict[str, object] | None:
    """Return a Cloudflare Pages project by name when it exists."""

    try:
        payload = request_json(
            url=(
                "https://api.cloudflare.com/client/v4/accounts/"
                f"{urllib.parse.quote(env_values['CLOUDFLARE_ACCOUNT_ID'])}/pages/projects/"
                f"{urllib.parse.quote(project_name)}"
            ),
            headers=build_cloudflare_api_headers(env_values),
        )
    except DevCliError as ex:
        if "HTTP 404" in str(ex):
            return None
        raise DevCliError(
            "Cloudflare Pages project lookup failed. "
            "Ensure the API token includes Pages read access for the configured account.\n"
            f"Original error: {ex}"
        ) from ex

    if not isinstance(payload, dict):
        raise DevCliError(f"Cloudflare Pages project lookup for '{project_name}' returned an unexpected payload.")

    result = payload.get("result")
    if not isinstance(result, dict):
        raise DevCliError(f"Cloudflare Pages project lookup for '{project_name}' did not include a project result.")
    return result


def is_cloudflare_pages_project_already_exists_error(error: DevCliError) -> bool:
    """Return whether a Cloudflare Pages project create request failed because the project already exists."""

    message = str(error).lower()
    return "already exists" in message or "code\":8000002" in message or "code: 8000002" in message


def get_pages_custom_domain_hostname(*, spa_base_url: str) -> str | None:
    """Return the Pages custom-domain hostname when the deploy target is not pages.dev."""

    parsed = urllib.parse.urlparse(spa_base_url)
    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        raise DevCliError(f"SPA base URL is not a valid URL: {spa_base_url}")
    if is_local_http_url(spa_base_url) or hostname.endswith(".pages.dev"):
        return None
    return hostname


def build_cloudflare_api_headers(env_values: dict[str, str]) -> dict[str, str]:
    """Build the authenticated headers for direct Cloudflare API calls."""

    return {
        "Authorization": f"Bearer {env_values['CLOUDFLARE_API_TOKEN']}",
        "Content-Type": "application/json",
    }


def extract_cloudflare_result_list(payload: object, *, context: str) -> list[dict[str, object]]:
    """Validate a Cloudflare API payload and return its ``result`` list."""

    if not isinstance(payload, dict):
        raise DevCliError(f"Cloudflare {context} returned an unexpected payload.")
    result = payload.get("result")
    if not isinstance(result, list):
        raise DevCliError(f"Cloudflare {context} did not include a result list.")
    return [entry for entry in result if isinstance(entry, dict)]


def get_cloudflare_pages_project_domains(env_values: dict[str, str], *, project_name: str) -> list[dict[str, object]]:
    """Return the configured custom domains for a Cloudflare Pages project."""

    payload = request_json(
        url=(
            "https://api.cloudflare.com/client/v4/accounts/"
            f"{urllib.parse.quote(env_values['CLOUDFLARE_ACCOUNT_ID'])}/pages/projects/"
            f"{urllib.parse.quote(project_name)}/domains"
        ),
        headers=build_cloudflare_api_headers(env_values),
    )
    return extract_cloudflare_result_list(payload, context=f"Pages domain lookup for {project_name}")


def iter_hostname_zone_candidates(hostname: str) -> list[str]:
    """Return candidate zone names from most specific to least specific."""

    parts = [part for part in hostname.split(".") if part]
    return [".".join(parts[index:]) for index in range(len(parts) - 1) if len(parts[index:]) >= 2]


def get_cloudflare_zone_for_hostname(env_values: dict[str, str], *, hostname: str) -> dict[str, object]:
    """Resolve the Cloudflare zone record that owns the provided hostname."""

    headers = build_cloudflare_api_headers(env_values)
    last_error: DevCliError | None = None
    for candidate in iter_hostname_zone_candidates(hostname):
        try:
            payload = request_json(
                url=(
                    "https://api.cloudflare.com/client/v4/zones"
                    f"?name={urllib.parse.quote(candidate)}"
                ),
                headers=headers,
            )
        except DevCliError as ex:
            last_error = ex
            continue

        zones = extract_cloudflare_result_list(payload, context=f"zone lookup for {candidate}")
        for zone in zones:
            zone_name = str(zone.get("name", "")).strip().lower()
            account = zone.get("account")
            account_id = str(account.get("id", "")).strip() if isinstance(account, dict) else ""
            if zone_name == candidate.lower() and account_id == env_values["CLOUDFLARE_ACCOUNT_ID"]:
                return zone

    if last_error is not None:
        raise DevCliError(
            "Cloudflare zone lookup failed while validating the Worker custom domain. "
            "Ensure the API token includes Zone read access for the configured account.\n"
            f"Original error: {last_error}"
        ) from last_error

    raise DevCliError(
        f"Unable to find a Cloudflare zone in account {env_values['CLOUDFLARE_ACCOUNT_ID']} for hostname '{hostname}'."
    )


def get_cloudflare_dns_records(env_values: dict[str, str], *, zone_id: str, hostname: str) -> list[dict[str, object]]:
    """Return the Cloudflare DNS records for an exact hostname within a zone."""

    try:
        payload = request_json(
            url=(
                f"https://api.cloudflare.com/client/v4/zones/{urllib.parse.quote(zone_id)}/dns_records"
                f"?name={urllib.parse.quote(hostname)}"
            ),
            headers=build_cloudflare_api_headers(env_values),
        )
    except DevCliError as ex:
        raise DevCliError(
            "Cloudflare DNS access failed while validating the custom domain. "
            "Ensure the API token includes Zone DNS read/edit access for the configured zone.\n"
            f"Original error: {ex}"
        ) from ex

    return extract_cloudflare_result_list(payload, context=f"DNS lookup for {hostname}")


def get_routing_dns_records(records: list[dict[str, object]], *, hostname: str) -> list[dict[str, object]]:
    """Return only address-routing DNS records for an exact hostname."""

    normalized_hostname = hostname.strip().lower()
    return [
        record
        for record in records
        if str(record.get("name", "")).strip().lower() == normalized_hostname
        and str(record.get("type", "")).strip().upper() in ROUTING_DNS_RECORD_TYPES
    ]


def is_cloudflare_managed_apex_pages_record(record: dict[str, object], *, hostname: str, zone_name: str) -> bool:
    """Return whether a record looks like the expected Cloudflare-managed apex Pages routing record."""

    normalized_hostname = hostname.strip().lower()
    normalized_zone_name = zone_name.strip().lower()
    if normalized_hostname != normalized_zone_name:
        return False

    record_type = str(record.get("type", "")).strip().upper()
    if record_type not in {"A", "AAAA"}:
        return False

    return bool(record.get("proxied", False))


def is_manageable_apex_pages_routing_record(record: dict[str, object], *, hostname: str, zone_name: str) -> bool:
    """Return whether a Pages deploy can safely replace this apex routing record."""

    normalized_hostname = hostname.strip().lower()
    normalized_zone_name = zone_name.strip().lower()
    if normalized_hostname != normalized_zone_name:
        return False

    record_type = str(record.get("type", "")).strip().upper()
    if record_type not in {"A", "AAAA", "CNAME"}:
        return False

    return bool(record.get("proxied", False))


def assert_worker_custom_domain_dns_prerequisites(env_values: dict[str, str]) -> None:
    """Fail early when a Worker custom-domain hostname is blocked by an existing DNS record."""

    worker_base_url = env_values["BOARD_ENTHUSIASTS_WORKERS_BASE_URL"]
    hostname = get_worker_custom_domain_hostname(worker_base_url=worker_base_url)
    if hostname is None:
        return

    reachable, _ = probe_http_endpoint(url=f"{worker_base_url.rstrip('/')}/")
    if reachable:
        return

    zone = get_cloudflare_zone_for_hostname(env_values, hostname=hostname)
    zone_id = str(zone.get("id", "")).strip()
    if not zone_id:
        raise DevCliError(f"Cloudflare zone lookup for '{hostname}' did not include an id.")

    records = get_cloudflare_dns_records(env_values, zone_id=zone_id, hostname=hostname)
    def is_cloudflare_managed_worker_record(record: dict[str, object]) -> bool:
        meta = record.get("meta")
        if not isinstance(meta, dict):
            return False
        origin_worker_id = str(meta.get("origin_worker_id", "")).strip()
        read_only = bool(meta.get("read_only", False))
        return bool(origin_worker_id) and read_only

    conflicting_records = [
        record
        for record in records
        if str(record.get("name", "")).strip().lower() == hostname.lower()
        and not is_cloudflare_managed_worker_record(record)
    ]
    if not conflicting_records:
        return

    record_types = sorted({str(record.get("type", "")).strip().upper() or "UNKNOWN" for record in conflicting_records})
    raise DevCliError(
        f"Cloudflare DNS already has record(s) for Worker custom domain '{hostname}' ({', '.join(record_types)}).\n"
        "Delete the existing DNS record in Cloudflare DNS before deploying. "
        "Worker custom domains manage the hostname automatically and cannot be attached while a standalone DNS record already exists."
    )


def build_cloudflare_pages_branch_alias_hostname(*, project_name: str, source_branch: str) -> str:
    """Build the Pages preview alias hostname for a source branch."""

    normalized_branch = re.sub(r"[^a-z0-9]", "-", source_branch.strip().lower())
    normalized_branch = re.sub(r"-{2,}", "-", normalized_branch).strip("-")
    if not normalized_branch:
        raise DevCliError(f"Unable to derive a Pages branch alias from source branch '{source_branch}'.")
    return f"{normalized_branch}.{project_name}.pages.dev"


def parse_cloudflare_pages_alias_hostname(output: str) -> str | None:
    """Extract the Pages deployment alias hostname from Wrangler output when present."""

    match = re.search(r"Deployment alias URL:\s+https://(?P<host>[a-z0-9.-]+\.pages\.dev)", output, re.IGNORECASE)
    if not match:
        return None
    return match.group("host").strip().lower()


def get_expected_cloudflare_pages_alias_hostname(*, project_name: str, source_branch: str) -> str:
    """Return the stable Pages alias hostname expected for a source branch."""

    normalized_branch = source_branch.strip().lower()
    if normalized_branch == "main":
        return f"{project_name}.pages.dev"
    return build_cloudflare_pages_branch_alias_hostname(project_name=project_name, source_branch=source_branch)


def assert_pages_custom_domain_dns_access(env_values: dict[str, str]) -> None:
    """Verify the token can inspect and later manage DNS for the Pages custom domain hostname."""

    hostname = get_pages_custom_domain_hostname(spa_base_url=env_values["BOARD_ENTHUSIASTS_SPA_BASE_URL"])
    if hostname is None:
        return

    zone = get_cloudflare_zone_for_hostname(env_values, hostname=hostname)
    zone_id = str(zone.get("id", "")).strip()
    if not zone_id:
        raise DevCliError(f"Cloudflare zone lookup for '{hostname}' did not include an id.")
    get_cloudflare_dns_records(env_values, zone_id=zone_id, hostname=hostname)


def ensure_cloudflare_pages_custom_domain(env_values: dict[str, str], *, target: str) -> None:
    """Ensure the SPA custom domain is attached to the target Pages project."""

    hostname = get_pages_custom_domain_hostname(spa_base_url=env_values["BOARD_ENTHUSIASTS_SPA_BASE_URL"])
    if hostname is None:
        return

    project_name = get_deploy_pages_project_name(target=target)
    domains = get_cloudflare_pages_project_domains(env_values, project_name=project_name)
    if any(str(domain.get("name", "")).strip().lower() == hostname for domain in domains):
        return

    write_step(f"Attaching Cloudflare Pages custom domain {hostname}")
    request_json(
        url=(
            "https://api.cloudflare.com/client/v4/accounts/"
            f"{urllib.parse.quote(env_values['CLOUDFLARE_ACCOUNT_ID'])}/pages/projects/"
            f"{urllib.parse.quote(project_name)}/domains"
        ),
        method="POST",
        headers=build_cloudflare_api_headers(env_values),
        payload={"name": hostname},
    )


def sync_cloudflare_pages_domain_dns(
    env_values: dict[str, str],
    *,
    target: str,
    alias_target: str,
) -> None:
    """Point the Pages custom domain DNS record at the current branch alias target."""

    hostname = get_pages_custom_domain_hostname(spa_base_url=env_values["BOARD_ENTHUSIASTS_SPA_BASE_URL"])
    if hostname is None:
        return

    zone = get_cloudflare_zone_for_hostname(env_values, hostname=hostname)
    zone_id = str(zone.get("id", "")).strip()
    if not zone_id:
        raise DevCliError(f"Cloudflare zone lookup for '{hostname}' did not include an id.")

    zone_name = str(zone.get("name", "")).strip()
    if not zone_name:
        raise DevCliError(f"Cloudflare zone lookup for '{hostname}' did not include a name.")

    records = get_routing_dns_records(
        get_cloudflare_dns_records(env_values, zone_id=zone_id, hostname=hostname),
        hostname=hostname,
    )

    if len(records) > 1:
        if all(is_manageable_apex_pages_routing_record(record, hostname=hostname, zone_name=zone_name) for record in records):
            for record in records:
                record_id = str(record.get("id", "")).strip()
                if not record_id:
                    raise DevCliError(f"Cloudflare DNS record for '{hostname}' did not include an id.")
                write_step(f"Deleting Cloudflare DNS record {hostname} ({str(record.get('type', '')).strip().upper() or 'UNKNOWN'})")
                request_json(
                    url=(
                        f"https://api.cloudflare.com/client/v4/zones/{urllib.parse.quote(zone_id)}/dns_records/"
                        f"{urllib.parse.quote(record_id)}"
                    ),
                    method="DELETE",
                    headers=build_cloudflare_api_headers(env_values),
                )
            records = []
        else:
            raise DevCliError(
                f"Cloudflare DNS has multiple records for '{hostname}'. Clean up the duplicate records before deploying again."
            )

    if records:
        record = records[0]
        record_type = str(record.get("type", "")).strip().upper()
        if is_cloudflare_managed_apex_pages_record(record, hostname=hostname, zone_name=zone_name):
            record_id = str(record.get("id", "")).strip()
            if not record_id:
                raise DevCliError(f"Cloudflare DNS record for '{hostname}' did not include an id.")
            write_step(f"Replacing Cloudflare apex routing record for Pages custom domain {hostname} -> {alias_target}")
            request_json(
                url=(
                    f"https://api.cloudflare.com/client/v4/zones/{urllib.parse.quote(zone_id)}/dns_records/"
                    f"{urllib.parse.quote(record_id)}"
                ),
                method="DELETE",
                headers=build_cloudflare_api_headers(env_values),
            )
            records = []
        elif record_type != "CNAME":
            raise DevCliError(
                f"Cloudflare DNS record '{hostname}' is type {record_type}, but Pages custom domains require a CNAME target. "
                "Replace the record with a proxied CNAME before deploying again."
            )
        else:
            current_target = str(record.get("content", "")).strip().lower()
            proxied = bool(record.get("proxied", False))
            if current_target == alias_target and proxied:
                return

            record_id = str(record.get("id", "")).strip()
            if not record_id:
                raise DevCliError(f"Cloudflare DNS record for '{hostname}' did not include an id.")

            write_step(f"Updating Cloudflare DNS for Pages custom domain {hostname} -> {alias_target}")
            request_json(
                url=(
                    f"https://api.cloudflare.com/client/v4/zones/{urllib.parse.quote(zone_id)}/dns_records/"
                    f"{urllib.parse.quote(record_id)}"
                ),
                method="PUT",
                headers=build_cloudflare_api_headers(env_values),
                payload={"type": "CNAME", "name": hostname, "content": alias_target, "proxied": True, "ttl": 1},
            )
            return

    write_step(f"Creating Cloudflare DNS for Pages custom domain {hostname} -> {alias_target}")
    request_json(
        url=f"https://api.cloudflare.com/client/v4/zones/{urllib.parse.quote(zone_id)}/dns_records",
        method="POST",
        headers=build_cloudflare_api_headers(env_values),
        payload={"type": "CNAME", "name": hostname, "content": alias_target, "proxied": True, "ttl": 1},
    )


def ensure_cloudflare_pages_project(config: DevConfig, *, target: str, env: dict[str, str]) -> None:
    """Ensure the Cloudflare Pages project exists for the target environment."""

    project_name = get_deploy_pages_project_name(target=target)
    ensure_named_cloudflare_pages_project(env, project_name=project_name)


def ensure_named_cloudflare_pages_project(
    env: dict[str, str],
    *,
    project_name: str,
    production_branch: str = "main",
) -> None:
    """Ensure a named Cloudflare Pages project exists."""

    if get_cloudflare_pages_project(env, project_name=project_name) is not None:
        return

    write_step(f"Creating Cloudflare Pages project {project_name}")
    try:
        request_json(
            url=(
                "https://api.cloudflare.com/client/v4/accounts/"
                f"{urllib.parse.quote(env['CLOUDFLARE_ACCOUNT_ID'])}/pages/projects"
            ),
            method="POST",
            headers=build_cloudflare_api_headers(env),
            payload={
                "name": project_name,
                "production_branch": production_branch,
            },
        )
    except DevCliError as ex:
        if is_cloudflare_pages_project_already_exists_error(ex):
            return
        raise


def assert_pages_custom_domain_prerequisites(env_values: dict[str, str]) -> None:
    """Verify the Pages custom-domain hostname can be managed for the current zone."""

    hostname = get_pages_custom_domain_hostname(spa_base_url=env_values["BOARD_ENTHUSIASTS_SPA_BASE_URL"])
    if hostname is None:
        return

    zone = get_cloudflare_zone_for_hostname(env_values, hostname=hostname)
    zone_id = str(zone.get("id", "")).strip()
    if not zone_id:
        raise DevCliError(f"Cloudflare zone lookup for '{hostname}' did not include an id.")
    zone_name = str(zone.get("name", "")).strip()
    if not zone_name:
        raise DevCliError(f"Cloudflare zone lookup for '{hostname}' did not include a name.")
    records = get_routing_dns_records(
        get_cloudflare_dns_records(env_values, zone_id=zone_id, hostname=hostname),
        hostname=hostname,
    )
    if len(records) > 1:
        if all(is_manageable_apex_pages_routing_record(record, hostname=hostname, zone_name=zone_name) for record in records):
            return
        raise DevCliError(
            f"Cloudflare DNS has multiple records for Pages custom domain '{hostname}'. "
            "Leave at most one record for this hostname before deploying."
        )
    if records:
        record_type = str(records[0].get("type", "")).strip().upper()
        if is_manageable_apex_pages_routing_record(records[0], hostname=hostname, zone_name=zone_name):
            return
        if record_type != "CNAME":
            raise DevCliError(
                f"Cloudflare DNS record '{hostname}' is type {record_type}, but the deploy flow manages Pages custom domains "
                "through a proxied CNAME target. Replace the existing record before deploying."
            )


def run_supabase_link(config: DevConfig, *, env_values: dict[str, str], subprocess_env: dict[str, str]) -> None:
    """Link the backend Supabase workspace to the hosted target project."""

    run_command(
        [
            "npx",
            "supabase",
            "link",
            "--yes",
            "--project-ref",
            env_values["SUPABASE_PROJECT_REF"],
            "--password",
            env_values["SUPABASE_DB_PASSWORD"],
            "--workdir",
            str(config.repo_root / "backend"),
        ],
        cwd=config.repo_root / "backend",
        env=subprocess_env,
    )


def run_supabase_remote_dry_run(config: DevConfig, *, subprocess_env: dict[str, str]) -> None:
    """Run a hosted Supabase schema dry-run against the linked project."""

    write_step("Running Supabase remote schema dry-run")
    run_command(
        [
            "npx",
            "supabase",
            "db",
            "push",
            "--linked",
            "--dry-run",
            "--workdir",
            str(config.repo_root / "backend"),
        ],
        cwd=config.repo_root / "backend",
        env=subprocess_env,
    )


def run_supabase_remote_push(config: DevConfig, *, subprocess_env: dict[str, str]) -> None:
    """Apply hosted Supabase migrations against the linked project."""

    write_step("Applying Supabase hosted migrations")
    run_command(
        [
            "npx",
            "supabase",
            "db",
            "push",
            "--linked",
            "--workdir",
            str(config.repo_root / "backend"),
        ],
        cwd=config.repo_root / "backend",
        env=subprocess_env,
    )


def run_supabase_remote_config_push(config: DevConfig, *, env_values: dict[str, str], subprocess_env: dict[str, str]) -> None:
    """Push the hosted Supabase auth/provider configuration for the current target."""

    write_step("Pushing Supabase hosted auth configuration")
    rendered_config = render_supabase_deploy_config(config, env_values=env_values)

    with tempfile.TemporaryDirectory(prefix="board-enthusiasts-supabase-config-") as temp_dir:
        temp_root = Path(temp_dir)
        shutil.copytree(config.repo_root / config.supabase_root, temp_root / "supabase")
        (temp_root / "supabase" / "config.toml").write_text(rendered_config, encoding="utf-8")

        run_command(
            [
                "npx",
                "supabase",
                "config",
                "push",
                "--project-ref",
                env_values["SUPABASE_PROJECT_REF"],
                "--workdir",
                str(temp_root),
                "--yes",
            ],
            cwd=temp_root,
            env=subprocess_env,
        )


def run_supabase_bucket_provisioning(config: DevConfig, *, env_values: dict[str, str], subprocess_env: dict[str, str]) -> None:
    """Provision hosted Supabase storage buckets without seeding demo data."""

    write_step("Provisioning hosted Supabase storage buckets")
    run_command(
        [
            "npm",
            "run",
            "seed:migration",
            "--",
            "--buckets-only",
            "--supabase-url",
            env_values["SUPABASE_URL"],
            "--secret-key",
            env_values["SUPABASE_SECRET_KEY"],
            "--avatars-bucket",
            env_values["SUPABASE_AVATARS_BUCKET"],
            "--card-images-bucket",
            env_values["SUPABASE_CARD_IMAGES_BUCKET"],
            "--hero-images-bucket",
            env_values["SUPABASE_HERO_IMAGES_BUCKET"],
            "--logo-images-bucket",
            env_values["SUPABASE_LOGO_IMAGES_BUCKET"],
        ],
        cwd=config.repo_root,
        env=subprocess_env,
    )


def run_supabase_hosted_demo_seeding(
    config: DevConfig,
    *,
    target: str,
    env_values: dict[str, str],
    subprocess_env: dict[str, str],
) -> None:
    """Seed additive hosted demo data for staging without overwriting existing rows."""

    if target != "staging":
        write_step(f"Skipping hosted demo seeding for {target}")
        return

    seed_password = env_values.get("DEPLOY_SMOKE_USER_PASSWORD", "").strip()
    if not seed_password:
        raise DevCliError("Hosted staging demo seeding requires DEPLOY_SMOKE_USER_PASSWORD.")
    seed_values = {**env_values, "DEPLOY_SMOKE_USER_PASSWORD": seed_password}

    asset_root = (config.repo_root / "frontend" / "public" / "seed-catalog").resolve()
    if not asset_root.exists():
        raise DevCliError(f"Migration seed asset root was not found: {asset_root}")

    write_step("Seeding hosted staging demo catalog and smoke users")
    run_command(
        [
            "npm",
            "run",
            "seed:migration",
            "--",
            "--additive",
            "--supabase-url",
            seed_values["SUPABASE_URL"],
            "--secret-key",
            seed_values["SUPABASE_SECRET_KEY"],
            "--password",
            seed_values["DEPLOY_SMOKE_USER_PASSWORD"],
            "--asset-root",
            str(asset_root),
            "--avatars-bucket",
            seed_values["SUPABASE_AVATARS_BUCKET"],
            "--card-images-bucket",
            seed_values["SUPABASE_CARD_IMAGES_BUCKET"],
            "--hero-images-bucket",
            seed_values["SUPABASE_HERO_IMAGES_BUCKET"],
            "--logo-images-bucket",
            seed_values["SUPABASE_LOGO_IMAGES_BUCKET"],
        ],
        cwd=config.repo_root,
        env=subprocess_env,
    )


def build_deploy_stage_state(
    *,
    target: str,
    fingerprint: str,
    completed_stages: Sequence[str],
) -> dict[str, object]:
    """Build the persisted deployment stage-state payload."""

    now = datetime.now(timezone.utc).isoformat()
    return {
        "target": target,
        "fingerprint": fingerprint,
        "completed_stages": list(completed_stages),
        "updated_at": now,
    }


def normalize_deploy_stage_state(
    config: DevConfig,
    *,
    target: str,
    fingerprint: str,
    force: bool,
    upgrade: bool,
) -> tuple[set[str], dict[str, object]]:
    """Resolve persisted deploy state and enforce force/upgrade semantics."""

    if force:
        clear_deploy_state(config, target=target)
        return set(), build_deploy_stage_state(target=target, fingerprint=fingerprint, completed_stages=[])

    existing_state = load_deploy_state(config, target=target)
    if not existing_state:
        return set(), build_deploy_stage_state(target=target, fingerprint=fingerprint, completed_stages=[])

    existing_fingerprint = str(existing_state.get("fingerprint", ""))
    existing_completed = existing_state.get("completed_stages")
    completed_stages = set(existing_completed) if isinstance(existing_completed, list) else set()
    if existing_fingerprint and existing_fingerprint != fingerprint:
        if not upgrade:
            raise DevCliError(
                f"Deployment state already exists for {target} from a different source fingerprint.\n"
                "Rerun with --upgrade to apply the new changes or --force to rerun every stage from scratch."
            )
        clear_deploy_state(config, target=target)
        return set(), build_deploy_stage_state(target=target, fingerprint=fingerprint, completed_stages=[])

    return completed_stages, build_deploy_stage_state(
        target=target,
        fingerprint=fingerprint,
        completed_stages=sorted(completed_stages),
    )


def update_deploy_stage_completion(
    config: DevConfig,
    *,
    target: str,
    fingerprint: str,
    completed_stages: set[str],
    stage_name: str,
) -> None:
    """Mark a deployment stage as completed in local state."""

    completed_stages.add(stage_name)
    save_deploy_state(
        config,
        target=target,
        state=build_deploy_stage_state(
            target=target,
            fingerprint=fingerprint,
            completed_stages=sorted(completed_stages),
        ),
    )


def get_deploy_stage_failure_guidance(*, stage_name: str, target: str) -> str:
    """Return guidance for a failed deployment stage."""

    stage_guidance = {
        "supabase_config": (
            "Hosted Supabase auth/provider configuration is rerun-safe.\n"
            "After fixing the missing credentials or redirect settings, rerun deploy to push the updated config."
        ),
        "supabase_schema": (
            "Hosted Supabase migrations are not automatically rolled back.\n"
            "If this stage failed after partially applying migrations, inspect the remote migration history in Supabase before rerunning."
        ),
        "supabase_storage": (
            "Bucket provisioning is idempotent and safe to leave in place.\n"
            "You can rerun deploy after fixing the underlying error."
        ),
        "supabase_demo_seed": (
            "Hosted staging demo seeding is additive and rerun-safe for the maintained fixtures.\n"
            "Fix the seed/auth issue, then rerun deploy; existing staging user data will be preserved."
        ),
        "pages_project": (
            "Cloudflare Pages project creation is safe to leave in place.\n"
            "No manual rollback is required before the next attempt."
        ),
        "workers_deploy": (
            "Worker secret sync and publish are rerun-safe, but there is no automatic rollback to the previous secret values.\n"
            f"If you need to back out immediately, redeploy the last known-good Worker for {target} after correcting the config."
        ),
        "pages_deploy": (
            "Cloudflare Pages deploys are not automatically rolled back.\n"
            f"If the live site is unhealthy, redeploy the last known-good Pages bundle for {target} after correcting the config."
        ),
    }
    return stage_guidance.get(stage_name, "Fix the failing stage and rerun the deploy command.")


def assert_supabase_publishable_access(env_values: dict[str, str]) -> None:
    """Verify the hosted Supabase publishable key can reach the public auth settings endpoint."""

    url = f"{env_values['SUPABASE_URL'].rstrip('/')}/auth/v1/settings"
    reachable, detail = probe_http_endpoint(
        url=url,
        headers={"apikey": env_values["SUPABASE_PUBLISHABLE_KEY"], "accept": "application/json"},
    )
    if not reachable:
        raise DevCliError(f"Supabase publishable key probe failed: {detail or url}")


def assert_supabase_secret_access(env_values: dict[str, str]) -> None:
    """Verify the hosted Supabase secret key can reach the admin auth API."""

    url = f"{env_values['SUPABASE_URL'].rstrip('/')}/auth/v1/admin/users?page=1&per_page=1"
    reachable, detail = probe_http_endpoint(
        url=url,
        headers=build_supabase_bearer_headers(api_key=env_values["SUPABASE_SECRET_KEY"]),
    )
    if not reachable:
        raise DevCliError(f"Supabase secret key probe failed: {detail or url}")


def assert_supabase_project_alignment(env_values: dict[str, str]) -> None:
    """Ensure the hosted Supabase URL points at the same project ref used for migrations."""

    configured_project_ref = env_values["SUPABASE_PROJECT_REF"].strip()
    supabase_url = env_values["SUPABASE_URL"].strip()
    url_project_ref = get_supabase_project_ref_from_url(supabase_url)
    write_step(
        "Supabase runtime target: "
        f"SUPABASE_PROJECT_REF={configured_project_ref}; "
        f"SUPABASE_URL={supabase_url}; "
        f"URL-derived project ref={url_project_ref or 'unavailable'}"
    )
    if not url_project_ref or url_project_ref == configured_project_ref:
        return

    raise DevCliError(
        "Supabase deploy environment mismatch detected.\n"
        f"SUPABASE_PROJECT_REF targets '{configured_project_ref}', but SUPABASE_URL points at '{url_project_ref}'.\n"
        "The deploy flow migrates the project selected by SUPABASE_PROJECT_REF, while the Worker runtime uses SUPABASE_URL.\n"
        "Update the environment so both values point at the same hosted Supabase project before retrying deploy."
    )


def assert_hosted_required_schema(env_values: dict[str, str]) -> None:
    """Verify the hosted Supabase project behind SUPABASE_URL exposes the maintained runtime schema."""

    required_tables = (
        "titles",
        "studios",
        "home_spotlight_entries",
        "home_offering_spotlight_entries",
        "analytics_event_types",
        "analytics_events",
        "developer_analytics_saved_views",
        "player_followed_studios",
        "be_home_presence_sessions",
        "be_home_device_identities",
        "title_detail_views",
        "title_get_clicks",
    )
    base_url = env_values["SUPABASE_URL"].rstrip("/")
    headers = build_supabase_bearer_headers(api_key=env_values["SUPABASE_SECRET_KEY"])
    failures: list[str] = []

    for table_name in required_tables:
        request = urllib.request.Request(
            f"{base_url}/rest/v1/{table_name}?select=*&limit=1",
            headers=headers,
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=15):
                continue
        except urllib.error.HTTPError as ex:
            detail = ex.read().decode("utf-8", errors="replace").strip()
            failures.append(f"{table_name}: HTTP {ex.code}{f' ({detail[:200]})' if detail else ''}")
        except (OSError, urllib.error.URLError, TimeoutError) as ex:
            failures.append(f"{table_name}: {ex}")

    if failures:
        raise DevCliError(
            "Hosted Supabase runtime schema verification failed after migration push.\n"
            f"Checked runtime URL: {base_url}\n"
            "The deploy flow may be migrating a different project than the Worker runtime uses, or the hosted Supabase origin may be unreachable.\n"
            "Verify SUPABASE_PROJECT_REF, SUPABASE_URL, and the remote migration history, then rerun deploy.\n"
            f"Failures:\n- " + "\n- ".join(failures)
        )


def assert_turnstile_secret_access(env_values: dict[str, str]) -> None:
    """Verify the configured Turnstile secret can reach siteverify without an invalid-secret response."""

    payload = urllib.parse.urlencode(
        {
            "secret": env_values["TURNSTILE_SECRET_KEY"],
            "response": "deploy-preflight-placeholder-token",
        }
    ).encode("utf-8")
    verification = request_json(
        url="https://challenges.cloudflare.com/turnstile/v0/siteverify",
        method="POST",
        headers={"content-type": "application/x-www-form-urlencoded"},
        data=payload,
    )
    if not isinstance(verification, dict):
        raise DevCliError("Turnstile siteverify returned an unexpected payload.")

    error_codes = verification.get("error-codes", [])
    if isinstance(error_codes, list) and any(code == "invalid-input-secret" for code in error_codes):
        raise DevCliError("Turnstile secret key was rejected by Cloudflare siteverify.")


def assert_brevo_configuration(env_values: dict[str, str]) -> None:
    """Verify Brevo access, list membership target, and required custom attributes."""

    headers = {
        "api-key": env_values["BREVO_API_KEY"],
        "accept": "application/json",
    }
    list_payload = request_json(
        url=f"https://api.brevo.com/v3/contacts/lists/{urllib.parse.quote(env_values['BREVO_SIGNUPS_LIST_ID'])}",
        headers=headers,
    )
    if not isinstance(list_payload, dict):
        raise DevCliError("Brevo list lookup returned an unexpected payload.")

    attribute_payload = request_json(
        url="https://api.brevo.com/v3/contacts/attributes",
        headers=headers,
    )
    available_attribute_names = collect_named_entries(attribute_payload)
    missing_attributes = [name for name in DEPLOY_BREVO_REQUIRED_ATTRIBUTES if name not in available_attribute_names]
    if missing_attributes:
        raise DevCliError(
            "Brevo is missing the required contact attributes:\n- " + "\n- ".join(missing_attributes)
        )


def run_deploy_preflight(config: DevConfig, *, target: str, env_values: dict[str, str], subprocess_env: dict[str, str]) -> None:
    """Run non-mutating provider and environment validation before deployment."""

    write_step(f"Running {target} deploy preflight")
    assert_github_environment_sync(config, target=target)
    get_cloudflare_pages_projects(env_values)
    assert_pages_custom_domain_prerequisites(env_values)
    assert_worker_custom_domain_dns_prerequisites(env_values)
    assert_supabase_publishable_access(env_values)
    assert_supabase_secret_access(env_values)
    assert_supabase_project_alignment(env_values)
    assert_turnstile_secret_access(env_values)
    assert_brevo_configuration(env_values)
    run_supabase_link(config, env_values=env_values, subprocess_env=subprocess_env)


def run_deploy_dry_run(config: DevConfig, *, target: str, env_values: dict[str, str], subprocess_env: dict[str, str]) -> None:
    """Run the full non-publishing deployment dry-run for the target environment."""

    write_step(f"Running {target} deploy dry-run")
    run_supabase_link(config, env_values=env_values, subprocess_env=subprocess_env)
    run_supabase_remote_dry_run(config, subprocess_env=subprocess_env)

    write_step("Building SPA for Cloudflare Pages")
    run_command(
        build_workspace_npm_command(script_name="build", workspace_name=config.migration_spa_workspace_name),
        cwd=config.repo_root,
        env=build_deploy_frontend_environment(env_values),
    )

    worker_config_path = get_deploy_worker_config_path(config, target=target, env_values=env_values)
    write_step("Dry-running Cloudflare Workers bundle")
    run_command(
        [
            "npx",
            "wrangler",
            "deploy",
            "--dry-run",
            "--config",
            str(worker_config_path),
        ],
        cwd=config.repo_root,
        env=subprocess_env,
    )


def run_legacy_staging_dry_run(
    config: DevConfig,
    *,
    pages_only: bool,
    workers_only: bool,
) -> None:
    """Run the legacy staging-only partial dry-run modes kept for submodule CI compatibility."""

    if pages_only == workers_only:
        raise DevCliError("Legacy staging dry run requires exactly one of --pages-only or --workers-only.")

    if pages_only:
        env_values = {
            **collect_present_environment_values(*OPTIONAL_DEPLOY_ENV_NAMES),
            **require_environment_values(
                *LEGACY_PAGES_DRY_RUN_REQUIRED_ENV_NAMES,
                context="Legacy Pages staging dry run",
            ),
        }
        write_step("Running legacy Pages staging dry run")
        write_step("Building SPA for Cloudflare Pages")
        run_command(
            build_workspace_npm_command(script_name="build", workspace_name=config.migration_spa_workspace_name),
            cwd=config.repo_root,
            env=build_deploy_frontend_environment(env_values),
        )
        return

    env_values = {
        **collect_present_environment_values(*OPTIONAL_DEPLOY_ENV_NAMES),
        **require_environment_values(
            *LEGACY_WORKERS_DRY_RUN_REQUIRED_ENV_NAMES,
            context="Legacy Workers staging dry run",
        ),
    }
    subprocess_env = build_subprocess_env(
        extra={
            "CLOUDFLARE_API_TOKEN": env_values["CLOUDFLARE_API_TOKEN"],
            "CLOUDFLARE_ACCOUNT_ID": env_values["CLOUDFLARE_ACCOUNT_ID"],
        }
    )
    worker_config_path = get_deploy_worker_config_path(config, target="staging", env_values=env_values)
    write_step("Running legacy Workers staging dry run")
    write_step("Dry-running Cloudflare Workers bundle")
    run_command(
        [
            "npx",
            "wrangler",
            "deploy",
            "--dry-run",
            "--config",
            str(worker_config_path),
        ],
        cwd=config.repo_root,
        env=subprocess_env,
    )


def sync_worker_secret(config: DevConfig, *, worker_config_path: Path, secret_name: str, secret_value: str, subprocess_env: dict[str, str]) -> None:
    """Sync a single Cloudflare Worker secret to the target script.

    Cloudflare's versioned Workers require the latest Worker version to already
    be deployed before ``wrangler secret put`` can mutate its secrets.
    """

    write_step(f"Syncing Cloudflare Worker secret {secret_name}")
    run_command(
        ["npx", "wrangler", "secret", "put", secret_name, "--config", str(worker_config_path)],
        cwd=config.repo_root,
        env=subprocess_env,
        input_data=secret_value,
    )


def run_pages_deploy(
    config: DevConfig,
    *,
    target: str,
    source_branch: str,
    subprocess_env: dict[str, str],
) -> str:
    """Deploy the built SPA bundle to Cloudflare Pages."""

    return run_named_pages_deploy(
        config,
        directory=config.repo_root / config.migration_spa_root / "dist",
        project_name=get_deploy_pages_project_name(target=target),
        source_branch=source_branch,
        subprocess_env=subprocess_env,
    )


def run_named_pages_deploy(
    config: DevConfig,
    *,
    directory: Path,
    project_name: str,
    source_branch: str,
    subprocess_env: dict[str, str],
) -> str:
    """Deploy a static directory to a named Cloudflare Pages project."""

    result = run_command(
        [
            "npx",
            "wrangler",
            "pages",
            "deploy",
            str(directory),
            "--project-name",
            project_name,
            "--branch",
            source_branch,
        ],
        cwd=config.repo_root,
        env=subprocess_env,
        capture_output=True,
    )
    if result.stdout:
        print_console_text(result.stdout.rstrip())
    if result.stderr:
        print_console_text(result.stderr.rstrip())

    alias_hostname = parse_cloudflare_pages_alias_hostname(f"{result.stdout or ''}\n{result.stderr or ''}")
    if not alias_hostname:
        alias_hostname = get_expected_cloudflare_pages_alias_hostname(
            project_name=project_name,
            source_branch=source_branch,
        )
    return alias_hostname


def deploy_fallback_pages(
    config: DevConfig,
    *,
    project_name: str,
    source_branch: str,
) -> str:
    """Deploy the standalone fallback/error pages bundle to Cloudflare Pages."""

    env_values = require_environment_values(
        "CLOUDFLARE_ACCOUNT_ID",
        "CLOUDFLARE_API_TOKEN",
        context="Cloudflare fallback Pages deploy",
    )
    subprocess_env = build_subprocess_env(
        extra={
            "CLOUDFLARE_API_TOKEN": env_values["CLOUDFLARE_API_TOKEN"],
            "CLOUDFLARE_ACCOUNT_ID": env_values["CLOUDFLARE_ACCOUNT_ID"],
        }
    )
    fallback_root = config.repo_root / config.cloudflare_fallback_pages_root

    write_step("Running Cloudflare fallback Pages preflight")
    get_cloudflare_pages_projects(env_values)
    ensure_named_cloudflare_pages_project(env_values, project_name=project_name)

    write_step(f"Deploying Cloudflare fallback Pages bundle for {project_name}")
    alias_hostname = run_named_pages_deploy(
        config,
        directory=fallback_root,
        project_name=project_name,
        source_branch=source_branch,
        subprocess_env=subprocess_env,
    )
    base_url = f"https://{alias_hostname}"

    print()
    print("Fallback Pages URLs")
    print(f"- Base page: {base_url}/")
    print(f"- Cloudflare 5xx page: {base_url}/cloudflare/5xx.html")
    print(f"- Cloudflare 1xxx page: {base_url}/cloudflare/1xxx.html")
    if source_branch.strip().lower() == "main":
        print(f"- Production alias: https://{project_name}.pages.dev/")
    else:
        print(f"- Preview branch: {source_branch}")
    return alias_hostname


def finalize_pages_custom_domain(
    env_values: dict[str, str],
    *,
    target: str,
    alias_target: str,
) -> None:
    """Attach the Pages custom domain and point it at the current branch alias."""

    ensure_cloudflare_pages_custom_domain(env_values, target=target)
    sync_cloudflare_pages_domain_dns(env_values, target=target, alias_target=alias_target)


def run_workers_deploy(config: DevConfig, *, worker_config_path: Path, subprocess_env: dict[str, str]) -> None:
    """Deploy the Cloudflare Worker bundle to the target environment."""

    run_command(
        [
            "npx",
            "wrangler",
            "deploy",
            "--config",
            str(worker_config_path),
        ],
        cwd=config.repo_root,
        env=subprocess_env,
    )


def get_brevo_contact(env_values: dict[str, str], *, email: str) -> dict[str, object] | None:
    """Fetch a Brevo contact by email when it exists."""

    try:
        payload = request_json(
            url=f"https://api.brevo.com/v3/contacts/{urllib.parse.quote(email)}?identifierType=email_id",
            headers={
                "api-key": env_values["BREVO_API_KEY"],
                "accept": "application/json",
            },
        )
    except DevCliError as ex:
        if "HTTP 404" in str(ex):
            return None
        raise

    return payload if isinstance(payload, dict) else None


def delete_brevo_contact(env_values: dict[str, str], *, email: str) -> None:
    """Delete a Brevo contact by email when present."""

    try:
        request_json(
            url=f"https://api.brevo.com/v3/contacts/{urllib.parse.quote(email)}?identifierType=email_id",
            method="DELETE",
            headers={
                "api-key": env_values["BREVO_API_KEY"],
                "accept": "application/json",
            },
        )
    except DevCliError as ex:
        if "HTTP 404" in str(ex):
            return
        raise


def get_supabase_marketing_contact(env_values: dict[str, str], *, email: str) -> dict[str, object] | None:
    """Fetch a marketing contact record by normalized email from Supabase."""

    normalized_email = email.strip().lower()
    payload = request_json(
        url=(
            f"{env_values['SUPABASE_URL'].rstrip('/')}/rest/v1/marketing_contacts"
            f"?select=*&normalized_email=eq.{urllib.parse.quote(normalized_email)}&limit=1"
        ),
        headers=build_supabase_bearer_headers(api_key=env_values["SUPABASE_SECRET_KEY"]),
    )
    if not isinstance(payload, list):
        raise DevCliError("Supabase marketing contact lookup returned an unexpected payload.")
    return payload[0] if payload else None


def get_supabase_marketing_contact_role_interests(env_values: dict[str, str], *, contact_id: str) -> list[str]:
    """Fetch the saved marketing contact role-interest values from Supabase."""

    payload = request_json(
        url=(
            f"{env_values['SUPABASE_URL'].rstrip('/')}/rest/v1/marketing_contact_role_interests"
            f"?select=role&marketing_contact_id=eq.{urllib.parse.quote(contact_id)}"
        ),
        headers=build_supabase_bearer_headers(api_key=env_values["SUPABASE_SECRET_KEY"]),
    )
    if not isinstance(payload, list):
        raise DevCliError("Supabase role-interest lookup returned an unexpected payload.")
    return sorted(
        [
            row["role"].strip()
            for row in payload
            if isinstance(row, dict) and isinstance(row.get("role"), str) and row["role"].strip()
        ]
    )


def delete_supabase_marketing_contact(env_values: dict[str, str], *, contact_id: str) -> None:
    """Delete a marketing contact and its role-interest rows from Supabase."""

    headers = build_supabase_bearer_headers(api_key=env_values["SUPABASE_SECRET_KEY"])
    request_json(
        url=(
            f"{env_values['SUPABASE_URL'].rstrip('/')}/rest/v1/marketing_contact_role_interests"
            f"?marketing_contact_id=eq.{urllib.parse.quote(contact_id)}"
        ),
        method="DELETE",
        headers={**headers, "Prefer": "return=minimal"},
    )
    request_json(
        url=(
            f"{env_values['SUPABASE_URL'].rstrip('/')}/rest/v1/marketing_contacts"
            f"?id=eq.{urllib.parse.quote(contact_id)}"
        ),
        method="DELETE",
        headers={**headers, "Prefer": "return=minimal"},
    )


def wait_for_workers_deploy_smoke_base_url(*, base_url: str, timeout_seconds: int = 300) -> dict[str, object]:
    """Poll the deployed Worker base URL until the root endpoint is reachable."""

    deadline = time.time() + timeout_seconds
    last_error = f"{base_url}/ was not yet reachable."
    while time.time() < deadline:
        try:
            payload = request_json(
                url=f"{base_url}/",
                headers={"accept": "application/json", "user-agent": DEPLOY_SMOKE_USER_AGENT},
            )
        except DevCliError as ex:
            last_error = str(ex)
        else:
            if isinstance(payload, dict) and payload.get("service") == "board-enthusiasts-workers-api":
                return payload
            last_error = f"Unexpected root payload from {base_url}/."
        time.sleep(5)

    raise DevCliError(
        f"Workers smoke failed: {base_url}/ did not become reachable within {timeout_seconds} seconds.\n"
        f"Last error: {last_error}"
    )


def is_truthy_env_value(value: str) -> bool:
    """Return whether an environment-style flag value should be treated as true."""

    return value.strip().lower() in {"1", "true", "yes", "on"}


def is_landing_mode_enabled(env_values: dict[str, str]) -> bool:
    """Return whether the configured deploy target is running in landing-page-only mode."""

    return is_truthy_env_value(env_values.get("VITE_LANDING_MODE", ""))


def build_api_bearer_headers(token: str) -> dict[str, str]:
    """Build standard API bearer headers for deploy-smoke API requests."""

    return {
        "authorization": f"Bearer {token}",
        "accept": "application/json",
        "user-agent": DEPLOY_SMOKE_USER_AGENT,
    }


def is_request_timeout_error(error: DevCliError) -> bool:
    """Return whether a CLI error represents an HTTP timeout from ``request_json``."""

    return str(error).startswith("Request timed out for ")


def request_workers_deploy_smoke_json(
    *,
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    payload: dict[str, object] | list[object] | None = None,
    data: bytes | None = None,
    timeout_seconds: int = 30,
) -> object:
    """Issue a post-deploy Workers smoke request with a slightly more forgiving timeout policy."""

    for attempt in range(2):
        try:
            return request_json(
                url=url,
                method=method,
                headers=headers,
                payload=payload,
                data=data,
                timeout_seconds=timeout_seconds,
            )
        except DevCliError as ex:
            if not is_request_timeout_error(ex) or attempt > 0:
                raise

            write_step(f"Workers smoke request timed out; retrying once: {url}")
            time.sleep(5)

    raise AssertionError("Workers deploy smoke request retry loop exhausted unexpectedly.")


def require_full_mvp_deploy_smoke_values(env_values: dict[str, str]) -> dict[str, str]:
    """Resolve the extra smoke-account values required for full-MVP hosted smoke."""

    resolved: dict[str, str] = {}
    missing: list[str] = []
    for name in FULL_MVP_DEPLOY_SMOKE_REQUIRED_ENV_NAMES:
        value = env_values.get(name, "").strip()
        if not value:
            missing.append(name)
            continue
        resolved[name] = value

    if missing:
        raise DevCliError(
            "Full-MVP deploy smoke requires smoke-account credentials when VITE_LANDING_MODE=false.\n"
            f"Missing values: {', '.join(missing)}"
        )

    return resolved


def build_workers_deploy_smoke_environment(env_values: dict[str, str]) -> dict[str, str]:
    """Return the environment mapping required for the post-deploy Workers smoke.

    Landing-mode smoke uses only the values already present in the deploy environment.
    Full-MVP smoke additionally needs the staged smoke-account credentials, which are
    intentionally kept outside the main deploy fingerprint and resolved on demand.
    """

    if is_landing_mode_enabled(env_values):
        return dict(env_values)

    return {
        **env_values,
        **collect_present_environment_values(*FULL_MVP_DEPLOY_SMOKE_REQUIRED_ENV_NAMES),
    }


def has_full_mvp_deploy_smoke_values(env_values: dict[str, str]) -> bool:
    """Return whether the supplied deploy environment includes full-auth smoke credentials."""

    return all(env_values.get(name, "").strip() for name in FULL_MVP_DEPLOY_SMOKE_REQUIRED_ENV_NAMES)


def run_landing_workers_deploy_smoke(*, target: str, env_values: dict[str, str]) -> None:
    """Exercise the hosted landing-page Worker routes and external integrations."""

    base_url = env_values["BOARD_ENTHUSIASTS_WORKERS_BASE_URL"].rstrip("/")
    spa_origin = env_values["BOARD_ENTHUSIASTS_SPA_BASE_URL"].rstrip("/")
    smoke_email = f"deploy-smoke+{target}-{int(time.time())}@boardenthusiasts.com"
    smoke_headers = {
        "origin": spa_origin,
        "content-type": "application/json",
        "accept": "application/json",
        "user-agent": DEPLOY_SMOKE_USER_AGENT,
        "x-board-enthusiasts-deploy-smoke-secret": env_values["DEPLOY_SMOKE_SECRET"],
    }

    wait_for_workers_deploy_smoke_base_url(base_url=base_url)

    ready_payload = request_workers_deploy_smoke_json(
        url=f"{base_url}/health/ready",
        headers={"accept": "application/json", "user-agent": DEPLOY_SMOKE_USER_AGENT},
    )
    if not isinstance(ready_payload, dict) or ready_payload.get("status") != "ready":
        raise DevCliError("Workers smoke failed: /health/ready did not report ready status.")

    try:
        signup_payload = request_workers_deploy_smoke_json(
            url=f"{base_url}/marketing/signups",
            method="POST",
            headers=smoke_headers,
            payload={
                "email": smoke_email,
                "firstName": "Deploy Smoke",
                "source": "landing_page",
                "consentTextVersion": "landing-page-v1",
                "roleInterests": ["player"],
            },
        )
        if not isinstance(signup_payload, dict) or signup_payload.get("accepted") is not True:
            raise DevCliError("Workers smoke failed: marketing signup was not accepted.")

        contact = get_supabase_marketing_contact(env_values, email=smoke_email)
        if not contact:
            raise DevCliError("Workers smoke failed: Supabase marketing contact was not created.")
        if contact.get("lifecycle_status") != "waitlisted":
            raise DevCliError("Workers smoke failed: Supabase lifecycle status was not waitlisted.")

        role_interests = get_supabase_marketing_contact_role_interests(env_values, contact_id=str(contact["id"]))
        if role_interests != ["player"]:
            raise DevCliError("Workers smoke failed: Supabase role-interest projection was not saved correctly.")

        brevo_contact = get_brevo_contact(env_values, email=smoke_email)
        if not brevo_contact:
            raise DevCliError("Workers smoke failed: Brevo contact was not created.")

        support_payload = request_workers_deploy_smoke_json(
            url=f"{base_url}/support/issues",
            method="POST",
            headers=smoke_headers,
            payload={
                "category": "email_signup",
                "firstName": "Deploy Smoke",
                "email": smoke_email,
                "pageUrl": env_values["BOARD_ENTHUSIASTS_SPA_BASE_URL"],
                "apiBaseUrl": env_values["BOARD_ENTHUSIASTS_WORKERS_BASE_URL"],
                "occurredAt": datetime.now(timezone.utc).isoformat(),
                "errorMessage": "Post-deploy smoke validation",
                "technicalDetails": "Automated deploy smoke verification",
                "userAgent": "board-enthusiasts-dev-cli",
                "language": "en-US",
                "timeZone": "UTC",
            },
        )
        if not isinstance(support_payload, dict) or support_payload.get("accepted") is not True:
            raise DevCliError("Workers smoke failed: support issue route did not accept the smoke payload.")
    finally:
        contact = get_supabase_marketing_contact(env_values, email=smoke_email)
        if contact and isinstance(contact.get("id"), str):
            delete_supabase_marketing_contact(env_values, contact_id=contact["id"])
        delete_brevo_contact(env_values, email=smoke_email)


def run_full_mvp_workers_deploy_smoke(*, target: str, env_values: dict[str, str]) -> None:
    """Exercise the hosted full-MVP Worker routes with staged smoke accounts."""

    base_url = env_values["BOARD_ENTHUSIASTS_WORKERS_BASE_URL"].rstrip("/")
    smoke_values = require_full_mvp_deploy_smoke_values(env_values)
    wait_for_workers_deploy_smoke_base_url(base_url=base_url)

    ready_payload = request_workers_deploy_smoke_json(
        url=f"{base_url}/health/ready",
        headers={"accept": "application/json", "user-agent": DEPLOY_SMOKE_USER_AGENT},
    )
    if not isinstance(ready_payload, dict) or ready_payload.get("status") != "ready":
        raise DevCliError("Workers smoke failed: /health/ready did not report ready status.")

    player_token = fetch_supabase_access_token(
        supabase_url=env_values["SUPABASE_URL"],
        publishable_key=env_values["SUPABASE_PUBLISHABLE_KEY"],
        email=smoke_values["DEPLOY_SMOKE_PLAYER_EMAIL"],
        password=smoke_values["DEPLOY_SMOKE_USER_PASSWORD"],
    )
    developer_token = fetch_supabase_access_token(
        supabase_url=env_values["SUPABASE_URL"],
        publishable_key=env_values["SUPABASE_PUBLISHABLE_KEY"],
        email=smoke_values["DEPLOY_SMOKE_DEVELOPER_EMAIL"],
        password=smoke_values["DEPLOY_SMOKE_USER_PASSWORD"],
    )
    moderator_token = fetch_supabase_access_token(
        supabase_url=env_values["SUPABASE_URL"],
        publishable_key=env_values["SUPABASE_PUBLISHABLE_KEY"],
        email=smoke_values["DEPLOY_SMOKE_MODERATOR_EMAIL"],
        password=smoke_values["DEPLOY_SMOKE_USER_PASSWORD"],
    )

    metadata_payload = request_workers_deploy_smoke_json(
        url=f"{base_url}/",
        headers={"accept": "application/json", "user-agent": DEPLOY_SMOKE_USER_AGENT},
    )
    if not isinstance(metadata_payload, dict) or metadata_payload.get("service") != "board-enthusiasts-workers-api":
        raise DevCliError("Workers smoke failed: root metadata route did not return the expected service name.")

    genres_payload = request_workers_deploy_smoke_json(
        url=f"{base_url}/genres",
        headers={"accept": "application/json", "user-agent": DEPLOY_SMOKE_USER_AGENT},
    )
    age_rating_payload = request_workers_deploy_smoke_json(
        url=f"{base_url}/age-rating-authorities",
        headers={"accept": "application/json", "user-agent": DEPLOY_SMOKE_USER_AGENT},
    )
    if not isinstance(genres_payload, dict) or not isinstance(genres_payload.get("genres"), list):
        raise DevCliError("Workers smoke failed: /genres did not return a genre list.")
    if not isinstance(age_rating_payload, dict) or not isinstance(age_rating_payload.get("ageRatingAuthorities"), list):
        raise DevCliError("Workers smoke failed: /age-rating-authorities did not return an authority list.")

    title_spotlights_payload = request_workers_deploy_smoke_json(
        url=f"{base_url}/spotlights/home",
        headers={"accept": "application/json", "user-agent": DEPLOY_SMOKE_USER_AGENT},
    )
    offering_spotlights_payload = request_workers_deploy_smoke_json(
        url=f"{base_url}/internal/home-offering-spotlights",
        headers={"accept": "application/json", "user-agent": DEPLOY_SMOKE_USER_AGENT},
    )
    metrics_payload = request_workers_deploy_smoke_json(
        url=f"{base_url}/internal/be-home/metrics",
        headers={"accept": "application/json", "user-agent": DEPLOY_SMOKE_USER_AGENT},
    )
    studios_payload = request_workers_deploy_smoke_json(
        url=f"{base_url}/studios",
        headers={"accept": "application/json", "user-agent": DEPLOY_SMOKE_USER_AGENT},
    )
    if not isinstance(title_spotlights_payload, dict) or not isinstance(title_spotlights_payload.get("entries"), list):
        raise DevCliError("Workers smoke failed: /spotlights/home did not return an entries list.")
    if not isinstance(offering_spotlights_payload, dict) or not isinstance(offering_spotlights_payload.get("entries"), list):
        raise DevCliError("Workers smoke failed: /internal/home-offering-spotlights did not return an entries list.")
    if not isinstance(metrics_payload, dict) or not isinstance(metrics_payload.get("metrics"), dict):
        raise DevCliError("Workers smoke failed: /internal/be-home/metrics did not return a metrics payload.")
    if not isinstance(studios_payload, dict) or not isinstance(studios_payload.get("studios"), list):
        raise DevCliError("Workers smoke failed: /studios did not return a studios list.")

    request_workers_deploy_smoke_json(
        url=f"{base_url}/identity/user-name-availability?userName=deploy-smoke-check",
        headers={"accept": "application/json", "user-agent": DEPLOY_SMOKE_USER_AGENT},
    )

    catalog_payload = request_workers_deploy_smoke_json(
        url=f"{base_url}/catalog?pageNumber=1&pageSize=4&sort=title-asc",
        headers={"accept": "application/json", "user-agent": DEPLOY_SMOKE_USER_AGENT},
    )
    if not isinstance(catalog_payload, dict) or not isinstance(catalog_payload.get("titles"), list):
        raise DevCliError("Workers smoke failed: /catalog did not return a titles list.")

    public_title = next((entry for entry in catalog_payload["titles"] if isinstance(entry, dict)), None)
    library_title = next(
        (
            entry
            for entry in catalog_payload["titles"]
            if isinstance(entry, dict)
            and str(entry.get("id", "")).strip()
            and isinstance(entry.get("acquisitionUrl"), str)
            and entry["acquisitionUrl"].strip()
        ),
        None,
    )
    public_title_id = str(public_title.get("id", "")).strip() if isinstance(public_title, dict) else ""
    public_title_slug = str(public_title.get("slug", "")).strip() if isinstance(public_title, dict) else ""
    public_studio_slug = str(public_title.get("studioSlug", "")).strip() if isinstance(public_title, dict) else ""
    library_title_id = str(library_title.get("id", "")).strip() if isinstance(library_title, dict) else ""

    if public_title_id and public_title_slug and public_studio_slug:
        request_workers_deploy_smoke_json(
            url=f"{base_url}/catalog/{urllib.parse.quote(public_studio_slug)}/{urllib.parse.quote(public_title_slug)}",
            headers={"accept": "application/json", "user-agent": DEPLOY_SMOKE_USER_AGENT},
        )
        request_workers_deploy_smoke_json(
            url=f"{base_url}/studios/{urllib.parse.quote(public_studio_slug)}",
            headers={"accept": "application/json", "user-agent": DEPLOY_SMOKE_USER_AGENT},
        )
    elif target != "production":
        raise DevCliError("Workers smoke failed: /catalog did not return at least one public title.")
    if not library_title_id and target != "production":
        raise DevCliError("Workers smoke failed: /catalog did not return at least one library-eligible public title.")

    player_headers = build_api_bearer_headers(player_token)
    developer_headers = build_api_bearer_headers(developer_token)
    moderator_headers = build_api_bearer_headers(moderator_token)

    request_workers_deploy_smoke_json(url=f"{base_url}/identity/me", headers=player_headers)
    request_workers_deploy_smoke_json(url=f"{base_url}/identity/me/profile", headers=player_headers)
    player_notifications_payload = request_workers_deploy_smoke_json(url=f"{base_url}/identity/me/notifications", headers=player_headers)
    request_workers_deploy_smoke_json(
        url=f"{base_url}/identity/me/board-profile",
        method="PUT",
        headers=player_headers,
        payload={
            "boardUserId": "deploy_smoke_player",
            "displayName": "Deploy Smoke Player",
            "avatarUrl": "https://example.invalid/deploy-smoke-player.png",
        },
    )
    request_workers_deploy_smoke_json(url=f"{base_url}/identity/me/board-profile", headers=player_headers)
    request_workers_deploy_smoke_json(url=f"{base_url}/identity/me/board-profile", method="DELETE", headers=player_headers)
    request_workers_deploy_smoke_json(url=f"{base_url}/identity/me/developer-enrollment", headers=player_headers)
    if isinstance(player_notifications_payload, dict) and isinstance(player_notifications_payload.get("notifications"), list):
        first_notification = next(
            (
                entry
                for entry in player_notifications_payload["notifications"]
                if isinstance(entry, dict) and isinstance(entry.get("id"), str) and entry["id"].strip()
            ),
            None,
        )
        if isinstance(first_notification, dict):
            request_workers_deploy_smoke_json(
                url=f"{base_url}/identity/me/notifications/{urllib.parse.quote(first_notification['id'])}/read",
                method="POST",
                headers=player_headers,
            )

    request_workers_deploy_smoke_json(url=f"{base_url}/player/library", headers=player_headers)
    request_workers_deploy_smoke_json(url=f"{base_url}/player/wishlist", headers=player_headers)
    if library_title_id:
        request_workers_deploy_smoke_json(
            url=f"{base_url}/player/library/titles/{urllib.parse.quote(library_title_id)}",
            method="PUT",
            headers=player_headers,
        )
        request_workers_deploy_smoke_json(
            url=f"{base_url}/player/library/titles/{urllib.parse.quote(library_title_id)}",
            method="DELETE",
            headers=player_headers,
        )
    if public_title_id:
        request_workers_deploy_smoke_json(
            url=f"{base_url}/player/wishlist/titles/{urllib.parse.quote(public_title_id)}",
            method="PUT",
            headers=player_headers,
        )
        request_workers_deploy_smoke_json(
            url=f"{base_url}/player/wishlist/titles/{urllib.parse.quote(public_title_id)}",
            method="DELETE",
            headers=player_headers,
        )

    request_workers_deploy_smoke_json(url=f"{base_url}/identity/me", headers=developer_headers)
    request_workers_deploy_smoke_json(url=f"{base_url}/identity/me/profile", headers=developer_headers)
    request_workers_deploy_smoke_json(url=f"{base_url}/identity/me/developer-enrollment", headers=developer_headers)
    request_workers_deploy_smoke_json(url=f"{base_url}/identity/me/developer-enrollment", method="POST", headers=developer_headers)

    managed_studios_payload = request_workers_deploy_smoke_json(url=f"{base_url}/developer/studios", headers=developer_headers)
    if not isinstance(managed_studios_payload, dict) or not isinstance(managed_studios_payload.get("studios"), list):
        raise DevCliError("Workers smoke failed: /developer/studios did not return a managed studio list.")

    unique_suffix = str(int(time.time()))
    created_studio_id = ""
    created_title_id = ""
    created_report_id = ""
    second_created_report_id = ""
    rollback_release_id = ""
    release_under_test_id = ""
    try:
        created_studio_payload = request_workers_deploy_smoke_json(
            url=f"{base_url}/studios",
            method="POST",
            headers=developer_headers,
            payload={
                "slug": f"deploy-smoke-{unique_suffix}",
                "displayName": "Deploy Smoke Studio",
                "description": "Temporary hosted deploy-smoke studio.",
            },
        )
        if not isinstance(created_studio_payload, dict) or not isinstance(created_studio_payload.get("studio"), dict):
            raise DevCliError("Workers smoke failed: studio create did not return a studio payload.")
        created_studio_id = str(created_studio_payload["studio"].get("id", "")).strip()
        if not created_studio_id:
            raise DevCliError("Workers smoke failed: studio create did not return a studio id.")

        request_workers_deploy_smoke_json(
            url=f"{base_url}/developer/studios/{urllib.parse.quote(created_studio_id)}",
            method="PUT",
            headers=developer_headers,
            payload={
                "slug": f"deploy-smoke-{unique_suffix}",
                "displayName": "Deploy Smoke Studio",
                "description": "Updated temporary hosted deploy-smoke studio.",
            },
        )
        request_workers_deploy_smoke_json(url=f"{base_url}/developer/studios/{urllib.parse.quote(created_studio_id)}/links", headers=developer_headers)
        created_link_payload = request_workers_deploy_smoke_json(
            url=f"{base_url}/developer/studios/{urllib.parse.quote(created_studio_id)}/links",
            method="POST",
            headers=developer_headers,
            payload={"label": "Docs", "url": "https://example.invalid/deploy-docs"},
        )
        if not isinstance(created_link_payload, dict) or not isinstance(created_link_payload.get("link"), dict):
            raise DevCliError("Workers smoke failed: studio link create did not return a link payload.")
        created_link_id = str(created_link_payload["link"].get("id", "")).strip()
        if not created_link_id:
            raise DevCliError("Workers smoke failed: studio link create did not return a link id.")
        request_workers_deploy_smoke_json(
            url=f"{base_url}/developer/studios/{urllib.parse.quote(created_studio_id)}/links/{urllib.parse.quote(created_link_id)}",
            method="PUT",
            headers=developer_headers,
            payload={"label": "Support", "url": "https://example.invalid/deploy-support"},
        )
        request_workers_deploy_smoke_json(
            url=f"{base_url}/developer/studios/{urllib.parse.quote(created_studio_id)}/links/{urllib.parse.quote(created_link_id)}",
            method="DELETE",
            headers=developer_headers,
        )
        request_workers_deploy_smoke_json(url=f"{base_url}/developer/studios/{urllib.parse.quote(created_studio_id)}/titles", headers=developer_headers)

        created_title_payload = request_workers_deploy_smoke_json(
            url=f"{base_url}/developer/studios/{urllib.parse.quote(created_studio_id)}/titles",
            method="POST",
            headers=developer_headers,
            payload={
                "contentKind": "game",
                "metadata": {
                    "displayName": "Deploy Smoke Title",
                    "shortDescription": "Temporary hosted deploy-smoke title.",
                    "description": "This title exists only for hosted MVP smoke coverage.",
                    "genreSlugs": ["utility", "qa"],
                    "minPlayers": 1,
                    "maxPlayers": 4,
                    "maxPlayersOrMore": False,
                    "ageRatingAuthority": "ESRB",
                    "ageRatingValue": "E",
                    "minAgeYears": 6,
                },
            },
        )
        if not isinstance(created_title_payload, dict) or not isinstance(created_title_payload.get("title"), dict):
            raise DevCliError("Workers smoke failed: title create did not return a title payload.")
        created_title_id = str(created_title_payload["title"].get("id", "")).strip()
        if not created_title_id:
            raise DevCliError("Workers smoke failed: title create did not return a title id.")

        request_workers_deploy_smoke_json(url=f"{base_url}/developer/titles/{urllib.parse.quote(created_title_id)}", headers=developer_headers)
        request_workers_deploy_smoke_json(
            url=f"{base_url}/developer/titles/{urllib.parse.quote(created_title_id)}",
            method="PUT",
            headers=developer_headers,
            payload={
                "contentKind": "game",
                "visibility": "unlisted",
            },
        )
        revised_title_payload = request_workers_deploy_smoke_json(
            url=f"{base_url}/developer/titles/{urllib.parse.quote(created_title_id)}/metadata/current",
            method="PUT",
            headers=developer_headers,
            payload={
                "displayName": "Deploy Smoke Title Revised",
                "shortDescription": "Revised hosted deploy-smoke title.",
                "description": "Updated metadata for hosted MVP smoke coverage.",
                "genreSlugs": ["utility", "qa"],
                "minPlayers": 1,
                "maxPlayers": 6,
                "maxPlayersOrMore": False,
                "ageRatingAuthority": "ESRB",
                "ageRatingValue": "E10+",
                "minAgeYears": 10,
            },
        )
        if not isinstance(revised_title_payload, dict) or not isinstance(revised_title_payload.get("title"), dict):
            raise DevCliError("Workers smoke failed: title metadata update did not return a title payload.")
        current_metadata_revision = revised_title_payload["title"].get("currentMetadataRevision")
        if not isinstance(current_metadata_revision, int):
            raise DevCliError("Workers smoke failed: title metadata update did not return currentMetadataRevision.")

        request_workers_deploy_smoke_json(url=f"{base_url}/developer/titles/{urllib.parse.quote(created_title_id)}/metadata-versions", headers=developer_headers)
        request_workers_deploy_smoke_json(
            url=f"{base_url}/developer/titles/{urllib.parse.quote(created_title_id)}/metadata-versions/{current_metadata_revision}/activate",
            method="POST",
            headers=developer_headers,
        )
        request_workers_deploy_smoke_json(url=f"{base_url}/developer/titles/{urllib.parse.quote(created_title_id)}/media", headers=developer_headers)
        request_workers_deploy_smoke_json(
            url=f"{base_url}/developer/titles/{urllib.parse.quote(created_title_id)}/media/card",
            method="PUT",
            headers=developer_headers,
            payload={
                "sourceUrl": "https://example.invalid/deploy-card.png",
                "altText": "Deploy smoke card art",
                "mimeType": "image/png",
                "width": 900,
                "height": 1200,
            },
        )
        request_workers_deploy_smoke_json(url=f"{base_url}/developer/titles/{urllib.parse.quote(created_title_id)}/releases", headers=developer_headers)
        created_release_payload = request_workers_deploy_smoke_json(
            url=f"{base_url}/developer/titles/{urllib.parse.quote(created_title_id)}/releases",
            method="POST",
            headers=developer_headers,
            payload={
                "version": "0.1.0-smoke",
                "status": "testing",
                "acquisitionUrl": "https://example.invalid/releases/0.1.0-smoke",
            },
        )
        if not isinstance(created_release_payload, dict) or not isinstance(created_release_payload.get("release"), dict):
            raise DevCliError("Workers smoke failed: title release create did not return a release payload.")
        rollback_release_id = str(created_release_payload["release"].get("id", "")).strip()
        if not rollback_release_id:
            raise DevCliError("Workers smoke failed: title release create did not return a release id.")

        second_release_payload = request_workers_deploy_smoke_json(
            url=f"{base_url}/developer/titles/{urllib.parse.quote(created_title_id)}/releases",
            method="POST",
            headers=developer_headers,
            payload={
                "version": "0.1.1-smoke",
                "status": "production",
                "acquisitionUrl": "https://example.invalid/releases/0.1.1-smoke",
            },
        )
        if not isinstance(second_release_payload, dict) or not isinstance(second_release_payload.get("release"), dict):
            raise DevCliError("Workers smoke failed: second title release create did not return a release payload.")
        release_under_test_id = str(second_release_payload["release"].get("id", "")).strip()
        if not release_under_test_id:
            raise DevCliError("Workers smoke failed: second title release create did not return a release id.")

        release_list_payload = request_workers_deploy_smoke_json(
            url=f"{base_url}/developer/titles/{urllib.parse.quote(created_title_id)}/releases",
            headers=developer_headers,
        )
        if not isinstance(release_list_payload, dict) or not isinstance(release_list_payload.get("releases"), list):
            raise DevCliError("Workers smoke failed: title releases list did not return a release list.")
        release_versions = {
            str(entry.get("version", "")).strip()
            for entry in release_list_payload["releases"]
            if isinstance(entry, dict)
        }
        if "0.1.0-smoke" not in release_versions or "0.1.1-smoke" not in release_versions:
            raise DevCliError("Workers smoke failed: title releases list did not preserve both release versions.")

        request_workers_deploy_smoke_json(
            url=f"{base_url}/developer/titles/{urllib.parse.quote(created_title_id)}/releases/{urllib.parse.quote(release_under_test_id)}",
            method="PUT",
            headers=developer_headers,
            payload={
                "version": "0.1.1-smoke",
                "status": "production",
                "acquisitionUrl": "https://example.invalid/releases/0.1.1-smoke",
            },
        )
        request_workers_deploy_smoke_json(
            url=f"{base_url}/developer/titles/{urllib.parse.quote(created_title_id)}/releases/{urllib.parse.quote(rollback_release_id)}/activate",
            method="POST",
            headers=developer_headers,
        )
        request_workers_deploy_smoke_json(
            url=f"{base_url}/developer/titles/{urllib.parse.quote(created_title_id)}/activate",
            method="POST",
            headers=developer_headers,
        )
        request_workers_deploy_smoke_json(
            url=f"{base_url}/developer/titles/{urllib.parse.quote(created_title_id)}/archive",
            method="POST",
            headers=developer_headers,
        )
        request_workers_deploy_smoke_json(
            url=f"{base_url}/developer/titles/{urllib.parse.quote(created_title_id)}/unarchive",
            method="POST",
            headers=developer_headers,
        )

        created_report_payload = request_workers_deploy_smoke_json(
            url=f"{base_url}/player/reports",
            method="POST",
            headers=player_headers,
            payload={
                "titleId": created_title_id,
                "reason": f"Deploy smoke report {unique_suffix}",
            },
        )
        second_created_report_payload = request_workers_deploy_smoke_json(
            url=f"{base_url}/player/reports",
            method="POST",
            headers=player_headers,
            payload={
                "titleId": created_title_id,
                "reason": f"Deploy smoke report secondary {unique_suffix}",
            },
        )
        if not isinstance(created_report_payload, dict) or not isinstance(created_report_payload.get("report"), dict):
            raise DevCliError("Workers smoke failed: player report create did not return a report payload.")
        if not isinstance(second_created_report_payload, dict) or not isinstance(second_created_report_payload.get("report"), dict):
            raise DevCliError("Workers smoke failed: second player report create did not return a report payload.")
        created_report_id = str(created_report_payload["report"].get("id", "")).strip()
        second_created_report_id = str(second_created_report_payload["report"].get("id", "")).strip()
        if not created_report_id or not second_created_report_id:
            raise DevCliError("Workers smoke failed: player report creation did not return both report ids.")

        request_workers_deploy_smoke_json(url=f"{base_url}/player/reports", headers=player_headers)
        request_workers_deploy_smoke_json(url=f"{base_url}/player/reports/{urllib.parse.quote(created_report_id)}", headers=player_headers)
        request_workers_deploy_smoke_json(
            url=f"{base_url}/player/reports/{urllib.parse.quote(created_report_id)}/messages",
            method="POST",
            headers=player_headers,
            payload={"message": "Deploy smoke player follow-up."},
        )

        request_workers_deploy_smoke_json(url=f"{base_url}/developer/titles/{urllib.parse.quote(created_title_id)}/reports", headers=developer_headers)
        request_workers_deploy_smoke_json(
            url=f"{base_url}/developer/titles/{urllib.parse.quote(created_title_id)}/reports/{urllib.parse.quote(created_report_id)}",
            headers=developer_headers,
        )
        request_workers_deploy_smoke_json(
            url=f"{base_url}/developer/titles/{urllib.parse.quote(created_title_id)}/reports/{urllib.parse.quote(created_report_id)}/messages",
            method="POST",
            headers=developer_headers,
            payload={"message": "Deploy smoke developer follow-up."},
        )

        developer_search_term = smoke_values["DEPLOY_SMOKE_DEVELOPER_EMAIL"].split("@", 1)[0]
        moderation_search_payload = request_workers_deploy_smoke_json(
            url=f"{base_url}/moderation/developers?search={urllib.parse.quote(developer_search_term)}",
            headers=moderator_headers,
        )
        if not isinstance(moderation_search_payload, dict) or not isinstance(moderation_search_payload.get("developers"), list):
            raise DevCliError("Workers smoke failed: moderation developer search did not return a developer list.")
        moderated_developer = next(
            (
                entry
                for entry in moderation_search_payload["developers"]
                if isinstance(entry, dict) and entry.get("email") == smoke_values["DEPLOY_SMOKE_DEVELOPER_EMAIL"]
            ),
            None,
        )
        if not isinstance(moderated_developer, dict) or not isinstance(moderated_developer.get("developerSubject"), str):
            raise DevCliError("Workers smoke failed: moderation search did not return the configured smoke developer.")
        moderated_developer_subject = moderated_developer["developerSubject"].strip()
        request_workers_deploy_smoke_json(
            url=f"{base_url}/moderation/developers/{urllib.parse.quote(moderated_developer_subject)}/verification",
            headers=moderator_headers,
        )
        request_workers_deploy_smoke_json(
            url=f"{base_url}/moderation/developers/{urllib.parse.quote(moderated_developer_subject)}/verified-developer",
            method="PUT",
            headers=moderator_headers,
        )
        request_workers_deploy_smoke_json(
            url=f"{base_url}/moderation/developers/{urllib.parse.quote(moderated_developer_subject)}/verified-developer",
            method="DELETE",
            headers=moderator_headers,
        )

        request_workers_deploy_smoke_json(url=f"{base_url}/moderation/title-reports", headers=moderator_headers)
        request_workers_deploy_smoke_json(
            url=f"{base_url}/moderation/title-reports/{urllib.parse.quote(created_report_id)}",
            headers=moderator_headers,
        )
        request_workers_deploy_smoke_json(
            url=f"{base_url}/moderation/title-reports/{urllib.parse.quote(created_report_id)}/messages",
            method="POST",
            headers=moderator_headers,
            payload={"message": "Deploy smoke moderation follow-up.", "recipientRole": "developer"},
        )
        request_workers_deploy_smoke_json(
            url=f"{base_url}/moderation/title-reports/{urllib.parse.quote(created_report_id)}/validate",
            method="POST",
            headers=moderator_headers,
            payload={"note": "Validated by deploy smoke."},
        )
        request_workers_deploy_smoke_json(
            url=f"{base_url}/moderation/title-reports/{urllib.parse.quote(second_created_report_id)}/invalidate",
            method="POST",
            headers=moderator_headers,
            payload={"note": "Invalidated by deploy smoke."},
        )
    finally:
        if created_studio_id:
            request_workers_deploy_smoke_json(
                url=f"{base_url}/developer/studios/{urllib.parse.quote(created_studio_id)}",
                method="DELETE",
                headers=developer_headers,
            )


def run_public_mvp_workers_deploy_smoke(*, target: str, env_values: dict[str, str]) -> None:
    """Exercise public hosted Worker routes without relying on seeded authenticated smoke accounts."""

    del target
    base_url = env_values["BOARD_ENTHUSIASTS_WORKERS_BASE_URL"].rstrip("/")
    wait_for_workers_deploy_smoke_base_url(base_url=base_url)

    ready_payload = request_workers_deploy_smoke_json(
        url=f"{base_url}/health/ready",
        headers={"accept": "application/json", "user-agent": DEPLOY_SMOKE_USER_AGENT},
    )
    if not isinstance(ready_payload, dict) or ready_payload.get("status") != "ready":
        raise DevCliError("Workers smoke failed: /health/ready did not report ready status.")

    metadata_payload = request_workers_deploy_smoke_json(
        url=f"{base_url}/",
        headers={"accept": "application/json", "user-agent": DEPLOY_SMOKE_USER_AGENT},
    )
    if not isinstance(metadata_payload, dict) or metadata_payload.get("service") != "board-enthusiasts-workers-api":
        raise DevCliError("Workers smoke failed: root metadata route did not return the expected service name.")

    genres_payload = request_workers_deploy_smoke_json(
        url=f"{base_url}/genres",
        headers={"accept": "application/json", "user-agent": DEPLOY_SMOKE_USER_AGENT},
    )
    age_rating_payload = request_workers_deploy_smoke_json(
        url=f"{base_url}/age-rating-authorities",
        headers={"accept": "application/json", "user-agent": DEPLOY_SMOKE_USER_AGENT},
    )
    if not isinstance(genres_payload, dict) or not isinstance(genres_payload.get("genres"), list):
        raise DevCliError("Workers smoke failed: /genres did not return a genre list.")
    if not isinstance(age_rating_payload, dict) or not isinstance(age_rating_payload.get("ageRatingAuthorities"), list):
        raise DevCliError("Workers smoke failed: /age-rating-authorities did not return an authority list.")

    request_workers_deploy_smoke_json(
        url=f"{base_url}/identity/user-name-availability?userName=deploy-smoke-check",
        headers={"accept": "application/json", "user-agent": DEPLOY_SMOKE_USER_AGENT},
    )

    title_spotlights_payload = request_workers_deploy_smoke_json(
        url=f"{base_url}/spotlights/home",
        headers={"accept": "application/json", "user-agent": DEPLOY_SMOKE_USER_AGENT},
    )
    if not isinstance(title_spotlights_payload, dict) or not isinstance(title_spotlights_payload.get("entries"), list):
        raise DevCliError("Workers smoke failed: /spotlights/home did not return an entries list.")

    offering_spotlights_payload = request_workers_deploy_smoke_json(
        url=f"{base_url}/internal/home-offering-spotlights",
        headers={"accept": "application/json", "user-agent": DEPLOY_SMOKE_USER_AGENT},
    )
    if not isinstance(offering_spotlights_payload, dict) or not isinstance(offering_spotlights_payload.get("entries"), list):
        raise DevCliError("Workers smoke failed: /internal/home-offering-spotlights did not return an entries list.")

    catalog_payload = request_workers_deploy_smoke_json(
        url=f"{base_url}/catalog?pageNumber=1&pageSize=4&sort=title-asc",
        headers={"accept": "application/json", "user-agent": DEPLOY_SMOKE_USER_AGENT},
    )
    if not isinstance(catalog_payload, dict) or not isinstance(catalog_payload.get("titles"), list):
        raise DevCliError("Workers smoke failed: /catalog did not return a titles list.")

    studios_payload = request_workers_deploy_smoke_json(
        url=f"{base_url}/studios",
        headers={"accept": "application/json", "user-agent": DEPLOY_SMOKE_USER_AGENT},
    )
    if not isinstance(studios_payload, dict) or not isinstance(studios_payload.get("studios"), list):
        raise DevCliError("Workers smoke failed: /studios did not return a studios list.")

    public_title = next((entry for entry in catalog_payload["titles"] if isinstance(entry, dict)), None)
    if isinstance(public_title, dict):
        public_title_slug = str(public_title.get("slug", "")).strip()
        public_studio_slug = str(public_title.get("studioSlug", "")).strip()
        if public_title_slug and public_studio_slug:
            request_workers_deploy_smoke_json(
                url=f"{base_url}/catalog/{urllib.parse.quote(public_studio_slug)}/{urllib.parse.quote(public_title_slug)}",
                headers={"accept": "application/json", "user-agent": DEPLOY_SMOKE_USER_AGENT},
            )

    public_studio = next((entry for entry in studios_payload["studios"] if isinstance(entry, dict)), None)
    if isinstance(public_studio, dict):
        studio_slug = str(public_studio.get("slug", "")).strip()
        if studio_slug:
            request_workers_deploy_smoke_json(
                url=f"{base_url}/studios/{urllib.parse.quote(studio_slug)}",
                headers={"accept": "application/json", "user-agent": DEPLOY_SMOKE_USER_AGENT},
            )


def run_workers_deploy_smoke(config: DevConfig, *, target: str, env_values: dict[str, str]) -> None:
    """Exercise the hosted Worker directly after deploy and verify the active product mode."""

    del config
    smoke_env_values = build_workers_deploy_smoke_environment(env_values)
    write_step("Running post-deploy Workers smoke")
    if is_landing_mode_enabled(smoke_env_values):
        run_landing_workers_deploy_smoke(target=target, env_values=smoke_env_values)
        return

    if target == "staging":
        run_full_mvp_workers_deploy_smoke(target=target, env_values=smoke_env_values)
        return

    if has_full_mvp_deploy_smoke_values(smoke_env_values):
        write_step("Using authenticated production smoke accounts for full-MVP deploy smoke")
        run_full_mvp_workers_deploy_smoke(target=target, env_values=smoke_env_values)
        return

    write_step("Full-MVP smoke accounts are not configured; running public production Worker smoke")
    run_public_mvp_workers_deploy_smoke(target=target, env_values=smoke_env_values)


def is_expected_pages_shell_html(html: str) -> bool:
    """Return whether the fetched HTML looks like the expected deployed SPA shell."""

    normalized = html.lower()
    return (
        '<div id="root"></div>' in normalized
        and "/assets/index-" in normalized
        and "board enthusiasts" in normalized
        and "nothing is here yet" not in normalized
        and "error 1014" not in normalized
    )


def wait_for_pages_shell(url: str) -> None:
    """Poll a hosted SPA route until it serves the expected application shell."""

    deadline = time.time() + 300
    last_error = f"{url} did not become reachable."
    request = urllib.request.Request(
        url,
        headers={"accept": "text/html", "user-agent": DEPLOY_SMOKE_USER_AGENT},
    )

    while time.time() < deadline:
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                html = response.read().decode("utf-8", errors="replace")
        except Exception as ex:  # noqa: BLE001
            last_error = str(ex)
            time.sleep(5)
            continue

        if is_expected_pages_shell_html(html):
            return

        last_error = "Expected SPA shell markers were not present in the rendered HTML."
        time.sleep(5)

    raise DevCliError(
        "Pages smoke failed: the custom domain did not become ready within 300 seconds.\n"
        f"Last error: {last_error}"
    )


def run_pages_deploy_smoke(*, target: str, env_values: dict[str, str]) -> None:
    """Verify the hosted SPA is reachable after deploy for the active product mode."""

    write_step("Running post-deploy Pages smoke")
    base_url = env_values["BOARD_ENTHUSIASTS_SPA_BASE_URL"].rstrip("/")
    smoke_paths = [""]
    if not is_landing_mode_enabled(env_values):
        smoke_paths.extend(["/offerings", "/browse", "/studios", "/install", "/support"])
        if target == "staging":
            smoke_paths.extend(
                [
                    "/studios/blue-harbor-games",
                    "/browse/blue-harbor-games/lantern-drift",
                    "/player",
                    "/developer",
                    "/moderate",
                ]
            )

    for path in smoke_paths:
        wait_for_pages_shell(f"{base_url}{path}")


def resolve_deploy_source_branch(
    config: DevConfig,
    *,
    explicit_source_branch: str | None = None,
) -> str:
    """Resolve the branch name that should be attached to a hosted Pages deploy."""

    if explicit_source_branch and explicit_source_branch.strip():
        return explicit_source_branch.strip()

    github_ref_name = os.environ.get("GITHUB_REF_NAME", "").strip()
    if github_ref_name:
        return github_ref_name

    current_branch = run_command(
        ["git", "branch", "--show-current"],
        cwd=config.repo_root,
        capture_output=True,
    ).stdout.strip()
    if current_branch:
        return current_branch

    raise DevCliError(
        "Unable to determine the deploy source branch from Git or GITHUB_REF_NAME. "
        "Rerun from an attached branch or provide --source-branch explicitly."
    )


def resolve_deploy_required_environment_names(*, target: str) -> tuple[str, ...]:
    """Resolve the required deploy environment names for the selected hosted target."""

    if target == "staging":
        return (*DEPLOY_REQUIRED_ENV_NAMES, *STAGING_DEPLOY_REQUIRED_ENV_NAMES)
    return DEPLOY_REQUIRED_ENV_NAMES


def resolve_bootstrap_super_admin_email(*, email: str | None, target: str) -> str:
    """Return the operator email for a bootstrap run, prompting when omitted."""

    normalized = (email or "").strip()
    if normalized:
        return normalized

    if not sys.stdin.isatty():
        raise DevCliError(
            f"{target.title()} super-admin bootstrap requires --email when stdin is not interactive."
        )

    prompt = f"{target.title()} super-admin email: "
    while True:
        entered = input(prompt).strip()
        if entered:
            return entered
        print("Email is required.")


def prompt_bootstrap_super_admin_password(*, target: str, email: str) -> str:
    """Prompt securely for the bootstrap password and require confirmation."""

    if not sys.stdin.isatty():
        raise DevCliError(
            f"{target.title()} super-admin bootstrap requires an interactive terminal to enter the password securely."
        )

    prompt = f"{target.title()} super-admin password for {email}: "
    confirm_prompt = f"Confirm password for {email}: "
    while True:
        password = getpass.getpass(prompt)
        if not password:
            print("Password is required.")
            continue

        confirmation = getpass.getpass(confirm_prompt)
        if password != confirmation:
            print("Passwords did not match. Please try again.")
            continue

        return password


def run_bootstrap_super_admin_command(
    config: DevConfig,
    *,
    target: str,
    email: str | None,
    user_name: str | None,
    display_name: str | None,
    first_name: str | None,
    last_name: str | None,
) -> None:
    """Create or update the one-time super-admin account for the selected environment."""

    if target not in SUPPORTED_ENVIRONMENT_TARGETS:
        raise DevCliError(f"Unsupported bootstrap-super-admin target: {target}")

    ensure_migration_workspace_scaffolding(config)
    install_migration_workspace_dependencies(config)
    resolved_email = resolve_bootstrap_super_admin_email(email=email, target=target)
    password = prompt_bootstrap_super_admin_password(target=target, email=resolved_email)
    env_values = require_environment_values(
        "SUPABASE_URL",
        "SUPABASE_SECRET_KEY",
        context=f"{target.title()} super-admin bootstrap",
    )

    write_step(f"Bootstrapping super admin for {target}")
    run_command(
        [
            "npx",
            "tsx",
            "backend/scripts/bootstrap-super-admin.ts",
            "--supabase-url",
            env_values["SUPABASE_URL"],
            "--secret-key",
            env_values["SUPABASE_SECRET_KEY"],
            "--email",
            resolved_email,
            "--password-stdin",
            "--user-name",
            (user_name or "").strip() or DEFAULT_BOOTSTRAP_SUPER_ADMIN_USER_NAME,
            "--display-name",
            (display_name or "").strip() or DEFAULT_BOOTSTRAP_SUPER_ADMIN_DISPLAY_NAME,
            "--first-name",
            (first_name or "").strip() or DEFAULT_BOOTSTRAP_SUPER_ADMIN_FIRST_NAME,
            "--last-name",
            (last_name or "").strip() or DEFAULT_BOOTSTRAP_SUPER_ADMIN_LAST_NAME,
        ],
        cwd=config.repo_root,
        env=os.environ.copy(),
        input_data=password,
    )


def deploy_migration_target(
    config: DevConfig,
    *,
    target: str,
    source_branch: str | None,
    force: bool,
    upgrade: bool,
    preflight_only: bool,
    dry_run_only: bool,
) -> None:
    """Deploy the maintained stack to the requested hosted target."""

    if target not in {"staging", "production"}:
        raise DevCliError(f"Unsupported deploy target: {target}")

    assert_command_available("git")
    assert_command_available("npm")
    ensure_migration_workspace_scaffolding(config)
    install_migration_workspace_dependencies(config)

    env_values = {
        **collect_present_environment_values(*OPTIONAL_DEPLOY_ENV_NAMES),
        **require_environment_values(
            *resolve_deploy_required_environment_names(target=target),
            context=f"{target.title()} deployment",
        ),
    }
    subprocess_env = build_deploy_subprocess_environment(env_values)
    resolved_source_branch = resolve_deploy_source_branch(config, explicit_source_branch=source_branch)

    run_deploy_preflight(config, target=target, env_values=env_values, subprocess_env=subprocess_env)
    if preflight_only:
        return

    run_deploy_dry_run(config, target=target, env_values=env_values, subprocess_env=subprocess_env)
    if dry_run_only:
        return

    fingerprint = build_deploy_fingerprint(
        config,
        target=target,
        source_branch=resolved_source_branch,
        env_values=env_values,
    )
    completed_stages, _ = normalize_deploy_stage_state(
        config,
        target=target,
        fingerprint=fingerprint,
        force=force,
        upgrade=upgrade,
    )
    worker_config_path = get_deploy_worker_config_path(config, target=target, env_values=env_values)

    for stage_name in DEPLOY_TRANSACTIONAL_STAGES:
        if stage_name in completed_stages:
            write_step(f"Skipping completed deploy stage: {stage_name}")
            continue

        try:
            if stage_name == "supabase_config":
                run_supabase_remote_config_push(config, env_values=env_values, subprocess_env=subprocess_env)
            elif stage_name == "supabase_schema":
                run_supabase_link(config, env_values=env_values, subprocess_env=subprocess_env)
                run_supabase_remote_push(config, subprocess_env=subprocess_env)
                assert_hosted_required_schema(env_values)
            elif stage_name == "supabase_storage":
                run_supabase_bucket_provisioning(config, env_values=env_values, subprocess_env=subprocess_env)
            elif stage_name == "supabase_demo_seed":
                run_supabase_hosted_demo_seeding(
                    config,
                    target=target,
                    env_values=env_values,
                    subprocess_env=subprocess_env,
                )
            elif stage_name == "pages_project":
                ensure_cloudflare_pages_project(config, target=target, env=subprocess_env)
            elif stage_name == "workers_deploy":
                write_step(f"Deploying Cloudflare Workers bundle for {target}")
                run_workers_deploy(config, worker_config_path=worker_config_path, subprocess_env=subprocess_env)
                for secret_name in ("SUPABASE_SECRET_KEY", "TURNSTILE_SECRET_KEY", "BREVO_API_KEY", "DEPLOY_SMOKE_SECRET"):
                    sync_worker_secret(
                        config,
                        worker_config_path=worker_config_path,
                        secret_name=secret_name,
                        secret_value=env_values[secret_name],
                        subprocess_env=subprocess_env,
                    )
            elif stage_name == "pages_deploy":
                write_step(f"Deploying Cloudflare Pages bundle for {target}")
                pages_alias_target = run_pages_deploy(
                    config,
                    target=target,
                    source_branch=resolved_source_branch,
                    subprocess_env=subprocess_env,
                )
                finalize_pages_custom_domain(env_values, target=target, alias_target=pages_alias_target)
            else:
                raise DevCliError(f"Unknown deploy stage: {stage_name}")
        except DevCliError as ex:
            guidance = get_deploy_stage_failure_guidance(stage_name=stage_name, target=target)
            raise DevCliError(
                f"Deployment stage '{stage_name}' failed.\n"
                f"{guidance}\n"
                f"Original error: {ex}"
            ) from ex

        update_deploy_stage_completion(
            config,
            target=target,
            fingerprint=fingerprint,
            completed_stages=completed_stages,
            stage_name=stage_name,
        )

    run_workers_deploy_smoke(config, target=target, env_values=env_values)
    run_pages_deploy_smoke(target=target, env_values=env_values)


def run_environment_file_command(
    config: DevConfig,
    *,
    target: str,
    copy_example: bool,
    open_file: bool,
    sync_github_environment: bool,
    github_environment: str | None,
    github_repo: str | None,
) -> None:
    """Inspect or bootstrap a root-managed environment file."""

    env_path = get_environment_file_path(config, target=target)
    example_path = get_environment_example_path(config, target=target)

    if copy_example and not env_path.exists():
        env_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(example_path, env_path)
        print(f"Created environment file from example: {env_path}")
    elif copy_example and env_path.exists():
        print(f"Environment file already exists: {env_path}")

    print(f"Environment file: {env_path}")
    print(f"Example template: {example_path}")
    print(f"Exists: {'yes' if env_path.exists() else 'no'}")

    if open_file:
        if not env_path.exists():
            raise DevCliError(
                f"Environment file does not exist yet: {env_path}\n"
                f"Create it from the example first or rerun with 'python ./scripts/dev.py env {target} --copy-example'."
            )
        open_environment_file(env_path)

    if sync_github_environment:
        sync_root_environment_file_to_github_environment(
            config,
            target=target,
            github_environment=github_environment,
            github_repo=github_repo,
        )


def is_github_environment_secret(name: str) -> bool:
    """Return whether the named environment key should be stored as a GitHub Environment secret."""

    return name in GITHUB_ENVIRONMENT_SECRET_NAMES


def sync_root_environment_file_to_github_environment(
    config: DevConfig,
    *,
    target: str,
    github_environment: str | None,
    github_repo: str | None,
) -> None:
    """Publish the checked-out root environment file into the matching GitHub Environment."""

    if target == "local":
        raise DevCliError("GitHub Environment sync is supported only for hosted targets, not local.")

    github_cli_executable = resolve_github_cli_executable()
    env_path = get_environment_file_path(config, target=target)
    if not env_path.exists():
        raise DevCliError(
            f"Environment file does not exist yet: {env_path}\n"
            f"Create it from the example first or rerun with 'python ./scripts/dev.py env {target} --copy-example'."
        )

    target_environment = (github_environment or target).strip()
    if not target_environment:
        raise DevCliError("GitHub Environment name cannot be blank.")

    subprocess_env = build_subprocess_env()
    auth_status = run_command(
        [github_cli_executable, "auth", "status"],
        cwd=config.repo_root,
        env=subprocess_env,
        check=False,
        capture_output=True,
    )
    if auth_status.returncode != 0:
        detail = ((auth_status.stderr or "").strip() or (auth_status.stdout or "").strip()) or "GitHub CLI is not authenticated."
        raise DevCliError(f"Unable to sync GitHub Environment values because gh auth is unavailable.\n{detail}")

    parsed = parse_env_assignments(env_path.read_text(encoding="utf-8"))
    if not parsed:
        raise DevCliError(f"Environment file is empty: {env_path}")

    repo_flag = ["--repo", github_repo.strip()] if github_repo and github_repo.strip() else []
    synced_variables: list[str] = []
    synced_secrets: list[str] = []
    skipped_blank: list[str] = []

    write_step(f"Syncing {env_path.name} into GitHub Environment '{target_environment}'")
    for key, value in parsed.items():
        trimmed_value = value.strip()
        if not trimmed_value:
            skipped_blank.append(key)
            continue

        if is_github_environment_secret(key):
            run_command(
                [github_cli_executable, "secret", "set", key, "--env", target_environment, *repo_flag],
                cwd=config.repo_root,
                env=subprocess_env,
                input_data=value,
            )
            synced_secrets.append(key)
            continue

        run_command(
            [github_cli_executable, "variable", "set", key, "--env", target_environment, "--body", value, *repo_flag],
            cwd=config.repo_root,
            env=subprocess_env,
        )
        synced_variables.append(key)

    print(
        f"Synced GitHub Environment '{target_environment}'"
        + (f" in repo '{github_repo.strip()}'" if github_repo and github_repo.strip() else "")
        + f": {len(synced_variables)} variable(s), {len(synced_secrets)} secret(s)."
    )
    if skipped_blank:
        print("Skipped blank values: " + ", ".join(skipped_blank))


def infer_github_repo_from_origin(config: DevConfig) -> str:
    """Infer the GitHub owner/name slug from the local origin remote."""

    result = run_command(
        ["git", "config", "--get", "remote.origin.url"],
        cwd=config.repo_root,
        capture_output=True,
    )
    remote_url = result.stdout.strip()
    if not remote_url:
        raise DevCliError("Unable to infer the GitHub repo because remote.origin.url is empty.")

    match = re.search(r"github\.com[:/](?P<slug>[^/\s]+/[^/\s]+?)(?:\.git)?$", remote_url)
    if not match:
        raise DevCliError(
            f"Unable to infer the GitHub repo from remote.origin.url: {remote_url}\n"
            "Use a GitHub remote URL or update the repo-origin parsing logic."
        )

    return match.group("slug")


def get_github_environment_variables(config: DevConfig, *, repo_slug: str, environment_name: str) -> dict[str, str]:
    """Return the current GitHub Environment variables for the target environment."""

    github_cli_executable = resolve_github_cli_executable()
    path = (
        f"repos/{repo_slug}/environments/{urllib.parse.quote(environment_name, safe='')}"
        "/variables?per_page=100"
    )
    result = run_command(
        [github_cli_executable, "api", path],
        cwd=config.repo_root,
        capture_output=True,
    )
    payload = json.loads(result.stdout)
    variables = payload.get("variables")
    if not isinstance(variables, list):
        raise DevCliError(f"Unexpected GitHub Environment variables payload for '{environment_name}'.")

    parsed: dict[str, str] = {}
    for variable in variables:
        if not isinstance(variable, dict):
            continue
        name = variable.get("name")
        value = variable.get("value")
        if isinstance(name, str) and isinstance(value, str):
            parsed[name] = value
    return parsed


def get_github_environment_secret_names(config: DevConfig, *, repo_slug: str, environment_name: str) -> set[str]:
    """Return the current GitHub Environment secret names for the target environment."""

    github_cli_executable = resolve_github_cli_executable()
    path = (
        f"repos/{repo_slug}/environments/{urllib.parse.quote(environment_name, safe='')}"
        "/secrets?per_page=100"
    )
    result = run_command(
        [github_cli_executable, "api", path],
        cwd=config.repo_root,
        capture_output=True,
    )
    payload = json.loads(result.stdout)
    secrets = payload.get("secrets")
    if not isinstance(secrets, list):
        raise DevCliError(f"Unexpected GitHub Environment secrets payload for '{environment_name}'.")

    names: set[str] = set()
    for secret in secrets:
        if not isinstance(secret, dict):
            continue
        name = secret.get("name")
        if isinstance(name, str):
            names.add(name)
    return names


def assert_github_environment_sync(config: DevConfig, *, target: str) -> None:
    """Ensure the checked-out deploy env file is reflected in the matching GitHub Environment."""

    if target not in {"staging", "production"}:
        return
    if os.environ.get("GITHUB_ACTIONS", "").strip().lower() == "true":
        print("Skipping GitHub Environment sync preflight inside GitHub Actions.")
        return

    github_cli_executable = resolve_github_cli_executable()
    auth_status = run_command(
        [github_cli_executable, "auth", "status"],
        cwd=config.repo_root,
        check=False,
        capture_output=True,
    )
    if auth_status.returncode != 0:
        detail = ((auth_status.stderr or "").strip() or (auth_status.stdout or "").strip()) or "GitHub CLI is not authenticated."
        raise DevCliError(
            "GitHub Environment sync preflight requires an authenticated gh session.\n"
            f"{detail}"
        )

    env_path = get_environment_file_path(config, target=target)
    if not env_path.exists():
        raise DevCliError(f"GitHub Environment sync preflight requires an existing environment file: {env_path}")

    repo_slug = infer_github_repo_from_origin(config)
    environment_name = target
    environment_path = f"repos/{repo_slug}/environments/{urllib.parse.quote(environment_name, safe='')}"
    run_command([github_cli_executable, "api", environment_path], cwd=config.repo_root, capture_output=True)

    expected = {
        key: value.strip()
        for key, value in parse_env_assignments(env_path.read_text(encoding="utf-8")).items()
        if value.strip()
    }
    expected_variables = {key: value for key, value in expected.items() if not is_github_environment_secret(key)}
    expected_secrets = {key for key in expected if is_github_environment_secret(key)}

    actual_variables = get_github_environment_variables(config, repo_slug=repo_slug, environment_name=environment_name)
    actual_secret_names = get_github_environment_secret_names(config, repo_slug=repo_slug, environment_name=environment_name)

    missing_variables = sorted(name for name in expected_variables if name not in actual_variables)
    mismatched_variables = sorted(name for name, value in expected_variables.items() if actual_variables.get(name) != value)
    missing_secrets = sorted(name for name in expected_secrets if name not in actual_secret_names)

    if missing_variables or mismatched_variables or missing_secrets:
        details: list[str] = []
        if missing_variables:
            details.append("missing vars: " + ", ".join(missing_variables))
        if mismatched_variables:
            details.append("mismatched vars: " + ", ".join(mismatched_variables))
        if missing_secrets:
            details.append("missing secrets: " + ", ".join(missing_secrets))
        raise DevCliError(
            f"GitHub Environment '{environment_name}' is not synced with {env_path.name}.\n"
            + "\n".join(details)
            + f"\nRerun: python ./scripts/dev.py env {target} --sync-github-environment"
        )

    print(
        f"GitHub Environment '{environment_name}' matches {env_path.name} for "
        f"{len(expected_variables)} variable(s) and {len(expected_secrets)} secret name(s)."
    )
    if expected_secrets:
        print("Secret presence was verified by name only; GitHub does not expose secret values for comparison.")


def get_api_root(config: DevConfig) -> Path:
    """Resolve the API submodule root path.

    Args:
        config: CLI configuration containing the API root path.

    Returns:
        The resolved API submodule root path.
    """

    return config.repo_root / config.api_root


def resolve_postman_api_key(postman_api_key: str | None) -> str:
    """Resolve a Postman API key from the argument or environment.

    Args:
        postman_api_key: Explicit CLI override value, if provided.

    Returns:
        A non-empty Postman API key string.

    Raises:
        DevCliError: If no API key is available.
    """

    api_key = (postman_api_key or os.environ.get("POSTMAN_API_KEY", "")).strip()
    if not api_key:
        raise DevCliError(
            "POSTMAN_API_KEY is required. Pass --postman-api-key or set the POSTMAN_API_KEY environment variable."
        )
    return api_key


def login_postman_cli(config: DevConfig, *, postman_api_key: str | None) -> None:
    """Authenticate Postman CLI from the root developer entry point.

    Args:
        config: CLI configuration containing API asset paths.
        postman_api_key: Optional Postman API key override.

    Returns:
        None.

    Raises:
        DevCliError: If Postman CLI is unavailable or no API key is available.
    """

    assert_command_available("postman")
    api_root = get_api_root(config)
    api_key = resolve_postman_api_key(postman_api_key)

    write_step("Authenticating Postman CLI with API key")
    run_command(["postman", "login", "--with-api-key", api_key], cwd=api_root)


def run_api_spec_lint(config: DevConfig) -> None:
    """Lint the Git-tracked OpenAPI specification with Redocly CLI.

    Args:
        config: CLI configuration containing API asset paths.

    Returns:
        None.

    Raises:
        DevCliError: If `npx` is unavailable or linting fails.
    """

    assert_command_available("npx")
    spec_path = config.repo_root / config.api_spec

    write_step("Linting API specification with Redocly CLI")
    result = run_command(
        [
            "npx",
            "--yes",
            f"@redocly/cli@{REDOCLY_CLI_VERSION}",
            "lint",
            str(spec_path),
            "--skip-rule",
            "info-license",
            "--skip-rule",
            "no-server-example.com",
            "--skip-rule",
            "operation-4xx-response",
            "--skip-rule",
            "operation-2xx-response",
        ],
        cwd=config.repo_root,
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        combined_output = "\n".join(
            part.strip()
            for part in ((result.stdout or ""), (result.stderr or ""))
            if part and part.strip()
        )
        normalized_output = combined_output.lower()
        if (
            "your api description is valid" in normalized_output
            and "assertion failed: !(handle->flags & uv_handle_closing)" in normalized_output
        ):
            print_console_text(combined_output)
            print("OpenAPI spec lint passed. Ignoring known Redocly Windows shutdown assertion after successful validation.")
            return
        raise DevCliError("Redocly OpenAPI lint failed." + (f"\n{combined_output}" if combined_output else ""))
    print("OpenAPI spec lint passed.")


def run_api_contract_tests(
    config: DevConfig,
    *,
    environment_path: Path,
    base_url: str,
    contract_execution_mode: str,
    report_path: Path,
    lint_spec: bool,
    start_workers: bool,
    developer_token: str | None,
    moderator_token: str | None,
    developer_email: str | None,
    moderator_email: str | None,
    seed_user_password: str | None,
) -> None:
    """Run the Git-tracked Postman contract test collection with Postman CLI.

    Args:
        config: CLI configuration containing API asset paths.
        environment_path: Environment template path to use for the run. The
            committed local template intentionally ships with placeholder auth
            and resource identifiers, so authenticated success-path requests are
            skipped until a developer supplies real local values.
        base_url: Runtime base URL override.
        contract_execution_mode: `live` or `mock`.
        report_path: JUnit report output path.
        lint_spec: Whether to lint the spec before running the collection.
        start_workers: Whether to start the local Supabase + Workers stack automatically for the run.
        developer_token: Optional developer bearer token override for authenticated contract checks.
        moderator_token: Optional moderator bearer token override for moderation contract checks.
        developer_email: Optional seeded developer email used to fetch a local access token automatically.
        moderator_email: Optional seeded moderator email used to fetch a local access token automatically.
        seed_user_password: Optional seeded auth password used to fetch local access tokens automatically.
    Returns:
        None.

    Raises:
        DevCliError: If required files or tools are unavailable or the contract run fails.
    """

    assert_command_available("postman")
    api_root = get_api_root(config)
    collection_path = config.repo_root / config.api_contract_collection
    if not collection_path.exists():
        raise DevCliError(f"Postman contract collection not found: {collection_path}")
    if not environment_path.exists():
        raise DevCliError(f"Postman environment not found: {environment_path}")

    if lint_spec:
        run_api_spec_lint(config)

    report_path.parent.mkdir(parents=True, exist_ok=True)

    workers_process: subprocess.Popen | None = None
    runtime_env: dict[str, str] | None = None
    resolved_base_url = base_url
    resolved_developer_token = (developer_token or "").strip()
    resolved_moderator_token = (moderator_token or "").strip()

    if start_workers:
        if base_url != config.migration_workers_base_url and not is_local_http_url(base_url):
            raise DevCliError("--start-workers can only be used with the local Workers base URL.")
        run_supabase_stack_command(config, action="start")
        run_supabase_stack_command(config, action="db-reset")
        runtime_env = get_local_supabase_runtime(config)
        resolved_base_url = config.migration_workers_base_url
        write_step("Starting Workers API in the background for contract tests")
        workers_process, workers_log_path = start_migration_workers_process(config, runtime_env=runtime_env)
        print(f"Workers API log: {workers_log_path}")
    else:
        ensure_api_base_url_reachable(resolved_base_url)

    if runtime_env is None and is_local_http_url(resolved_base_url):
        try:
            runtime_env = get_local_supabase_runtime(config)
        except DevCliError:
            runtime_env = None

    if runtime_env is not None:
        resolved_developer_email = developer_email or (LOCAL_SEED_DEVELOPER_EMAIL if start_workers else None)
        resolved_moderator_email = moderator_email or (LOCAL_SEED_MODERATOR_EMAIL if start_workers else None)
        resolved_seed_password = seed_user_password or LOCAL_SEED_DEFAULT_PASSWORD

        if resolved_developer_email and not resolved_developer_token:
            resolved_developer_token = fetch_supabase_access_token(
                supabase_url=runtime_env["SUPABASE_URL"],
                publishable_key=runtime_env["SUPABASE_PUBLISHABLE_KEY"],
                email=resolved_developer_email,
                password=resolved_seed_password,
            )

        if resolved_moderator_email and not resolved_moderator_token:
            resolved_moderator_token = fetch_supabase_access_token(
                supabase_url=runtime_env["SUPABASE_URL"],
                publishable_key=runtime_env["SUPABASE_PUBLISHABLE_KEY"],
                email=resolved_moderator_email,
                password=resolved_seed_password,
            )

    write_step("Running API contract tests with Postman CLI")
    try:
        env_vars = [
            "--env-var",
            f"baseUrl={resolved_base_url}",
            "--env-var",
            f"contractExecutionMode={contract_execution_mode}",
        ]
        if resolved_developer_token:
            env_vars.extend(["--env-var", f"developerAccessToken={resolved_developer_token}"])
        if resolved_moderator_token:
            env_vars.extend(["--env-var", f"moderatorAccessToken={resolved_moderator_token}"])

        run_command(
            [
                "postman",
                "collection",
                "run",
                str(collection_path),
                "--environment",
                str(environment_path),
                *env_vars,
                "--bail",
                "failure",
                "--reporters",
                "cli,junit",
                "--reporter-junit-export",
                str(report_path),
                "--working-dir",
                str(api_root),
                *(["--insecure"] if is_local_http_url(resolved_base_url) and is_https_url(resolved_base_url) else []),
            ],
            cwd=api_root,
        )
    finally:
        if workers_process is not None:
            write_step("Stopping background Workers API")
            stop_background_process(workers_process)


def provision_api_mock(
    config: DevConfig,
    *,
    admin_environment_path: Path,
    mode: str,
    postman_api_key: str | None,
) -> None:
    """Provision a Postman mock server from the Git-tracked contract collection.

    Args:
        config: CLI configuration containing API asset paths.
        admin_environment_path: Mock admin environment template path.
        mode: Provisioning mode (`shared` or `ephemeral`).
        postman_api_key: Postman API key to pass to the provisioning script.

    Returns:
        None.

    Raises:
        DevCliError: If Node.js is unavailable, required files are missing, or the script fails.
    """

    assert_command_available("node")
    api_root = get_api_root(config)
    collection_path = config.repo_root / config.api_contract_collection
    script_path = config.repo_root / config.api_mock_provision_script

    if not script_path.exists():
        raise DevCliError(f"Mock provisioning script not found: {script_path}")
    if not admin_environment_path.exists():
        raise DevCliError(f"Mock admin environment not found: {admin_environment_path}")
    if not collection_path.exists():
        raise DevCliError(f"Postman contract collection not found: {collection_path}")

    api_key = resolve_postman_api_key(postman_api_key)

    write_step(f"Provisioning Postman mock ({mode}) from the Git-tracked contract collection")
    run_command(
        [
            "node",
            str(script_path),
            "--admin-env",
            str(admin_environment_path),
            "--collection",
            str(collection_path),
            "--mode",
            mode,
        ],
        cwd=api_root,
        env=build_subprocess_env(extra={"POSTMAN_API_KEY": api_key}),
    )


def sync_api_workspace(config: DevConfig, *, postman_api_key: str | None, reprovision_shared_mock: bool) -> None:
    """Push Native Git artifacts to Postman Cloud and optionally reprovision the shared mock.

    Args:
        config: CLI configuration containing API asset paths.
        postman_api_key: Optional Postman API key used for login and provisioning.
        reprovision_shared_mock: Whether to reprovision the shared mock after the workspace push.

    Returns:
        None.

    Raises:
        DevCliError: If required tools are unavailable or sync/provisioning fails.
    """

    assert_command_available("postman")
    api_root = get_api_root(config)
    api_key = (postman_api_key or os.environ.get("POSTMAN_API_KEY", "")).strip() or None

    if api_key:
        login_postman_cli(config, postman_api_key=api_key)
    else:
        print("No POSTMAN_API_KEY provided; using the current Postman CLI login session if available.")

    write_step("Preparing Postman Native Git workspace metadata")
    run_command(["postman", "workspace", "prepare"], cwd=api_root)

    write_step("Pushing Native Git workspace artifacts to Postman Cloud")
    run_command(["postman", "workspace", "push", "--yes"], cwd=api_root)

    if reprovision_shared_mock:
        if not api_key:
            print(
                "Skipping shared mock reprovision because POSTMAN_API_KEY was not provided. "
                "The workspace sync succeeded; rerun with --postman-api-key or set POSTMAN_API_KEY if you also want to reprovision the shared mock."
            )
            return
        provision_api_mock(
            config,
            admin_environment_path=config.repo_root / config.api_mock_admin_environment,
            mode="shared",
            postman_api_key=api_key,
        )


def run_doctor(config: DevConfig) -> None:
    """Run environment diagnostics for local tooling and repo state.

    Args:
        config: CLI configuration containing repository and maintained stack paths.

    Returns:
        None.
    """

    issues: list[str] = []
    optional_issues: list[str] = []

    write_step("Environment checks")
    for cmd in ("git", "docker", "python", "node", "npm"):
        if shutil.which(cmd):
            print(f"Found: {cmd}")
        else:
            print(f"Missing command: {cmd}")
            issues.append(f"Required command missing from PATH: {cmd}")

    for cmd in ("postman",):
        if shutil.which(cmd):
            print(f"Found (API/frontend workflow): {cmd}")
        else:
            print(f"Missing optional API/frontend workflow command: {cmd}")
            optional_issues.append(
                f"Optional API/frontend workflow command missing from PATH: {cmd}"
            )

    if shutil.which("supabase") or shutil.which("npx"):
        print("Found (stack workflow): supabase")
    else:
        print("Missing optional stack workflow command: supabase")
        optional_issues.append(
            "Optional stack workflow command missing from PATH: supabase (or npx fallback)"
        )

    local_wrangler_path = config.repo_root / "node_modules" / ".bin" / ("wrangler.cmd" if os.name == "nt" else "wrangler")
    if shutil.which("wrangler") or local_wrangler_path.exists():
        print("Found (stack workflow): wrangler")
    else:
        print("Missing optional stack workflow command: wrangler")
        optional_issues.append(
            "Optional stack workflow command missing from PATH: wrangler (run `python ./scripts/dev.py bootstrap` to install workspace tooling)"
        )

    for label, path in get_maintained_submodule_paths(config):
        if not test_submodule_initialized(path):
            issues.append(f"{label} submodule is not initialized (run: git submodule update --init --recursive)")

    if shutil.which("git"):
        write_step("Submodule status")
        run_command(["git", "submodule", "status"], cwd=config.repo_root, check=False, capture_output=False)

    if shutil.which("docker"):
        write_step("Docker version")
        result = run_command(["docker", "--version"], check=False, capture_output=False)
        if result.returncode != 0:
            issues.append("docker is installed but `docker --version` failed")
        daemon_check = run_command(["docker", "info"], check=False, capture_output=True, text=True)
        if daemon_check.returncode != 0:
            issues.append("Docker daemon is not reachable (start Docker Desktop/Engine)")

    maintained_paths = [
        ("Migration root package", config.repo_root / config.migration_root_package_json),
        ("Frontend workspace", config.repo_root / config.migration_spa_root),
        ("Frontend package manifest", config.repo_root / config.frontend_package_json),
        ("Workers workspace", config.repo_root / config.migration_workers_root),
        ("Workers Wrangler config", config.repo_root / config.migration_workers_root / "wrangler.jsonc"),
        ("Supabase project root", config.repo_root / config.supabase_root),
        ("Supabase config", config.repo_root / config.supabase_root / "config.toml"),
    ]
    write_step("Maintained stack paths")
    for label, path in maintained_paths:
        if path.exists():
            print(f"{label} found: {path}")
        else:
            print(f"{label} missing: {path}")
            issues.append(f"{label} not found: {path}")

    print()
    write_step("Doctor summary")
    if issues:
        print(f"FAIL ({len(issues)} issue(s) detected)")
        for idx, issue in enumerate(issues, start=1):
            print(f"{idx}. {issue}")
        print()
        print("Suggested next steps:")
        print("  python ./scripts/dev.py bootstrap")
        print("  python ./scripts/dev.py database up")
        print("  python ./scripts/dev.py auth up")
        print("  python ./scripts/dev.py api")
        print("  python ./scripts/dev.py web --hot-reload")
        print("  python ./scripts/dev.py all-tests")
        print("  python ./scripts/dev.py verify --start-workers")
        print("  python ./scripts/dev.py api-test --start-workers --skip-lint")
        print("  python ./scripts/dev.py database status")
        print("  python ./scripts/dev.py web status")
    else:
        print("PASS (no issues detected)")
        if optional_issues:
            print()
            print("Optional API workflow notes:")
            for idx, issue in enumerate(optional_issues, start=1):
                print(f"{idx}. {issue}")
        print()
        print("Suggested next steps:")
        print("  python ./scripts/dev.py bootstrap")
        print("  python ./scripts/dev.py database up")
        print("  python ./scripts/dev.py auth up")
        print("  python ./scripts/dev.py api")
        print("  python ./scripts/dev.py web --hot-reload")
        print("  python ./scripts/dev.py all-tests")
        print("  python ./scripts/dev.py verify --start-workers")
        print("  python ./scripts/dev.py api-test --start-workers --skip-lint")
        print("  python ./scripts/dev.py api-lint")
        print("  python ./scripts/dev.py database status")
        print("  python ./scripts/dev.py web status")


def run_verify(
    config: DevConfig,
    *,
    run_integration: bool,
    run_contract_tests: bool,
    environment_path: Path,
    base_url: str,
    contract_execution_mode: str,
    report_path: Path,
    start_workers: bool,
) -> None:
    """Run the main developer verification workflow from the repository root.

    Args:
        config: CLI configuration containing backend and API paths.
        run_integration: Whether to include integration tests.
        run_contract_tests: Whether to include API contract tests.
        environment_path: Environment file path for contract runs.
        base_url: Base URL used for contract execution.
        contract_execution_mode: Contract execution mode (`live` or `mock`).
        report_path: JUnit report output path for Postman CLI.
        start_workers: Whether to auto-start the Workers stack for contract runs.

    Returns:
        None.
    """

    restore_backend(config)
    run_migration_typecheck(config, restore=False)
    run_tests(config, run_integration=run_integration, restore=False)
    run_frontend_tests(config, restore=False)
    run_root_python_tests(config)
    run_api_spec_lint(config)

    if not run_contract_tests:
        print("Skipping API contract tests.")
        return

    run_api_contract_tests(
        config,
        environment_path=environment_path,
        base_url=base_url,
        contract_execution_mode=contract_execution_mode,
        report_path=report_path,
        lint_spec=False,
        start_workers=start_workers,
        developer_token=None,
        moderator_token=None,
        developer_email=LOCAL_SEED_DEVELOPER_EMAIL,
        moderator_email=LOCAL_SEED_MODERATOR_EMAIL,
        seed_user_password=LOCAL_SEED_DEFAULT_PASSWORD,
    )
    run_contract_smoke(
        config,
        base_url=base_url,
        start_workers=start_workers,
        token=None,
        player_token=None,
        moderator_token=None,
        developer_token=None,
        player_email=LOCAL_SEED_PLAYER_EMAIL,
        seed_user_email=LOCAL_SEED_DEVELOPER_EMAIL,
        moderator_email=LOCAL_SEED_MODERATOR_EMAIL,
        seed_user_password=LOCAL_SEED_DEFAULT_PASSWORD,
    )
    run_workers_flow_smoke_command(
        config,
        start_stack=start_workers,
        base_url=base_url,
        player_email=LOCAL_SEED_PLAYER_EMAIL,
        moderator_email=LOCAL_SEED_MODERATOR_EMAIL,
        developer_email=LOCAL_SEED_DEVELOPER_EMAIL,
        seed_password=LOCAL_SEED_DEFAULT_PASSWORD,
    )


def run_all_tests(
    config: DevConfig,
    *,
    bootstrap: bool,
    environment_path: Path,
    base_url: str,
    contract_execution_mode: str,
    report_path: Path,
    start_workers: bool,
) -> None:
    """Run the full cross-repository validation workflow in one command.

    Args:
        config: CLI configuration containing backend, frontend, and API paths.
        bootstrap: Whether to initialize submodules first when needed.
        environment_path: Postman environment file for contract runs.
        base_url: Base URL used for API contract execution.
        contract_execution_mode: Contract execution mode (`live` or `mock`).
        report_path: JUnit report output path for Postman CLI contract runs.
        start_workers: Whether to auto-start the Workers stack for contract runs.

    Returns:
        None.
    """

    if bootstrap:
        ensure_submodules(config)

    restore_backend(config)
    run_migration_typecheck(config, restore=False)
    run_tests(config, run_integration=True, restore=False)
    run_root_python_tests(config)

    restore_frontend(config)
    run_frontend_tests(config, restore=False)

    run_api_spec_lint(config)
    run_api_contract_tests(
        config,
        environment_path=environment_path,
        base_url=base_url,
        contract_execution_mode=contract_execution_mode,
        report_path=report_path,
        lint_spec=False,
        start_workers=start_workers,
        developer_token=None,
        moderator_token=None,
        developer_email=LOCAL_SEED_DEVELOPER_EMAIL,
        moderator_email=LOCAL_SEED_MODERATOR_EMAIL,
        seed_user_password=LOCAL_SEED_DEFAULT_PASSWORD,
    )
    run_contract_smoke(
        config,
        base_url=base_url,
        start_workers=start_workers,
        token=None,
        player_token=None,
        moderator_token=None,
        developer_token=None,
        player_email=LOCAL_SEED_PLAYER_EMAIL,
        seed_user_email=LOCAL_SEED_DEVELOPER_EMAIL,
        moderator_email=LOCAL_SEED_MODERATOR_EMAIL,
        seed_user_password=LOCAL_SEED_DEFAULT_PASSWORD,
    )
    run_workers_flow_smoke_command(
        config,
        start_stack=start_workers,
        base_url=base_url,
        player_email=LOCAL_SEED_PLAYER_EMAIL,
        moderator_email=LOCAL_SEED_MODERATOR_EMAIL,
        developer_email=LOCAL_SEED_DEVELOPER_EMAIL,
        seed_password=LOCAL_SEED_DEFAULT_PASSWORD,
    )


LOCAL_SEED_DEFAULT_PASSWORD = "LocalDevOnly!234"
LOCAL_SEED_PLAYER_EMAIL = "ava.garcia@boardtpl.local"
LOCAL_SEED_MODERATOR_EMAIL = "alex.rivera@boardtpl.local"
LOCAL_SEED_DEVELOPER_EMAIL = "emma.torres@boardtpl.local"


def build_parser() -> argparse.ArgumentParser:
    """Construct the CLI parser with typed subcommands and shared options.

    Args:
        None.

    Returns:
        Configured top-level ``argparse.ArgumentParser`` instance.
    """

    parser = argparse.ArgumentParser(
        description="Developer automation CLI for local backend/frontend/API workflows.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    shared = argparse.ArgumentParser(add_help=False)

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "bootstrap",
        parents=[shared],
        help="Initialize submodules and install maintained workspace dependencies",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    subparsers.add_parser(
        "clean-all",
        parents=[shared],
        help="Run all local clean operations from web down through database",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    database = subparsers.add_parser(
        "database",
        parents=[shared],
        help="Manage the local database-only runtime profile",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    database.add_argument(
        "action",
        choices=("up", "down", "status", "clean"),
        nargs="?",
        default="up",
        help="Database runtime action",
    )
    database.add_argument(
        "--include-dependencies",
        action="store_true",
        help="Retained for command symmetry; the database profile has no lower-level local dependencies",
    )

    auth = subparsers.add_parser(
        "auth",
        parents=[shared],
        help="Manage the local database + auth runtime profile",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    auth.add_argument(
        "action",
        choices=("up", "down", "status", "clean"),
        nargs="?",
        default="up",
        help="Auth runtime action",
    )
    auth.add_argument(
        "--include-dependencies",
        action="store_true",
        help="Include lower-level dependency handling/status output for the database runtime",
    )

    api = subparsers.add_parser(
        "api",
        parents=[shared],
        help="Manage the local database + auth + backend runtime profile",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    api.add_argument(
        "action",
        choices=("up", "down", "status", "clean"),
        nargs="?",
        default="up",
        help="API runtime action",
    )
    api.add_argument(
        "--include-dependencies",
        action="store_true",
        help="Include auth and database dependency handling/status output",
    )
    api.add_argument(
        "--bootstrap",
        "-Bootstrap",
        action="store_true",
        help="Run submodule initialization checks before startup",
    )
    api.add_argument(
        "--skip-install",
        "-SkipInstall",
        action="store_true",
        help="Skip npm workspace installation before backend startup",
    )

    web = subparsers.add_parser(
        "web",
        parents=[shared],
        help="Manage the full local database + auth + backend + frontend runtime profile",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    web.add_argument(
        "action",
        choices=("up", "down", "status", "clean"),
        nargs="?",
        default="up",
        help="Web runtime action",
    )
    web.add_argument(
        "--include-dependencies",
        action="store_true",
        help="Include API, auth, and database dependency handling/status output",
    )
    web.add_argument(
        "--bootstrap",
        "-Bootstrap",
        action="store_true",
        help="Run submodule initialization checks before startup",
    )
    web.add_argument(
        "--skip-install",
        "-SkipInstall",
        action="store_true",
        help="Skip npm workspace installation before startup",
    )
    web.add_argument(
        "--hot-reload",
        "-HotReload",
        action="store_true",
        help="Run Vite and Wrangler in their hot-reload dev modes while the stack is up",
    )
    web.add_argument(
        "--landing-mode",
        action="store_true",
        help="Start the SPA in landing-page-only mode for the production landing wave",
    )
    web.add_argument(
        "--no-browser",
        "-NoBrowser",
        action="store_true",
        help="Do not automatically open the frontend URL in the default browser",
    )
    test = subparsers.add_parser(
        "test",
        parents=[shared],
        help="Run backend unit tests and optionally integration tests",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    test.add_argument("--skip-integration", "-SkipIntegration", action="store_true", help="Skip integration tests")

    all_tests = subparsers.add_parser(
        "all-tests",
        parents=[shared],
        help="Run maintained backend tests, root CLI tests, frontend tests, API lint, and API contract tests",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    all_tests.add_argument(
        "--bootstrap",
        "-Bootstrap",
        action="store_true",
        help="Run submodule initialization checks before validation",
    )
    all_tests.add_argument(
        "--environment",
        default="api/postman/environments/board-enthusiasts_local.postman_environment.json",
        help="Postman environment file path used for contract tests",
    )
    all_tests.add_argument(
        "--base-url",
        "-BaseUrl",
        default="http://127.0.0.1:8787",
        help="Base URL injected into contract test runs",
    )
    all_tests.add_argument(
        "--contract-execution-mode",
        "-ContractExecutionMode",
        choices=("live", "mock"),
        default="live",
        help="Contract execution mode variable value for Postman runs",
    )
    all_tests.add_argument(
        "--report-path",
        "-ReportPath",
        default="api/postman-cli-reports/all-tests-contract-tests.xml",
        help="JUnit report output path for Postman contract runs",
    )
    all_tests.add_argument(
        "--start-workers",
        action="store_true",
        help="Start the local Supabase + Workers stack automatically for contract tests",
    )

    verify = subparsers.add_parser(
        "verify",
        parents=[shared],
        help="Run maintained backend tests, root CLI tests, API lint, and optional contract tests",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    verify.add_argument("--skip-integration", "-SkipIntegration", action="store_true", help="Skip integration tests")
    verify.add_argument(
        "--skip-contract-tests",
        "-SkipContractTests",
        action="store_true",
        help="Skip API contract tests after backend/test/spec validation",
    )
    verify.add_argument(
        "--environment",
        default="api/postman/environments/board-enthusiasts_local.postman_environment.json",
        help="Postman environment file path used when contract tests run",
    )
    verify.add_argument(
        "--base-url",
        "-BaseUrl",
        default="http://127.0.0.1:8787",
        help="Base URL injected into contract test runs",
    )
    verify.add_argument(
        "--contract-execution-mode",
        "-ContractExecutionMode",
        choices=("live", "mock"),
        default="live",
        help="Contract execution mode variable value for Postman runs",
    )
    verify.add_argument(
        "--report-path",
        "-ReportPath",
        default="api/postman-cli-reports/verify-contract-tests.xml",
        help="JUnit report output path for Postman runs",
    )
    verify.add_argument(
        "--start-workers",
        action="store_true",
        help="Start the local Supabase + Workers stack automatically for contract tests",
    )

    subparsers.add_parser(
        "doctor",
        parents=[shared],
        help="Run local environment diagnostics",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    env_command = subparsers.add_parser(
        "env",
        parents=[shared],
        help="Inspect or bootstrap the root-managed environment files",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    env_command.add_argument(
        "target",
        choices=SUPPORTED_ENVIRONMENT_TARGETS,
        help="Environment file target to inspect",
    )
    env_command.add_argument(
        "--copy-example",
        action="store_true",
        help="Create the target environment file from its checked-in example when it does not exist",
    )
    env_command.add_argument(
        "--open",
        action="store_true",
        help="Open the target environment file in the platform default application",
    )
    env_command.add_argument(
        "--sync-github-environment",
        action="store_true",
        help="Publish the current target environment file into the matching GitHub Environment",
    )
    env_command.add_argument(
        "--github-environment",
        help="Override the GitHub Environment name instead of using the target name directly",
    )
    env_command.add_argument(
        "--repo",
        help="Optional GitHub repo override in owner/name form for gh commands",
    )

    bootstrap_super_admin = subparsers.add_parser(
        "bootstrap-super-admin",
        parents=[shared],
        help="Create or update the one-time super-admin account for a target environment",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    bootstrap_super_admin.add_argument(
        "target",
        choices=SUPPORTED_ENVIRONMENT_TARGETS,
        nargs="?",
        default="production",
        help="Environment whose Supabase project should receive the bootstrap account",
    )
    bootstrap_super_admin.add_argument(
        "--email",
        help="Super-admin email address; prompted when omitted",
    )
    bootstrap_super_admin.add_argument(
        "--user-name",
        default=DEFAULT_BOOTSTRAP_SUPER_ADMIN_USER_NAME,
        help="Projected BE user name for the super-admin account",
    )
    bootstrap_super_admin.add_argument(
        "--display-name",
        default=DEFAULT_BOOTSTRAP_SUPER_ADMIN_DISPLAY_NAME,
        help="Display name for the super-admin account",
    )
    bootstrap_super_admin.add_argument(
        "--first-name",
        default=DEFAULT_BOOTSTRAP_SUPER_ADMIN_FIRST_NAME,
        help="First name for the super-admin account",
    )
    bootstrap_super_admin.add_argument(
        "--last-name",
        default=DEFAULT_BOOTSTRAP_SUPER_ADMIN_LAST_NAME,
        help="Last name for the super-admin account",
    )

    api_login = subparsers.add_parser(
        "api-login",
        parents=[shared],
        help="Authenticate Postman CLI with a Postman API key",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    api_login.add_argument(
        "--postman-api-key",
        "-PostmanApiKey",
        default=None,
        help="Postman API key override (defaults to POSTMAN_API_KEY env var)",
    )

    subparsers.add_parser(
        "api-lint",
        parents=[shared],
        help="Lint the Git-tracked OpenAPI specification with Redocly CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    api_test = subparsers.add_parser(
        "api-test",
        parents=[shared],
        help="Run Git-tracked API contract tests with Postman CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    api_test.add_argument(
        "--environment",
        default="api/postman/environments/board-enthusiasts_local.postman_environment.json",
        help="Postman environment file path",
    )
    api_test.add_argument(
        "--base-url",
        "-BaseUrl",
        default="http://127.0.0.1:8787",
        help="Base URL injected into the collection run",
    )
    api_test.add_argument(
        "--contract-execution-mode",
        "-ContractExecutionMode",
        choices=("live", "mock"),
        default="live",
        help="Contract execution mode variable value",
    )
    api_test.add_argument(
        "--report-path",
        "-ReportPath",
        default="api/postman-cli-reports/local-contract-tests.xml",
        help="JUnit report output path",
    )
    api_test.add_argument(
        "--skip-lint",
        "-SkipLint",
        action="store_true",
        help="Skip OpenAPI spec lint before running the collection",
    )
    api_test.add_argument(
        "--start-workers",
        action="store_true",
        help="Start the local Supabase + Workers stack automatically for the collection run",
    )
    api_test.add_argument(
        "--developer-token",
        default=None,
        help="Optional developer bearer token override for authenticated contract checks",
    )
    api_test.add_argument(
        "--moderator-token",
        default=None,
        help="Optional moderator bearer token override for moderation contract checks",
    )
    api_test.add_argument(
        "--developer-email",
        default=LOCAL_SEED_DEVELOPER_EMAIL,
        help="Seeded Supabase developer email used to resolve a local access token automatically",
    )
    api_test.add_argument(
        "--moderator-email",
        default=LOCAL_SEED_MODERATOR_EMAIL,
        help="Seeded Supabase moderator email used to resolve a local access token automatically",
    )
    api_test.add_argument(
        "--seed-user-password",
        default=LOCAL_SEED_DEFAULT_PASSWORD,
        help="Seeded Supabase auth password used to resolve local access tokens automatically",
    )

    api_mock = subparsers.add_parser(
        "api-mock",
        parents=[shared],
        help="Provision a Postman mock from the Git-tracked contract collection",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    api_mock.add_argument(
        "--mode",
        choices=("shared", "ephemeral"),
        default="shared",
        help="Mock provisioning mode",
    )
    api_mock.add_argument(
        "--admin-environment",
        default="api/postman/environments/board-enthusiasts_mock-admin.postman_environment.json",
        help="Mock admin environment file path",
    )
    api_mock.add_argument(
        "--postman-api-key",
        "-PostmanApiKey",
        default=None,
        help="Postman API key override (defaults to POSTMAN_API_KEY env var)",
    )

    api_sync = subparsers.add_parser(
        "api-sync",
        parents=[shared],
        help="Push Native Git API artifacts to Postman Cloud and optionally reprovision the shared mock",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    api_sync.add_argument(
        "--postman-api-key",
        "-PostmanApiKey",
        default=None,
        help="Postman API key override (defaults to POSTMAN_API_KEY env var or existing CLI login)",
    )
    api_sync.add_argument(
        "--skip-mock",
        "-SkipMock",
        action="store_true",
        help="Skip shared mock reprovisioning after workspace push",
    )

    seed_data = subparsers.add_parser(
        "seed-data",
        parents=[shared],
        help="Populate deterministic local Supabase sample data for UI/UX testing",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    seed_data.add_argument(
        "--seed-password",
        default=LOCAL_SEED_DEFAULT_PASSWORD,
        help="Password assigned to seeded local Supabase users",
    )
    seed_data.add_argument(
        "--reset",
        action="store_true",
        help="Reset the local Supabase database before reseeding the maintained fixtures",
    )

    contract_smoke = subparsers.add_parser(
        "contract-smoke",
        parents=[shared],
        help="Run the maintained API contract smoke harness",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    contract_smoke.add_argument(
        "--base-url",
        "-BaseUrl",
        default="http://127.0.0.1:8787",
        help="Base URL for the API smoke run",
    )
    contract_smoke.add_argument(
        "--start-workers",
        action="store_true",
        help="Start the local Supabase + Workers stack automatically for the smoke run",
    )
    contract_smoke.add_argument(
        "--token",
        default=None,
        help="Optional fallback bearer token for authenticated smoke endpoints",
    )
    contract_smoke.add_argument(
        "--player-token",
        default=None,
        help="Optional player bearer token for role-specific smoke endpoints",
    )
    contract_smoke.add_argument(
        "--moderator-token",
        default=None,
        help="Optional moderator bearer token for role-specific smoke endpoints",
    )
    contract_smoke.add_argument(
        "--developer-token",
        default=None,
        help="Optional developer bearer token for role-specific smoke endpoints",
    )
    contract_smoke.add_argument(
        "--player-email",
        default=LOCAL_SEED_PLAYER_EMAIL,
        help="Seeded Supabase player email used to fetch an auth token automatically",
    )
    contract_smoke.add_argument(
        "--seed-user-email",
        default=LOCAL_SEED_DEVELOPER_EMAIL,
        help="Seeded Supabase developer email used to fetch an auth token automatically",
    )
    contract_smoke.add_argument(
        "--moderator-email",
        default=LOCAL_SEED_MODERATOR_EMAIL,
        help="Seeded Supabase moderator email used to fetch an auth token automatically",
    )
    contract_smoke.add_argument(
        "--seed-user-password",
        default=LOCAL_SEED_DEFAULT_PASSWORD,
        help="Seeded Supabase auth password used to fetch auth tokens automatically",
    )

    workers_smoke = subparsers.add_parser(
        "workers-smoke",
        parents=[shared],
        help="Run end-to-end Workers auth, data, and upload smoke coverage",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    workers_smoke.add_argument(
        "--start-stack",
        action="store_true",
        help="Start and reseed the local Supabase + Workers stack automatically",
    )
    workers_smoke.add_argument(
        "--base-url",
        default="http://127.0.0.1:8787",
        help="Workers API base URL",
    )
    workers_smoke.add_argument(
        "--player-email",
        default=LOCAL_SEED_PLAYER_EMAIL,
        help="Seeded player account email",
    )
    workers_smoke.add_argument(
        "--moderator-email",
        default="alex.rivera@boardtpl.local",
        help="Seeded moderator account email",
    )
    workers_smoke.add_argument(
        "--developer-email",
        default="emma.torres@boardtpl.local",
        help="Seeded developer account email",
    )
    workers_smoke.add_argument(
        "--seed-password",
        default=LOCAL_SEED_DEFAULT_PASSWORD,
        help="Seeded auth password",
    )

    parity_test = subparsers.add_parser(
        "parity-test",
        parents=[shared],
        help="Run browser smoke and screenshot-comparison parity tests against the current UX",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    capture_parity = subparsers.add_parser(
        "capture-parity-baseline",
        parents=[shared],
        help="Refresh committed screenshot baselines for the current UX",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    deploy = subparsers.add_parser(
        "deploy",
        parents=[shared],
        help="Run the hosted deploy flow, defaulting to production unless --staging is provided",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    deploy.add_argument(
        "--staging",
        action="store_true",
        help="Target the staging environment instead of production",
    )
    deploy.add_argument(
        "--force",
        action="store_true",
        help="Rerun every deploy stage from scratch instead of reusing completed-stage state",
    )
    deploy.add_argument(
        "--upgrade",
        action="store_true",
        help="Allow a new source fingerprint to replace the saved stage state and rerun the deploy stages",
    )
    deploy.add_argument(
        "--preflight-only",
        action="store_true",
        help="Run only the provider/config preflight checks for the selected environment",
    )
    deploy.add_argument(
        "--dry-run-only",
        action="store_true",
        help="Run preflight plus the non-publishing dry-run checks for the selected environment",
    )
    deploy.add_argument(
        "--source-branch",
        default=None,
        help="Explicit Git branch name to attach to hosted deploy metadata; defaults to GITHUB_REF_NAME or the current branch",
    )

    deploy_staging = subparsers.add_parser(
        "deploy-staging",
        parents=[shared],
        help=argparse.SUPPRESS,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    deploy_staging.add_argument(
        "--force",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    deploy_staging.add_argument(
        "--upgrade",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    deploy_staging.add_argument(
        "--preflight-only",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    deploy_staging.add_argument(
        "--dry-run-only",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    deploy_staging.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run_only",
        help=argparse.SUPPRESS,
    )
    deploy_staging.add_argument(
        "--pages-only",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    deploy_staging.add_argument(
        "--workers-only",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    deploy_staging.add_argument(
        "--source-branch",
        default=None,
        help=argparse.SUPPRESS,
    )

    deploy_fallback_pages = subparsers.add_parser(
        "deploy-fallback-pages",
        parents=[shared],
        help="Deploy the standalone Cloudflare fallback/error pages bundle",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    deploy_fallback_pages.add_argument(
        "--staging",
        action="store_true",
        help="Load Cloudflare credentials from the staging environment file instead of production",
    )
    deploy_fallback_pages.add_argument(
        "--project-name",
        default=DEFAULT_CLOUDFLARE_FALLBACK_PAGES_PROJECT_NAME,
        help="Cloudflare Pages project name for the standalone fallback site",
    )
    deploy_fallback_pages.add_argument(
        "--source-branch",
        default=None,
        help="Explicit Git branch name to attach to the Pages deploy metadata; defaults to GITHUB_REF_NAME or the current branch",
    )

    return parser


def config_from_args(args: argparse.Namespace, repo_root: Path) -> DevConfig:
    """Build ``DevConfig`` from parsed CLI arguments.

    Args:
        args: Parsed CLI arguments namespace.
        repo_root: Resolved repository root directory.

    Returns:
        A populated ``DevConfig`` instance.
    """

    return DevConfig(
        repo_root=repo_root,
        frontend_root="frontend",
        frontend_package_json="frontend/package.json",
        backend_base_url="http://127.0.0.1:8787",
        frontend_base_url="http://127.0.0.1:4173",
        api_root="api",
        api_spec="api/postman/specs/board-enthusiasts-api.v1.openapi.yaml",
        api_contract_collection="api/postman/collections/board-enthusiasts-api.contract-tests.postman_collection.json",
        api_local_environment="api/postman/environments/board-enthusiasts_local.postman_environment.json",
        api_mock_environment="api/postman/environments/board-enthusiasts_mock.postman_environment.json",
        api_mock_admin_environment="api/postman/environments/board-enthusiasts_mock-admin.postman_environment.json",
        api_mock_provision_script="api/scripts/postman-provision-mock.mjs",
        migration_root_package_json="package.json",
        migration_spa_root="frontend",
        migration_spa_workspace_name="@board-enthusiasts/spa",
        migration_workers_root="backend/apps/workers-api",
        migration_workers_workspace_name="@board-enthusiasts/workers-api",
        migration_contract_root="packages/migration-contract",
        supabase_root="backend/supabase",
        local_env_example="config/.env.local.example",
        staging_env_example="config/.env.staging.example",
        production_env_example="config/.env.example",
        local_env_file="config/.env.local",
        staging_env_file="config/.env.staging",
        production_env_file="config/.env",
        cloudflare_pages_template="cloudflare/pages/wrangler.template.jsonc",
        cloudflare_workers_template="backend/cloudflare/workers/wrangler.template.jsonc",
        cloudflare_fallback_pages_root="cloudflare/fallback-pages",
        migration_spa_base_url="http://127.0.0.1:4173",
        migration_workers_base_url="http://127.0.0.1:8787",
    )


def apply_runtime_base_url_overrides(config: DevConfig) -> DevConfig:
    """Apply local runtime URL overrides after environment loading."""

    local_workers_base_url = get_local_workers_base_url()
    local_frontend_base_url = get_local_frontend_base_url()
    return replace(
        config,
        backend_base_url=local_workers_base_url,
        frontend_base_url=local_frontend_base_url,
        migration_workers_base_url=local_workers_base_url,
        migration_spa_base_url=local_frontend_base_url,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI program entry point.

    Args:
        argv: Optional argument list. When ``None``, uses ``sys.argv``.

    Returns:
        Process exit code (`0` for success, non-zero for failures).
    """

    parser = build_parser()
    args = parser.parse_args(argv)
    repo_root = get_repo_root(Path(__file__))
    config = config_from_args(args, repo_root)
    deploy_target = None
    if args.command == "deploy":
        deploy_target = resolve_deploy_target(staging=getattr(args, "staging", False))
    elif args.command == "deploy-staging":
        deploy_target = "staging"
    elif args.command == "deploy-fallback-pages":
        deploy_target = resolve_deploy_target(staging=getattr(args, "staging", False))
    elif args.command == "bootstrap-super-admin":
        deploy_target = args.target
    auto_load_command_environment(config, command_name=args.command, deploy_target=deploy_target)
    config = apply_runtime_base_url_overrides(config)

    try:
        if args.command == "bootstrap":
            ensure_submodules(config)
            restore_backend(config)
            print("Bootstrap complete.")
        elif args.command == "clean-all":
            handle_clean_all(config)
        elif args.command == "database":
            if args.action == "up":
                restart_runtime_profile(config, profile=SUPABASE_PROFILE_DATABASE)
            elif args.action == "down":
                handle_database_down(config, include_dependencies=args.include_dependencies)
            elif args.action == "clean":
                handle_database_clean(config)
            else:
                show_database_command_status(config, include_dependencies=args.include_dependencies)
        elif args.command == "auth":
            if args.action == "up":
                restart_runtime_profile(config, profile=SUPABASE_PROFILE_AUTH)
            elif args.action == "down":
                handle_auth_down(config, include_dependencies=args.include_dependencies)
            elif args.action == "clean":
                handle_auth_clean(config)
            else:
                show_auth_command_status(config, include_dependencies=args.include_dependencies)
        elif args.command == "api":
            if args.action == "up":
                run_local_api_stack(
                    config,
                    bootstrap=args.bootstrap,
                    install_dependencies=not args.skip_install,
                )
            elif args.action == "down":
                handle_api_down(config, include_dependencies=args.include_dependencies)
            elif args.action == "clean":
                handle_api_clean(config)
            else:
                show_api_command_status(config, include_dependencies=args.include_dependencies)
        elif args.command == "web":
            if args.action == "up":
                run_full_local_web_stack(
                    config,
                    bootstrap=args.bootstrap,
                    install_dependencies=not args.skip_install,
                    hot_reload=args.hot_reload,
                    landing_mode=args.landing_mode,
                    open_browser_on_ready=not args.no_browser,
                )
            elif args.action == "down":
                handle_web_down(config, include_dependencies=args.include_dependencies)
            elif args.action == "clean":
                handle_web_clean(config)
            else:
                show_web_command_status(config, include_dependencies=args.include_dependencies)
        elif args.command == "test":
            run_tests(config, run_integration=not args.skip_integration)
        elif args.command == "all-tests":
            run_all_tests(
                config,
                bootstrap=args.bootstrap,
                environment_path=(config.repo_root / args.environment).resolve(),
                base_url=args.base_url,
                contract_execution_mode=args.contract_execution_mode,
                report_path=(config.repo_root / args.report_path).resolve(),
                start_workers=args.start_workers,
            )
        elif args.command == "verify":
            run_verify(
                config,
                run_integration=not args.skip_integration,
                run_contract_tests=not args.skip_contract_tests,
                environment_path=(config.repo_root / args.environment).resolve(),
                base_url=args.base_url,
                contract_execution_mode=args.contract_execution_mode,
                report_path=(config.repo_root / args.report_path).resolve(),
                start_workers=args.start_workers,
            )
        elif args.command == "doctor":
            run_doctor(config)
        elif args.command == "env":
            run_environment_file_command(
                config,
                target=args.target,
                copy_example=args.copy_example,
                open_file=args.open,
                sync_github_environment=args.sync_github_environment,
                github_environment=args.github_environment,
                github_repo=args.repo,
            )
        elif args.command == "bootstrap-super-admin":
            run_bootstrap_super_admin_command(
                config,
                target=args.target,
                email=args.email,
                user_name=args.user_name,
                display_name=args.display_name,
                first_name=args.first_name,
                last_name=args.last_name,
            )
        elif args.command == "api-login":
            login_postman_cli(config, postman_api_key=args.postman_api_key)
        elif args.command == "api-lint":
            run_api_spec_lint(config)
        elif args.command == "api-test":
            run_api_contract_tests(
                config,
                environment_path=(config.repo_root / args.environment).resolve(),
                base_url=args.base_url,
                contract_execution_mode=args.contract_execution_mode,
                report_path=(config.repo_root / args.report_path).resolve(),
                lint_spec=not args.skip_lint,
                start_workers=args.start_workers,
                developer_token=args.developer_token,
                moderator_token=args.moderator_token,
                developer_email=args.developer_email,
                moderator_email=args.moderator_email,
                seed_user_password=args.seed_user_password,
            )
        elif args.command == "api-mock":
            provision_api_mock(
                config,
                admin_environment_path=(config.repo_root / args.admin_environment).resolve(),
                mode=args.mode,
                postman_api_key=args.postman_api_key,
            )
        elif args.command == "api-sync":
            sync_api_workspace(
                config,
                postman_api_key=args.postman_api_key,
                reprovision_shared_mock=not args.skip_mock,
            )
        elif args.command == "seed-data":
            run_supabase_stack_command(config, action="start")
            if args.reset:
                run_supabase_stack_command(config, action="db-reset", seed_password=args.seed_password)
            else:
                seed_migration_data(config, seed_password=args.seed_password, additive=True)
        elif args.command == "contract-smoke":
            run_contract_smoke(
                config,
                base_url=args.base_url,
                start_workers=args.start_workers,
                token=args.token,
                player_token=args.player_token,
                moderator_token=args.moderator_token,
                developer_token=args.developer_token,
                player_email=args.player_email,
                seed_user_email=args.seed_user_email,
                moderator_email=args.moderator_email,
                seed_user_password=args.seed_user_password,
            )
        elif args.command == "workers-smoke":
            run_workers_flow_smoke_command(
                config,
                start_stack=args.start_stack,
                base_url=args.base_url,
                player_email=args.player_email,
                moderator_email=args.moderator_email,
                developer_email=args.developer_email,
                seed_password=args.seed_password,
            )
        elif args.command == "parity-test":
            run_parity_suite(
                config,
                update_snapshots=False,
            )
        elif args.command == "capture-parity-baseline":
            run_parity_suite(
                config,
                update_snapshots=True,
            )
        elif args.command == "deploy":
            deploy_migration_target(
                config,
                target=resolve_deploy_target(staging=args.staging),
                source_branch=args.source_branch,
                force=args.force,
                upgrade=args.upgrade,
                preflight_only=args.preflight_only,
                dry_run_only=args.dry_run_only,
            )
        elif args.command == "deploy-staging":
            if getattr(args, "pages_only", False) or getattr(args, "workers_only", False):
                if not args.dry_run_only:
                    raise DevCliError(
                        "Legacy deploy-staging partial modes are supported only with --dry-run/--dry-run-only."
                    )
                run_legacy_staging_dry_run(
                    config,
                    pages_only=getattr(args, "pages_only", False),
                    workers_only=getattr(args, "workers_only", False),
                )
                return 0
            deploy_migration_target(
                config,
                target="staging",
                source_branch=args.source_branch,
                force=args.force,
                upgrade=args.upgrade,
                preflight_only=args.preflight_only,
                dry_run_only=args.dry_run_only,
            )
        elif args.command == "deploy-fallback-pages":
            deploy_fallback_pages(
                config,
                project_name=args.project_name,
                source_branch=resolve_deploy_source_branch(config, explicit_source_branch=args.source_branch),
            )
        else:
            parser.error(f"Unknown command: {args.command}")
    except KeyboardInterrupt:
        print("\nOperation cancelled.")
        return 130
    except DevCliError as ex:
        print(f"Error: {ex}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
