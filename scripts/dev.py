#!/usr/bin/env python3
"""Developer CLI for local workflows in the board-enthusiasts repository.

This script is the primary developer automation entry point for:
- bootstrap/setup (`bootstrap`)
- dependency lifecycle (`up`, `down`, `status`)
- full local web stack execution (`web`)
- frontend web UI execution (`frontend`)
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
import json
import math
import os
import shlex
import shutil
import signal
import socket
import ssl
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


@dataclass(frozen=True)
class DevConfig:
    """Configuration values used across CLI commands.

    Attributes:
        repo_root: Repository root directory.
        frontend_root: Relative path to the frontend submodule root.
        frontend_web_project: Relative path to the frontend web project file.
        frontend_solution: Relative path to the frontend solution file.
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
        migration_local_env_template: Relative path to the local migration env example.
        migration_staging_env_template: Relative path to the staging migration env example.
        cloudflare_pages_template: Relative path to the Cloudflare Pages config template.
        cloudflare_workers_template: Relative path to the Cloudflare Workers config template.
        migration_spa_base_url: Default local React SPA URL.
        migration_workers_base_url: Default local Workers API URL.
    """

    repo_root: Path
    frontend_root: str
    frontend_web_project: str
    frontend_solution: str
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
    migration_local_env_template: str
    migration_staging_env_template: str
    cloudflare_pages_template: str
    cloudflare_workers_template: str
    migration_spa_base_url: str
    migration_workers_base_url: str


class DevCliError(RuntimeError):
    """Raised for expected CLI/runtime failures with user-friendly messages."""


REDOCLY_CLI_VERSION = "2.20.3"


def get_web_stack_state_path(config: DevConfig) -> Path:
    """Return the on-disk state file used for locally launched web stack processes.

    Args:
        config: CLI configuration containing the repository root.

    Returns:
        State file path under the shared CLI logs directory.
    """

    return config.repo_root / ".dev-cli-logs" / "web-stack-state.json"


def write_step(message: str) -> None:
    """Print a visible step marker for long-running actions.

    Args:
        message: Human-readable step description to print.

    Returns:
        None.
    """

    print(f"==> {message}")


def quote_cmd(parts: Sequence[str]) -> str:
    """Render a subprocess command as a shell-like string for error messages.

    Args:
        parts: Command tokens to quote and join.

    Returns:
        A shell-safe string representation of the command.
    """

    return " ".join(shlex.quote(p) for p in parts)


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
    result = run_command(["docker", "info"], check=False, capture_output=True, text=True)
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


def save_web_stack_state(config: DevConfig, *, state: dict[str, object]) -> Path:
    """Persist the locally launched web stack process metadata.

    Args:
        config: CLI configuration containing the repository root.
        state: Serializable process metadata to write.

    Returns:
        The written state file path.
    """

    state_path = get_web_stack_state_path(config)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state_path


def load_web_stack_state(config: DevConfig) -> dict[str, object] | None:
    """Load the persisted web stack state file if present and valid.

    Args:
        config: CLI configuration containing the repository root.

    Returns:
        Parsed state mapping, or ``None`` when the file is absent.

    Raises:
        DevCliError: If the file exists but cannot be parsed.
    """

    state_path = get_web_stack_state_path(config)
    if not state_path.exists():
        return None

    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as ex:
        raise DevCliError(f"Web stack state file is invalid JSON: {state_path}") from ex


def clear_web_stack_state(config: DevConfig) -> None:
    """Delete the persisted web stack state file when present.

    Args:
        config: CLI configuration containing the repository root.

    Returns:
        None.
    """

    get_web_stack_state_path(config).unlink(missing_ok=True)


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
        result = run_command(
            ["tasklist", "/FI", f"PID eq {pid}"],
            check=False,
            capture_output=True,
            text=True,
        )
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
        run_command(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            check=False,
            capture_output=True,
            text=True,
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


DOTNET_WATCH_ENC_CRASH_MARKERS = (
    "An unexpected error occurred: System.InvalidOperationException: Unexpected value 'Block'",
    "Microsoft.CodeAnalysis.CSharp.LambdaUtilities.TryGetCorrespondingLambdaBody",
)


def is_known_dotnet_watch_enc_crash(*, return_code: int, log_path: Path | None = None) -> bool:
    """Return whether a ``dotnet watch`` exit matches the known Roslyn EnC crash signature.

    Args:
        return_code: Process exit code from ``dotnet watch``.
        log_path: Optional log file path to inspect for crash markers.

    Returns:
        ``True`` when the exit/signature matches the known crash pattern.
    """

    if return_code != -1:
        return False

    if log_path is None or not log_path.exists():
        return True

    try:
        text = log_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return True

    return any(marker in text for marker in DOTNET_WATCH_ENC_CRASH_MARKERS)


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
            "Start the maintained backend in another terminal with 'python ./scripts/dev.py workers run' "
            "or rerun this command with '--start-backend'."
        )

    raise DevCliError(f"API base URL is not reachable: {base_url}{detail_suffix}")


def ensure_submodules(config: DevConfig) -> None:
    """Initialize backend/frontend submodules when needed.

    Args:
        config: CLI configuration containing the repository root.

    Returns:
        None.

    Raises:
        DevCliError: If Git is unavailable or submodule initialization fails.
    """

    assert_command_available("git")
    backend_path = config.repo_root / "backend"
    frontend_path = config.repo_root / "frontend"
    if test_submodule_initialized(backend_path) and test_submodule_initialized(frontend_path):
        print("Submodules appear initialized.")
        return

    write_step("Initializing submodules")
    run_command(["git", "submodule", "update", "--init", "--recursive"], cwd=config.repo_root)


def restore_backend(config: DevConfig) -> None:
    """Prepare the maintained backend workspace dependencies.

    Args:
        config: CLI configuration containing migration workspace paths.

    Returns:
        None.

    Raises:
        DevCliError: If npm is unavailable or workspace install fails.
    """

    assert_command_available("npm")
    ensure_migration_workspace_scaffolding(config)
    install_migration_workspace_dependencies(config)


def start_dependencies(config: DevConfig) -> None:
    """Start or reuse the maintained local backend dependencies.

    Args:
        config: CLI configuration containing migration workspace paths.

    Returns:
        None.

    Raises:
        DevCliError: If Supabase CLI is unavailable or local services cannot start.
    """
    run_supabase_stack_command(config, action="start")


def stop_dependencies(config: DevConfig) -> None:
    """Stop the maintained local backend dependencies.

    Args:
        config: CLI configuration containing compose and PostgreSQL settings.

    Returns:
        None.

    Raises:
        DevCliError: If the Supabase CLI command fails.
    """
    run_supabase_stack_command(config, action="stop")


def show_status(config: DevConfig) -> None:
    """Show the maintained local backend dependency status.

    Args:
        config: CLI configuration containing compose and dependency settings.

    Returns:
        None.
    """

    run_supabase_stack_command(config, action="status")


def run_backend_api(config: DevConfig, *, do_restore: bool) -> None:
    """Run the maintained backend API locally.

    Args:
        config: CLI configuration containing backend project paths.
        do_restore: Whether to run ``dotnet restore`` before starting the API.

    Returns:
        None.

    Raises:
        DevCliError: If required migration workspace files or local Supabase runtime are unavailable.
    """
    run_supabase_stack_command(config, action="start")
    run_migration_workers_command(config, action="run", install_dependencies=do_restore)


def run_frontend_web_ui(
    config: DevConfig,
    *,
    bootstrap: bool,
    do_npm_install: bool,
    do_css_build: bool,
    do_restore: bool,
    hot_reload: bool,
) -> None:
    """Run the frontend web UI from the repository root.

    Args:
        config: CLI configuration containing frontend paths.
        bootstrap: Whether to initialize submodules before running.
        do_npm_install: Whether to install frontend JavaScript dependencies first.
        do_css_build: Whether to build Tailwind CSS before launching the app.
        do_restore: Whether to restore the frontend .NET project before launching.
        hot_reload: Whether to enable frontend hot reload, including Tailwind watch.

    Returns:
        None.

    Raises:
        DevCliError: If required commands are unavailable or frontend files are missing.
    """

    del do_css_build, do_restore, hot_reload
    if bootstrap:
        ensure_submodules(config)
    run_migration_spa_command(config, action="run", install_dependencies=do_npm_install)


def run_full_local_web_stack(
    config: DevConfig,
    *,
    bootstrap: bool,
    do_backend_restore: bool,
    do_frontend_npm_install: bool,
    do_frontend_css_build: bool,
    do_frontend_restore: bool,
    hot_reload: bool,
    open_browser_on_ready: bool,
    backend_url: str,
    frontend_url: str,
) -> None:
    """Run the maintained local migration web stack together.

    Args:
        config: CLI configuration containing repository paths and defaults.
        bootstrap: Whether to initialize submodules before running.
        do_backend_restore: Whether to install/update shared npm workspace dependencies before launch.
        do_frontend_npm_install: Whether to install/update shared npm workspace dependencies before launch.
        do_frontend_css_build: Unused compatibility parameter retained for older call sites.
        do_frontend_restore: Unused compatibility parameter retained for older call sites.
        hot_reload: Unused compatibility parameter retained for older call sites.
        open_browser_on_ready: Whether to open the system browser when the frontend is reachable.
        backend_url: Backend URL to bind and probe.
        frontend_url: Frontend URL to bind, probe, and open in the browser.

    Returns:
        None.

    Raises:
        DevCliError: If required tools are unavailable or any launched process exits unexpectedly.
    """

    if bootstrap:
        ensure_submodules(config)

    assert_command_available("npm")
    del do_frontend_css_build, do_frontend_restore, hot_reload
    ensure_migration_workspace_scaffolding(config)
    if do_backend_restore or do_frontend_npm_install:
        install_migration_workspace_dependencies(config)

    run_supabase_stack_command(config, action="start")

    backend_process: subprocess.Popen | None = None
    frontend_process: subprocess.Popen | None = None
    backend_log_path: Path | None = None
    frontend_log_path: Path | None = None

    try:
        ensure_local_url_port_available(url=backend_url, description="backend API")
        ensure_local_url_port_available(url=frontend_url, description="frontend web UI")

        runtime_env = get_local_supabase_runtime(config)

        write_step("Starting maintained backend API in the background")
        backend_process, backend_log_path = start_migration_workers_process(config, runtime_env=runtime_env)
        print(f"Backend log: {backend_log_path}")
        write_step("Starting migration SPA in the background")
        frontend_process, frontend_log_path = start_background_command_with_log(
            cmd=build_workspace_npm_command(script_name="dev", workspace_name=config.migration_spa_workspace_name),
            cwd=config.repo_root,
            log_name="migration-spa.log",
            config=config,
        )
        print(f"Frontend log: {frontend_log_path}")
        wait_for_background_process_http_ready(
            process=frontend_process,
            url=frontend_url,
            description="migration SPA",
            log_path=frontend_log_path,
        )

        state: dict[str, object] = {
            "started_at_utc": datetime.now(timezone.utc).isoformat(),
            "backend": {
                "pid": backend_process.pid,
                "url": backend_url,
                "log_path": str(backend_log_path),
            },
            "frontend": {
                "pid": frontend_process.pid,
                "url": frontend_url,
                "log_path": str(frontend_log_path),
            },
        }

        state_path = save_web_stack_state(config, state=state)
        print(f"Web stack state: {state_path}")

        if open_browser_on_ready:
            write_step(f"Opening browser to {frontend_url}")
            webbrowser.open(frontend_url)

        print("Local migration web stack is running. Press Ctrl+C to stop backend and frontend.")
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
        clear_web_stack_state(config)
        if frontend_process is not None:
            write_step("Stopping frontend web UI")
            stop_background_process(frontend_process)
        if backend_process is not None:
            write_step("Stopping backend API")
            stop_background_process(backend_process)


def show_web_stack_status(config: DevConfig) -> None:
    """Show status for the locally launched backend/frontend web stack processes.

    Args:
        config: CLI configuration containing the repository root.

    Returns:
        None.
    """

    state = load_web_stack_state(config)
    if state is None:
        print("No active root-managed web stack state file was found.")
        print("Start it with: python ./scripts/dev.py web --hot-reload")
        return

    print(f"State file: {get_web_stack_state_path(config)}")
    started_at = state.get("started_at_utc")
    if isinstance(started_at, str) and started_at:
        print(f"Started at (UTC): {started_at}")

    active_count = 0
    stale_entries: list[str] = []
    for key in ("backend", "frontend", "css_watch"):
        entry = state.get(key)
        if not isinstance(entry, dict):
            continue

        pid = int(entry.get("pid", 0))
        label = key.replace("_", " ")
        running = is_process_running(pid)
        status = "running" if running else "not running"
        print(f"{label}: PID {pid} ({status})")

        url = entry.get("url")
        if isinstance(url, str) and url:
            print(f"  url: {url}")

        log_path = entry.get("log_path")
        if isinstance(log_path, str) and log_path:
            print(f"  log: {log_path}")

        if running:
            active_count += 1
        else:
            stale_entries.append(label)

    if active_count == 0:
        print("No tracked web stack processes are still running.")
        if stale_entries:
            print("The state file is stale. Remove it with: python ./scripts/dev.py web-stop")


def stop_web_stack(config: DevConfig, *, stop_dependencies_too: bool) -> None:
    """Stop the locally launched backend/frontend web stack processes.

    Args:
        config: CLI configuration containing the repository root.
        stop_dependencies_too: Whether to also stop local Supabase services.

    Returns:
        None.
    """

    state = load_web_stack_state(config)
    if state is None:
        print("No active root-managed web stack state file was found.")
    else:
        for key, label in (
            ("frontend", "frontend web UI"),
            ("css_watch", "frontend Tailwind watch"),
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

        clear_web_stack_state(config)
        print("Cleared root-managed web stack state.")

    if stop_dependencies_too:
        stop_dependencies(config)
        print("Dependencies stopped.")


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


def get_frontend_web_launch_command(project_path: Path, *, hot_reload: bool) -> list[str]:
    """Return the frontend web launch command.

    Args:
        project_path: Frontend web project path.
        hot_reload: Whether to launch with ``dotnet watch``.

    Returns:
        Command tokens for launching the frontend web app.
    """

    if hot_reload:
        return ["dotnet", "watch", "--project", str(project_path), "run", "--no-restore", "--no-launch-profile"]

    return ["dotnet", "run", "--project", str(project_path), "--no-restore", "--no-launch-profile"]


def build_frontend_web_environment(*, frontend_url: str, hot_reload: bool) -> dict[str, str]:
    """Build the environment used by frontend web runs.

    Args:
        frontend_url: URL the frontend should bind to.
        hot_reload: Whether frontend hot reload is enabled.

    Returns:
        Environment variables for the frontend process.
    """

    extra = {
        "ASPNETCORE_URLS": frontend_url,
        "ASPNETCORE_ENVIRONMENT": "Development",
    }
    if hot_reload:
        extra["DOTNET_WATCH_RESTART_ON_RUDE_EDIT"] = "true"

    return build_subprocess_env(extra=extra)


def start_frontend_web_process_with_log(
    config: DevConfig,
    *,
    frontend_url: str,
    hot_reload: bool,
) -> tuple[subprocess.Popen, Path]:
    """Start the frontend web app and return both process and log path.

    Args:
        config: CLI configuration containing frontend paths.
        frontend_url: URL the frontend should bind to.
        hot_reload: Whether frontend hot reload is enabled.

    Returns:
        Tuple of process handle and log file path.
    """

    assert_command_available("dotnet")
    frontend_root = config.repo_root / config.frontend_root
    project_path = config.repo_root / config.frontend_web_project
    if not project_path.exists():
        raise DevCliError(f"Frontend web project not found: {project_path}")
    ensure_local_url_port_available(url=frontend_url, description="frontend web UI")

    return start_background_command_with_log(
        cmd=get_frontend_web_launch_command(project_path, hot_reload=hot_reload),
        cwd=frontend_root,
        log_name="frontend-web.log",
        config=config,
        env=build_frontend_web_environment(frontend_url=frontend_url, hot_reload=hot_reload),
    )


def run_tests(config: DevConfig, *, run_integration: bool, restore: bool = True) -> None:
    """Run maintained backend verification and optionally integration coverage.

    Args:
        config: CLI configuration containing migration backend paths.
        run_integration: Whether to run backend integration coverage after typecheck.
        restore: Whether to install root npm workspace dependencies first.

    Returns:
        None.

    Raises:
        DevCliError: If required migration workspace commands fail.
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
            moderator_email=LOCAL_SEED_MODERATOR_EMAIL,
            developer_email=LOCAL_SEED_DEVELOPER_EMAIL,
            seed_password=LOCAL_SEED_DEFAULT_PASSWORD,
        )
    else:
        print("Skipping integration tests.")


def restore_frontend(config: DevConfig) -> None:
    """Restore the frontend solution.

    Args:
        config: CLI configuration containing frontend solution paths.

    Returns:
        None.

    Raises:
        DevCliError: If ``dotnet`` is unavailable or restore fails.
    """

    assert_command_available("dotnet")
    frontend_root = config.repo_root / config.frontend_root
    solution_path = config.repo_root / config.frontend_solution
    write_step("Restoring frontend solution")
    run_command(["dotnet", "restore", str(solution_path)], cwd=frontend_root)


def run_frontend_tests(config: DevConfig, *, restore: bool = True) -> None:
    """Run frontend tests.

    Args:
        config: CLI configuration containing frontend test project/solution paths.
        restore: Whether to restore packages before running tests.

    Returns:
        None.

    Raises:
        DevCliError: If ``dotnet`` is unavailable or test execution fails.
    """

    assert_command_available("dotnet")
    frontend_root = config.repo_root / config.frontend_root
    solution_path = config.repo_root / config.frontend_solution
    restore_args = [] if restore else ["--no-restore"]

    write_step("Running frontend tests")
    run_command(["dotnet", "test", str(solution_path), *restore_args], cwd=frontend_root)


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
        return [*base_command, "dev", "--config", "wrangler.jsonc", "src/worker.ts", "--ip", "127.0.0.1", "--port", "8787"]
    if action == "build":
        return [*base_command, "deploy", "--config", "wrangler.jsonc", "src/worker.ts", "--dry-run"]
    if action == "deploy":
        return [*base_command, "deploy", "--config", "wrangler.jsonc", "src/worker.ts"]

    raise DevCliError(f"Unsupported Workers Wrangler action: {action}")


def get_root_workspace_manifest_path(config: DevConfig) -> Path:
    """Return the root migration workspace package manifest path."""

    return config.repo_root / config.migration_root_package_json


def ensure_migration_workspace_scaffolding(config: DevConfig) -> None:
    """Ensure the Wave 1 migration workspace files exist before running commands.

    Args:
        config: CLI configuration containing migration workspace paths.

    Returns:
        None.

    Raises:
        DevCliError: If required migration workspace files are missing.
    """

    required_paths = [
        ("root migration package manifest", config.repo_root / config.migration_root_package_json),
        ("SPA workspace", config.repo_root / config.migration_spa_root),
        ("Workers workspace", config.repo_root / config.migration_workers_root),
        ("shared contract package", config.repo_root / config.migration_contract_root),
        ("Supabase project root", config.repo_root / config.supabase_root),
        ("local migration env template", config.repo_root / config.migration_local_env_template),
        ("staging migration env template", config.repo_root / config.migration_staging_env_template),
        ("Cloudflare Pages template", config.repo_root / config.cloudflare_pages_template),
        ("Cloudflare Workers template", config.repo_root / config.cloudflare_workers_template),
    ]

    missing = [f"{label}: {path}" for label, path in required_paths if not path.exists()]
    if missing:
        preview = "\n".join(missing)
        raise DevCliError(f"Migration workspace scaffolding is incomplete:\n{preview}")


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
    """Install root npm workspace dependencies for the migration scaffolding.

    Args:
        config: CLI configuration containing the repository root.

    Returns:
        None.
    """

    assert_command_available("npm")
    ensure_migration_workspace_scaffolding(config)
    if has_current_migration_workspace_dependencies(config):
        print("Migration workspace npm dependencies are already current.")
        return

    write_step("Installing migration workspace npm dependencies")
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
        return ["npx", "supabase"]
    raise DevCliError("Supabase CLI was not found. Install `supabase` or ensure `npx` is available.")


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
    result = run_command(
        [*prefix, "status", "-o", "env"],
        cwd=config.repo_root / config.supabase_root,
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        output = "\n".join(
            part.strip()
            for part in ((result.stdout or ""), (result.stderr or ""))
            if part and part.strip()
        )
        if "No such container" in output or "failed to inspect container health" in output:
            raise DevCliError("Local Supabase services are not running. Start them with 'python ./scripts/dev.py supabase start'.")
        raise DevCliError("Supabase status command failed." + (f"\n{output}" if output else ""))

    parsed = parse_env_assignments(result.stdout or "")
    required = ("API_URL", "ANON_KEY", "SERVICE_ROLE_KEY")
    missing = [name for name in required if not parsed.get(name)]
    if missing:
        raise DevCliError(
            "Supabase status output did not include the expected runtime keys: "
            + ", ".join(missing)
        )
    return parsed


def get_local_supabase_runtime(config: DevConfig) -> dict[str, str]:
    """Build the normalized local Supabase runtime environment mapping.

    Args:
        config: CLI configuration containing the Supabase project path.

    Returns:
        Mapping containing the API URL plus anon and service keys.
    """

    status_env = get_supabase_status_env(config)
    return {
        "SUPABASE_URL": status_env["API_URL"],
        "SUPABASE_ANON_KEY": status_env["ANON_KEY"],
        "SUPABASE_SERVICE_ROLE_KEY": status_env["SERVICE_ROLE_KEY"],
        "SUPABASE_MEDIA_BUCKET": "catalog-media",
    }


def build_supabase_bearer_headers(*, api_key: str) -> dict[str, str]:
    """Build the standard Supabase API headers for a bearer-authenticated request.

    Args:
        api_key: Supabase anon or service-role API key.

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
    timeout_seconds: int = 120,
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

    service_headers = build_supabase_bearer_headers(api_key=runtime_env["SUPABASE_SERVICE_ROLE_KEY"])
    base_url = runtime_env["SUPABASE_URL"].rstrip("/")
    checks = (
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
        f"SUPABASE_ANON_KEY={runtime_env['SUPABASE_ANON_KEY']}",
        f"SUPABASE_SERVICE_ROLE_KEY={runtime_env['SUPABASE_SERVICE_ROLE_KEY']}",
        f"SUPABASE_MEDIA_BUCKET={runtime_env['SUPABASE_MEDIA_BUCKET']}",
    ]
    dev_vars_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dev_vars_path


def run_supabase_stack_command(config: DevConfig, *, action: str) -> None:
    """Run a Supabase local workflow command from the repository root.

    Args:
        config: CLI configuration containing the Supabase project path.
        action: Supported action name.

    Returns:
        None.
    """

    ensure_migration_workspace_scaffolding(config)
    supabase_root = config.repo_root / config.supabase_root
    prefix = resolve_supabase_command_prefix()

    if action == "start":
        write_step("Starting local Supabase services")
        run_command([*prefix, "start"], cwd=supabase_root)
        return

    if action == "stop":
        write_step("Stopping local Supabase services")
        run_command([*prefix, "stop"], cwd=supabase_root)
        return

    if action == "status":
        write_step("Showing local Supabase service status")
        result = run_command(
            [*prefix, "status", "-o", "env"],
            cwd=supabase_root,
            check=False,
            capture_output=True,
        )
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
        write_step("Resetting local Supabase database and reseeding")
        result = run_command(
            [*prefix, "db", "reset", "--local"],
            cwd=supabase_root,
            check=False,
            capture_output=True,
        )
        if result.returncode != 0:
            output = "\n".join(
                part.strip()
                for part in ((result.stdout or ""), (result.stderr or ""))
                if part and part.strip()
            )
            if "Error status 502" in output:
                get_supabase_status_env(config)
                print("Supabase db reset completed with a transient 502 during service restart; continuing.")
            else:
                raise DevCliError("Supabase db reset failed." + (f"\n{output}" if output else ""))
        seed_migration_data(config, seed_password=LOCAL_SEED_DEFAULT_PASSWORD)
        return

    raise DevCliError(f"Unsupported Supabase action: {action}")


def run_migration_spa_command(
    config: DevConfig,
    *,
    action: str,
    install_dependencies: bool,
) -> None:
    """Run a migration React SPA workspace command.

    Args:
        config: CLI configuration containing migration workspace paths.
        action: `install`, `build`, or `run`.
        install_dependencies: Whether to install root npm dependencies first.

    Returns:
        None.
    """

    assert_command_available("npm")
    ensure_migration_workspace_scaffolding(config)
    if install_dependencies or action == "install":
        install_migration_workspace_dependencies(config)
        if action == "install":
            return

    if action == "build":
        write_step("Building migration React SPA")
        run_command(build_workspace_npm_command(script_name="build", workspace_name=config.migration_spa_workspace_name), cwd=config.repo_root)
        return

    if action == "run":
        write_step(f"Starting migration React SPA at {config.migration_spa_base_url} (Ctrl+C to stop)")
        run_command(build_workspace_npm_command(script_name="dev", workspace_name=config.migration_spa_workspace_name), cwd=config.repo_root)
        return

    raise DevCliError(f"Unsupported SPA action: {action}")


def run_migration_workers_command(
    config: DevConfig,
    *,
    action: str,
    install_dependencies: bool,
) -> None:
    """Run a migration Workers API workspace command.

    Args:
        config: CLI configuration containing migration workspace paths.
        action: `install`, `build`, or `run`.
        install_dependencies: Whether to install root npm dependencies first.

    Returns:
        None.
    """

    assert_command_available("npm")
    ensure_migration_workspace_scaffolding(config)
    if install_dependencies or action == "install":
        install_migration_workspace_dependencies(config)
        if action == "install":
            return

    if action == "build":
        write_step("Building migration Workers API shell")
        run_command(build_workers_wrangler_command(action="build"), cwd=config.repo_root / config.migration_workers_root)
        return

    if action == "run":
        runtime_env = get_local_supabase_runtime(config)
        wait_for_local_supabase_http_ready(runtime_env=runtime_env)
        dev_vars_path = write_workers_local_dev_vars(config, runtime_env=runtime_env)
        print(f"Workers dev bindings file: {dev_vars_path}")
        write_step(f"Starting migration Workers API at {config.migration_workers_base_url} (Ctrl+C to stop)")
        run_command(build_workers_wrangler_command(action="dev"), cwd=config.repo_root / config.migration_workers_root)
        return

    raise DevCliError(f"Unsupported Workers action: {action}")


def seed_migration_data(config: DevConfig, *, seed_password: str) -> None:
    """Seed deterministic Supabase auth, data, and storage fixtures for Wave 2.

    Args:
        config: CLI configuration containing migration workspace paths.
        seed_password: Password assigned to seeded local Supabase auth users.

    Returns:
        None.
    """

    assert_command_available("npm")
    ensure_migration_workspace_scaffolding(config)
    install_migration_workspace_dependencies(config)
    runtime_env = get_local_supabase_runtime(config)
    asset_root = (
        config.repo_root
        / "frontend"
        / "src"
        / "Board.ThirdPartyLibrary.Frontend.Web"
        / "wwwroot"
        / "test-images"
        / "seed-catalog"
    ).resolve()
    if not asset_root.exists():
        raise DevCliError(f"Migration seed asset root was not found: {asset_root}")

    write_step("Seeding local Supabase auth, storage, and relational demo data")
    run_command(
        [
            "npm",
            "run",
            "seed:migration",
            "--",
            "--supabase-url",
            runtime_env["SUPABASE_URL"],
            "--service-role-key",
            runtime_env["SUPABASE_SERVICE_ROLE_KEY"],
            "--password",
            seed_password,
            "--asset-root",
            str(asset_root),
            "--bucket",
            runtime_env["SUPABASE_MEDIA_BUCKET"],
        ],
        cwd=config.repo_root,
    )


def fetch_supabase_access_token(*, supabase_url: str, anon_key: str, email: str, password: str) -> str:
    """Exchange email/password credentials for a Supabase access token.

    Args:
        supabase_url: Supabase API base URL.
        anon_key: Supabase anon key.
        email: Seeded user email.
        password: Seeded user password.

    Returns:
        Access token string.
    """

    request = urllib.request.Request(
        f"{supabase_url.rstrip('/')}/auth/v1/token?grant_type=password",
        data=json.dumps({"email": email, "password": password}).encode("utf-8"),
        headers={
            "apikey": anon_key,
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
        config: CLI configuration containing migration workspace paths.
        runtime_env: Resolved local Supabase runtime environment values.

    Returns:
        Tuple of process handle and log path.
    """

    clear_local_listener_port(url=config.migration_workers_base_url, description="migration Workers API")
    ensure_local_url_port_available(url=config.migration_workers_base_url, description="migration Workers API")
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
        description="migration Workers API",
        log_path=log_path,
        timeout_seconds=120,
    )
    return process, log_path


def run_workers_smoke(
    config: DevConfig,
    *,
    base_url: str,
    moderator_token: str,
    developer_token: str,
) -> None:
    """Run the Wave 2 Workers flow smoke suite.

    Args:
        config: CLI configuration containing repository paths.
        base_url: Target Workers API base URL.
        moderator_token: Bearer token for the seeded moderator user.
        developer_token: Bearer token for the seeded developer user.

    Returns:
        None.
    """

    env = build_subprocess_env(
        extra={
            "WORKERS_SMOKE_BASE_URL": base_url,
            "WORKERS_SMOKE_MODERATOR_TOKEN": moderator_token,
            "WORKERS_SMOKE_DEVELOPER_TOKEN": developer_token,
            "NODE_TLS_REJECT_UNAUTHORIZED": "0" if is_local_http_url(base_url) and is_https_url(base_url) else None,
        }
    )
    write_step("Running Wave 2 Workers flow smoke suite")
    run_command(["npm", "run", "test:workers-smoke"], cwd=config.repo_root, env=env)


def run_workers_flow_smoke_command(
    config: DevConfig,
    *,
    start_stack: bool,
    base_url: str,
    moderator_email: str,
    developer_email: str,
    seed_password: str,
) -> None:
    """Run the Wave 2 end-to-end Workers smoke suite.

    Args:
        config: CLI configuration containing repository paths.
        start_stack: Whether to start and seed the local Supabase + Workers stack.
        base_url: Target Workers API base URL.
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
            write_step("Starting migration Workers API in the background for Wave 2 smoke")
            workers_process, workers_log_path = start_migration_workers_process(config, runtime_env=runtime_env)
            print(f"Workers API log: {workers_log_path}")
        else:
            ensure_api_base_url_reachable(resolved_base_url)
            runtime_env = get_local_supabase_runtime(config)

        moderator_token = fetch_supabase_access_token(
            supabase_url=runtime_env["SUPABASE_URL"],
            anon_key=runtime_env["SUPABASE_ANON_KEY"],
            email=moderator_email,
            password=seed_password,
        )
        developer_token = fetch_supabase_access_token(
            supabase_url=runtime_env["SUPABASE_URL"],
            anon_key=runtime_env["SUPABASE_ANON_KEY"],
            email=developer_email,
            password=seed_password,
        )
        run_workers_smoke(
            config,
            base_url=resolved_base_url,
            moderator_token=moderator_token,
            developer_token=developer_token,
        )
    finally:
        if workers_process is not None:
            write_step("Stopping background migration Workers API")
            stop_background_process(workers_process)


def run_contract_smoke(
    config: DevConfig,
    *,
    base_url: str,
    start_workers: bool,
    token: str | None,
    moderator_token: str | None,
    developer_token: str | None,
    seed_user_email: str | None,
    moderator_email: str | None,
    seed_user_password: str | None,
) -> None:
    """Run the maintained API contract smoke harness.

    Args:
        config: CLI configuration containing workspace paths.
        base_url: Target API base URL.
        start_workers: Whether to start the migration Workers stack automatically.
        token: Optional bearer token for authenticated smoke checks.
        moderator_token: Optional moderator bearer token for role-specific smoke checks.
        developer_token: Optional developer bearer token for role-specific smoke checks.
        seed_user_email: Optional seeded user email used to fetch a migration auth token.
        moderator_email: Optional seeded moderator email used to fetch a migration auth token.
        seed_user_password: Optional seeded user password used to fetch a migration auth token.

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
    resolved_moderator_token = moderator_token or ""
    resolved_developer_token = developer_token or ""

    if start_workers:
        if base_url != config.migration_workers_base_url and not is_local_http_url(base_url):
            raise DevCliError("--start-workers can only be used with the local Workers base URL.")
        run_supabase_stack_command(config, action="start")
        run_supabase_stack_command(config, action="db-reset")
        runtime_env = get_local_supabase_runtime(config)
        resolved_base_url = config.migration_workers_base_url
        write_step("Starting migration Workers API in the background for contract smoke")
        workers_process, workers_log_path = start_migration_workers_process(config, runtime_env=runtime_env)
        print(f"Workers API log: {workers_log_path}")
    else:
        ensure_api_base_url_reachable(resolved_base_url)

    if runtime_env is None and is_local_http_url(resolved_base_url):
        runtime_env = get_local_supabase_runtime(config)

    if runtime_env is not None:
        developer_email = seed_user_email or (LOCAL_SEED_DEVELOPER_EMAIL if start_workers else None)
        resolved_moderator_email = moderator_email or (LOCAL_SEED_MODERATOR_EMAIL if start_workers else None)
        seed_password = seed_user_password or LOCAL_SEED_DEFAULT_PASSWORD

        if developer_email and not resolved_developer_token:
            resolved_developer_token = fetch_supabase_access_token(
                supabase_url=runtime_env["SUPABASE_URL"],
                anon_key=runtime_env["SUPABASE_ANON_KEY"],
                email=developer_email,
                password=seed_password,
            )

        if resolved_moderator_email and not resolved_moderator_token:
            resolved_moderator_token = fetch_supabase_access_token(
                supabase_url=runtime_env["SUPABASE_URL"],
                anon_key=runtime_env["SUPABASE_ANON_KEY"],
                email=resolved_moderator_email,
                password=seed_password,
            )

        if not resolved_token:
            resolved_token = resolved_developer_token or resolved_moderator_token

    env = build_subprocess_env(
        extra={
            "CONTRACT_SMOKE_BASE_URL": resolved_base_url,
            "CONTRACT_SMOKE_TOKEN": resolved_token,
            "CONTRACT_SMOKE_PLAYER_TOKEN": resolved_developer_token or resolved_token,
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
            write_step("Stopping background migration Workers API")
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

    frontend_ready, detail = probe_http_url(config.frontend_base_url)
    if not frontend_ready:
        raise DevCliError(
            f"Frontend base URL is not reachable: {config.frontend_base_url}"
            + (f" ({detail})" if detail else "")
        )

    env = build_subprocess_env(
        extra={
            "PARITY_BASE_URL": config.frontend_base_url,
            "PARITY_ADMIN_USERNAME": "alex.rivera",
            "PARITY_ADMIN_PASSWORD": LOCAL_SEED_DEFAULT_PASSWORD,
            "NODE_TLS_REJECT_UNAUTHORIZED": "0" if is_https_url(config.frontend_base_url) else None,
        }
    )
    command = ["npm", "run", "capture:parity-baseline" if update_snapshots else "test:parity"]
    write_step("Running parity browser baseline suite")
    run_command(command, cwd=config.repo_root, env=env)


def deploy_migration_staging(
    config: DevConfig,
    *,
    pages_only: bool,
    workers_only: bool,
    dry_run: bool,
) -> None:
    """Run the staging deployment wrappers for the migration workspaces.

    Args:
        config: CLI configuration containing migration paths.
        pages_only: Whether to deploy only Cloudflare Pages.
        workers_only: Whether to deploy only Cloudflare Workers.
        dry_run: Whether to perform build-only validation instead of deployment.

    Returns:
        None.
    """

    if pages_only and workers_only:
        raise DevCliError("--pages-only and --workers-only cannot be used together.")

    assert_command_available("npm")
    ensure_migration_workspace_scaffolding(config)
    install_migration_workspace_dependencies(config)

    if not workers_only:
        write_step("Building migration SPA for Cloudflare Pages")
        run_command(build_workspace_npm_command(script_name="build", workspace_name=config.migration_spa_workspace_name), cwd=config.repo_root)
        if not dry_run:
            write_step("Deploying Cloudflare Pages staging bundle")
            run_command(
                [
                    "npx",
                    "wrangler",
                    "pages",
                    "deploy",
                    str(config.repo_root / config.migration_spa_root / "dist"),
                    "--project-name",
                    "board-enthusiasts-staging",
                    "--branch",
                    "main",
                ],
                cwd=config.repo_root,
            )

    if not pages_only:
        write_step("Deploying Cloudflare Workers staging bundle")
        worker_command = [
            "npx",
            "wrangler",
            "deploy",
            *(["--dry-run"] if dry_run else []),
            "--config",
            str(config.repo_root / config.cloudflare_workers_template),
        ]
        run_command(worker_command, cwd=config.repo_root)


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
            part.strip() for part in (result.stdout or "", result.stderr or "") if part and part.strip()
        )
        raise DevCliError(
            "Redocly OpenAPI lint failed."
            + (f"\n{combined_output}" if combined_output else "")
        )
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
        write_step("Starting migration Workers API in the background for contract tests")
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
                anon_key=runtime_env["SUPABASE_ANON_KEY"],
                email=resolved_developer_email,
                password=resolved_seed_password,
            )

        if resolved_moderator_email and not resolved_moderator_token:
            resolved_moderator_token = fetch_supabase_access_token(
                supabase_url=runtime_env["SUPABASE_URL"],
                anon_key=runtime_env["SUPABASE_ANON_KEY"],
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
            write_step("Stopping background migration Workers API")
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
    for cmd in ("git", "docker", "dotnet", "python"):
        if shutil.which(cmd):
            print(f"Found: {cmd}")
        else:
            print(f"Missing command: {cmd}")
            issues.append(f"Required command missing from PATH: {cmd}")

    for cmd in ("node", "npm", "postman"):
        if shutil.which(cmd):
            print(f"Found (API/frontend workflow): {cmd}")
        else:
            print(f"Missing optional API/frontend workflow command: {cmd}")
            optional_issues.append(
                f"Optional API/frontend workflow command missing from PATH: {cmd}"
            )

    if shutil.which("supabase") or shutil.which("npx"):
        print("Found (migration workflow): supabase")
    else:
        print("Missing optional migration workflow command: supabase")
        optional_issues.append(
            "Optional migration workflow command missing from PATH: supabase (or npx fallback)"
        )

    local_wrangler_path = config.repo_root / "node_modules" / ".bin" / ("wrangler.cmd" if os.name == "nt" else "wrangler")
    if shutil.which("wrangler") or local_wrangler_path.exists():
        print("Found (migration workflow): wrangler")
    else:
        print("Missing optional migration workflow command: wrangler")
        optional_issues.append(
            "Optional migration workflow command missing from PATH: wrangler (run `python ./scripts/dev.py bootstrap` to install workspace tooling)"
        )

    backend_path = config.repo_root / "backend"
    frontend_path = config.repo_root / "frontend"
    if not test_submodule_initialized(backend_path):
        issues.append("Backend submodule is not initialized (run: git submodule update --init --recursive)")
    if not test_submodule_initialized(frontend_path):
        issues.append("Frontend submodule is not initialized (run: git submodule update --init --recursive)")

    if shutil.which("git"):
        write_step("Submodule status")
        run_command(["git", "submodule", "status"], cwd=config.repo_root, check=False, capture_output=False)

    if shutil.which("dotnet"):
        write_step(".NET SDK version")
        result = run_command(["dotnet", "--version"], check=False, capture_output=False)
        if result.returncode != 0:
            issues.append("dotnet is installed but `dotnet --version` failed")

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
        print("  python ./scripts/dev.py web")
        print("  python ./scripts/dev.py frontend")
        print("  python ./scripts/dev.py up --dependencies-only")
        print("  python ./scripts/dev.py up --skip-restore")
        print("  python ./scripts/dev.py all-tests")
        print("  python ./scripts/dev.py api-test --start-workers --skip-lint")
        print("  python ./scripts/dev.py spa install")
        print("  python ./scripts/dev.py workers build")
        print("  python ./scripts/dev.py supabase status")
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
        print("  python ./scripts/dev.py web")
        print("  python ./scripts/dev.py frontend")
        print("  python ./scripts/dev.py up --dependencies-only")
        print("  python ./scripts/dev.py up --skip-restore")
        print("  python ./scripts/dev.py all-tests")
        print("  python ./scripts/dev.py api-test --start-workers --skip-lint")
        print("  python ./scripts/dev.py api-lint")
        print("  python ./scripts/dev.py spa run")
        print("  python ./scripts/dev.py workers run")
        print("  python ./scripts/dev.py supabase start")


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
        start_workers: Whether to auto-start the Workers migration stack for contract runs.

    Returns:
        None.
    """

    restore_backend(config)
    run_tests(config, run_integration=run_integration, restore=False)
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
        start_workers: Whether to auto-start the Workers migration stack for contract runs.

    Returns:
        None.
    """

    if bootstrap:
        ensure_submodules(config)

    restore_backend(config)
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


LOCAL_SEED_DEFAULT_PASSWORD = "ChangeMe!123"
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

    up = subparsers.add_parser(
        "up",
        parents=[shared],
        help="Start/reuse local Supabase services and run the maintained backend API",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    up.add_argument(
        "--bootstrap",
        "-Bootstrap",
        action="store_true",
        help="Run submodule initialization checks before startup",
    )
    up.add_argument(
        "--dependencies-only",
        "-DependenciesOnly",
        action="store_true",
        help="Start local dependencies only (do not run API)",
    )
    up.add_argument(
        "--skip-restore",
        "-SkipRestore",
        action="store_true",
        help="Skip npm workspace installation before backend startup",
    )

    frontend = subparsers.add_parser(
        "frontend",
        parents=[shared],
        help="Run the maintained SPA frontend from the repository root",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    frontend.add_argument(
        "--bootstrap",
        "-Bootstrap",
        action="store_true",
        help="Run submodule initialization checks before startup",
    )
    frontend.add_argument(
        "--skip-npm-install",
        "-SkipNpmInstall",
        action="store_true",
        help="Skip npm dependency installation before launch",
    )
    frontend.add_argument(
        "--skip-css-build",
        "-SkipCssBuild",
        action="store_true",
        help="Retained for compatibility; the maintained SPA launch does not use this flag",
    )
    frontend.add_argument(
        "--skip-restore",
        "-SkipRestore",
        action="store_true",
        help="Retained for compatibility; the maintained SPA launch does not use this flag",
    )
    frontend.add_argument(
        "--hot-reload",
        "-HotReload",
        action="store_true",
        help="Retained for compatibility; Vite dev mode already provides the maintained SPA reload workflow",
    )

    web = subparsers.add_parser(
        "web",
        parents=[shared],
        help="Run local Supabase, the maintained backend API, and the maintained SPA together",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    web.add_argument(
        "--bootstrap",
        "-Bootstrap",
        action="store_true",
        help="Run submodule initialization checks before startup",
    )
    web.add_argument(
        "--skip-backend-restore",
        "-SkipBackendRestore",
        action="store_true",
        help="Skip npm workspace installation before backend startup",
    )
    web.add_argument(
        "--skip-npm-install",
        "-SkipNpmInstall",
        action="store_true",
        help="Skip frontend npm dependency installation before startup",
    )
    web.add_argument(
        "--skip-css-build",
        "-SkipCssBuild",
        action="store_true",
        help="Retained for compatibility; the maintained SPA launch does not use this flag",
    )
    web.add_argument(
        "--skip-frontend-restore",
        "-SkipFrontendRestore",
        action="store_true",
        help="Retained for compatibility; the maintained SPA launch does not use this flag",
    )
    web.add_argument(
        "--hot-reload",
        "-HotReload",
        action="store_true",
        help="Retained for compatibility; Vite dev mode already provides the maintained SPA reload workflow",
    )
    web.add_argument(
        "--no-browser",
        "-NoBrowser",
        action="store_true",
        help="Do not automatically open the frontend URL in the default browser",
    )
    web.add_argument(
        "--backend-url",
        "-BackendUrl",
        default="http://127.0.0.1:8787",
        help="Backend URL to bind and probe",
    )
    web.add_argument(
        "--frontend-url",
        "-FrontendUrl",
        default="http://127.0.0.1:4173",
        help="Frontend URL to bind, probe, and open",
    )

    web_status = subparsers.add_parser(
        "web-status",
        parents=[shared],
        help="Show status for the locally launched root web stack",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    web_stop = subparsers.add_parser(
        "web-stop",
        parents=[shared],
        help="Stop the locally launched root web stack",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    web_stop.add_argument(
        "--down-dependencies",
        "-DownDependencies",
        action="store_true",
        help="Also stop local Supabase services after stopping app processes",
    )

    subparsers.add_parser(
        "down",
        parents=[shared],
        help="Stop local Supabase services",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    subparsers.add_parser(
        "status",
        parents=[shared],
        help="Show local Supabase service status",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
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

    spa = subparsers.add_parser(
        "spa",
        parents=[shared],
        help="Run migration React SPA workspace workflows",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    spa.add_argument(
        "action",
        choices=("install", "build", "run"),
        nargs="?",
        default="run",
        help="Migration SPA action to execute",
    )
    spa.add_argument(
        "--skip-install",
        action="store_true",
        help="Do not install root npm workspace dependencies before build/run",
    )

    workers = subparsers.add_parser(
        "workers",
        parents=[shared],
        help="Run migration Workers API workspace workflows",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    workers.add_argument(
        "action",
        choices=("install", "build", "run"),
        nargs="?",
        default="run",
        help="Workers API action to execute",
    )
    workers.add_argument(
        "--skip-install",
        action="store_true",
        help="Do not install root npm workspace dependencies before build/run",
    )

    supabase = subparsers.add_parser(
        "supabase",
        parents=[shared],
        help="Run local Supabase CLI workflows for the migration stack",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    supabase.add_argument(
        "action",
        choices=("start", "stop", "status", "db-reset"),
        help="Supabase local workflow action",
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
        help="Start the local Supabase + Workers migration stack automatically for the smoke run",
    )
    contract_smoke.add_argument(
        "--token",
        default=None,
        help="Optional fallback bearer token for authenticated smoke endpoints",
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
        "--seed-user-email",
        default=LOCAL_SEED_DEVELOPER_EMAIL,
        help="Seeded Supabase developer email used to fetch a migration auth token automatically",
    )
    contract_smoke.add_argument(
        "--moderator-email",
        default=LOCAL_SEED_MODERATOR_EMAIL,
        help="Seeded Supabase moderator email used to fetch a migration auth token automatically",
    )
    contract_smoke.add_argument(
        "--seed-user-password",
        default=LOCAL_SEED_DEFAULT_PASSWORD,
        help="Seeded Supabase auth password used to fetch migration auth tokens automatically",
    )

    workers_smoke = subparsers.add_parser(
        "workers-smoke",
        parents=[shared],
        help="Run end-to-end Wave 2 Workers auth, data, and upload smoke coverage",
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

    deploy_staging = subparsers.add_parser(
        "deploy-staging",
        parents=[shared],
        help="Run migration staging deployment wrappers for Pages and Workers",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    deploy_staging.add_argument(
        "--pages-only",
        action="store_true",
        help="Deploy only the Cloudflare Pages bundle",
    )
    deploy_staging.add_argument(
        "--workers-only",
        action="store_true",
        help="Deploy only the Cloudflare Workers bundle",
    )
    deploy_staging.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and validate deployment inputs without publishing them",
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
        frontend_web_project="frontend/src/Board.ThirdPartyLibrary.Frontend.Web/Board.ThirdPartyLibrary.Frontend.Web.csproj",
        frontend_solution="frontend/Board.ThirdPartyLibrary.Frontend.slnx",
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
        migration_spa_root="apps/spa",
        migration_spa_workspace_name="@board-enthusiasts/spa",
        migration_workers_root="backend/apps/workers-api",
        migration_workers_workspace_name="@board-enthusiasts/workers-api",
        migration_contract_root="packages/migration-contract",
        supabase_root="backend/supabase",
        migration_local_env_template="config/migration.local.env.example",
        migration_staging_env_template="config/migration.staging.env.example",
        cloudflare_pages_template="cloudflare/pages/wrangler.template.jsonc",
        cloudflare_workers_template="backend/cloudflare/workers/wrangler.template.jsonc",
        migration_spa_base_url="http://127.0.0.1:4173",
        migration_workers_base_url="http://127.0.0.1:8787",
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

    try:
        if args.command == "bootstrap":
            ensure_submodules(config)
            restore_backend(config)
            print("Bootstrap complete.")
        elif args.command == "up":
            if args.bootstrap:
                print("Running bootstrap checks before startup (convenience mode).")
                ensure_submodules(config)
            start_dependencies(config)
            if args.dependencies_only:
                print("Dependencies are up.")
                print("Run the API with: python ./scripts/dev.py up --skip-restore")
                return 0
            run_backend_api(config, do_restore=not args.skip_restore)
        elif args.command == "frontend":
            run_frontend_web_ui(
                config,
                bootstrap=args.bootstrap,
                do_npm_install=not args.skip_npm_install,
                do_css_build=not args.skip_css_build,
                do_restore=not args.skip_restore,
                hot_reload=args.hot_reload,
            )
        elif args.command == "web":
            run_full_local_web_stack(
                config,
                bootstrap=args.bootstrap,
                do_backend_restore=not args.skip_backend_restore,
                do_frontend_npm_install=not args.skip_npm_install,
                do_frontend_css_build=not args.skip_css_build,
                do_frontend_restore=not args.skip_frontend_restore,
                hot_reload=args.hot_reload,
                open_browser_on_ready=not args.no_browser,
                backend_url=args.backend_url,
                frontend_url=args.frontend_url,
            )
        elif args.command == "web-status":
            show_web_stack_status(config)
        elif args.command == "web-stop":
            stop_web_stack(config, stop_dependencies_too=args.down_dependencies)
        elif args.command == "down":
            stop_dependencies(config)
            print("Dependencies stopped.")
        elif args.command == "status":
            show_status(config)
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
            seed_migration_data(
                config,
                seed_password=args.seed_password,
            )
        elif args.command == "spa":
            run_migration_spa_command(
                config,
                action=args.action,
                install_dependencies=not args.skip_install,
            )
        elif args.command == "workers":
            run_migration_workers_command(
                config,
                action=args.action,
                install_dependencies=not args.skip_install,
            )
        elif args.command == "supabase":
            run_supabase_stack_command(config, action=args.action)
        elif args.command == "contract-smoke":
            run_contract_smoke(
                config,
                base_url=args.base_url,
                start_workers=args.start_workers,
                token=args.token,
                moderator_token=args.moderator_token,
                developer_token=args.developer_token,
                seed_user_email=args.seed_user_email,
                moderator_email=args.moderator_email,
                seed_user_password=args.seed_user_password,
            )
        elif args.command == "workers-smoke":
            run_workers_flow_smoke_command(
                config,
                start_stack=args.start_stack,
                base_url=args.base_url,
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
        elif args.command == "deploy-staging":
            deploy_migration_staging(
                config,
                pages_only=args.pages_only,
                workers_only=args.workers_only,
                dry_run=args.dry_run,
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

