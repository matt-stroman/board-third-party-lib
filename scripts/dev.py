#!/usr/bin/env python3
"""Developer CLI for local workflows in the board-third-party-lib repository.

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
  with optional backend auto-start for local contract runs
- environment diagnostics (`doctor`)
- local PostgreSQL backup/restore helpers (`db-backup`, `db-restore`)

Use `python ./scripts/dev.py --help` and `python ./scripts/dev.py <command> --help`
for command-specific help.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import shlex
import shutil
import signal
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class DevConfig:
    """Configuration values used across CLI commands.

    Attributes:
        repo_root: Repository root directory.
        compose_file: Relative path to the Docker Compose file.
        postgres_container_name: Expected local PostgreSQL container name.
        postgres_user: PostgreSQL username for local commands.
        postgres_database: PostgreSQL database name for local commands.
        mailpit_container_name: Expected local Mailpit container name.
        mailpit_ready_url: URL used to verify local Mailpit readiness.
        keycloak_container_name: Expected local Keycloak container name.
        keycloak_ready_url: URL used to verify local Keycloak readiness.
        backend_project: Relative path to the backend API project file.
        backend_solution: Relative path to the backend solution file.
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
    """

    repo_root: Path
    compose_file: str
    postgres_container_name: str
    postgres_user: str
    postgres_database: str
    mailpit_container_name: str
    mailpit_ready_url: str
    keycloak_container_name: str
    keycloak_ready_url: str
    backend_project: str
    backend_solution: str
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


class DevCliError(RuntimeError):
    """Raised for expected CLI/runtime failures with user-friendly messages."""


KEYCLOAK_DEV_CERT_RELATIVE_PATH = "backend/keycloak/certs/boardtpl-localhost-devcert.pfx"
KEYCLOAK_DEV_CERT_PASSWORD = "boardtpl-devcert"
MAILPIT_SERVER_CERT_RELATIVE_PATH = "backend/mailpit/certs/server.crt"
MAILPIT_SERVER_KEY_RELATIVE_PATH = "backend/mailpit/certs/server.key"
POSTGRES_SERVER_CERT_RELATIVE_PATH = "backend/postgres/certs/server.crt"
POSTGRES_SERVER_KEY_RELATIVE_PATH = "backend/postgres/certs/server.key"
REDOCLY_CLI_VERSION = "2.20.3"
KEYCLOAK_READY_TIMEOUT_SECONDS = 240


def get_web_stack_state_path(config: DevConfig) -> Path:
    """Return the on-disk state file used for locally launched web stack processes.

    Args:
        config: CLI configuration containing the repository root.

    Returns:
        State file path under the shared CLI logs directory.
    """

    return config.repo_root / ".dev-cli-logs" / "web-stack-state.json"


def get_keycloak_dev_certificate_path(config: DevConfig) -> Path:
    """Return the exported localhost certificate path used by local Keycloak HTTPS.

    Args:
        config: CLI configuration containing the repository root.

    Returns:
        Certificate file path under the backend Keycloak config area.
    """

    return config.repo_root / KEYCLOAK_DEV_CERT_RELATIVE_PATH


def get_postgres_server_certificate_path(config: DevConfig) -> Path:
    """Return the exported PEM certificate path used by local PostgreSQL TLS.

    Args:
        config: CLI configuration containing the repository root.

    Returns:
        PEM certificate file path.
    """

    return config.repo_root / POSTGRES_SERVER_CERT_RELATIVE_PATH


def get_postgres_server_key_path(config: DevConfig) -> Path:
    """Return the exported PEM private key path used by local PostgreSQL TLS.

    Args:
        config: CLI configuration containing the repository root.

    Returns:
        PEM private key file path.
    """

    return config.repo_root / POSTGRES_SERVER_KEY_RELATIVE_PATH


def get_mailpit_server_certificate_path(config: DevConfig) -> Path:
    """Return the PEM certificate path used by local Mailpit HTTPS and STARTTLS.

    Args:
        config: CLI configuration containing the repository root.

    Returns:
        PEM certificate file path.
    """

    return config.repo_root / MAILPIT_SERVER_CERT_RELATIVE_PATH


def get_mailpit_server_key_path(config: DevConfig) -> Path:
    """Return the PEM private key path used by local Mailpit HTTPS and STARTTLS.

    Args:
        config: CLI configuration containing the repository root.

    Returns:
        PEM private key file path.
    """

    return config.repo_root / MAILPIT_SERVER_KEY_RELATIVE_PATH


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


def get_compose_args(config: DevConfig) -> list[str]:
    """Build docker compose base arguments for the configured compose file.

    Args:
        config: CLI configuration containing the compose file path.

    Returns:
        Base ``docker compose`` arguments including the ``-f`` compose file flag.
    """

    return ["compose", "-f", str(config.repo_root / config.compose_file)]


def invoke_docker_compose(config: DevConfig, sub_args: Sequence[str]) -> None:
    """Invoke docker compose with the configured compose file.

    Args:
        config: CLI configuration containing compose settings.
        sub_args: Additional ``docker compose`` arguments (for example ``["up", "-d"]``).

    Returns:
        None.

    Raises:
        DevCliError: If Docker is unavailable or the compose command fails.
    """

    ensure_docker_daemon_available()
    args = ["docker", *get_compose_args(config), *sub_args]
    run_command(args, check=True, capture_output=False, text=True)


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


def get_docker_container_state(container_name: str) -> str | None:
    """Return Docker container state or ``None`` if the container is missing.

    Args:
        container_name: Docker container name to inspect.

    Returns:
        Container state string (for example ``"running"`` or ``"exited"``), or
        ``None`` when the container does not exist.

    Raises:
        DevCliError: If Docker is unavailable on ``PATH``.
    """

    ensure_docker_daemon_available()
    result = run_command(
        ["docker", "container", "inspect", "-f", "{{.State.Status}}", container_name],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return (result.stdout or "").strip() or None


def wait_for_postgres(
    *,
    container_name: str,
    user: str,
    database: str,
    timeout_seconds: int = 60,
) -> None:
    """Wait until ``pg_isready`` succeeds inside the PostgreSQL container.

    Args:
        container_name: PostgreSQL container name.
        user: PostgreSQL user for readiness checks.
        database: PostgreSQL database for readiness checks.
        timeout_seconds: Maximum time to wait before failing.

    Returns:
        None.

    Raises:
        DevCliError: If PostgreSQL does not become ready before timeout.
    """

    write_step(f"Waiting for PostgreSQL readiness (up to {timeout_seconds} seconds)")
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        result = run_command(
            ["docker", "exec", container_name, "pg_isready", "-U", user, "-d", database],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print("PostgreSQL is ready.")
            return
        time.sleep(2)
    raise DevCliError(f"Timed out waiting for PostgreSQL container '{container_name}' to become ready.")


def wait_for_http_ready(*, url: str, description: str, timeout_seconds: int = 90) -> None:
    """Wait until an HTTP endpoint returns a successful status code.

    Args:
        url: URL to poll for readiness.
        description: Human-readable service description for log output.
        timeout_seconds: Maximum time to wait before failing.

    Returns:
        None.

    Raises:
        DevCliError: If the URL does not return a success status before timeout.
    """

    write_step(f"Waiting for {description} readiness (up to {timeout_seconds} seconds)")
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        reachable, detail = probe_http_url(url)
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


def ensure_dotnet_dev_certificate_trusted() -> None:
    """Ensure the .NET HTTPS development certificate exists and is trusted.

    Returns:
        None.

    Raises:
        DevCliError: If ``dotnet`` is unavailable or trust establishment fails.
    """

    assert_command_available("dotnet")
    supports_trust = sys.platform.startswith("win") or sys.platform == "darwin"
    check = run_command(
        [
            "dotnet",
            "dev-certs",
            "https",
            "--check",
            *(["--trust"] if supports_trust else []),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if check.returncode == 0:
        return

    if supports_trust:
        write_step("Trusting the .NET HTTPS development certificate")
        run_command(["dotnet", "dev-certs", "https", "--trust"], check=True, capture_output=False, text=True)
        return

    write_step("Ensuring the .NET HTTPS development certificate exists")
    run_command(["dotnet", "dev-certs", "https"], check=True, capture_output=False, text=True)


def ensure_keycloak_https_certificate_exported(config: DevConfig) -> Path:
    """Export the trusted localhost development certificate for Keycloak HTTPS.

    Args:
        config: CLI configuration containing the repository root.

    Returns:
        Exported certificate path.
    """

    ensure_dotnet_dev_certificate_trusted()
    certificate_path = get_keycloak_dev_certificate_path(config)
    certificate_path.parent.mkdir(parents=True, exist_ok=True)

    write_step("Exporting localhost HTTPS development certificate for Keycloak")
    run_command(
        [
            "dotnet",
            "dev-certs",
            "https",
            "--export-path",
            str(certificate_path),
            "--password",
            KEYCLOAK_DEV_CERT_PASSWORD,
        ],
        cwd=config.repo_root,
        check=True,
        capture_output=False,
        text=True,
    )
    return certificate_path


def ensure_postgres_tls_material_exported(config: DevConfig) -> tuple[Path, Path]:
    """Export PEM certificate and private key for local PostgreSQL TLS.

    Args:
        config: CLI configuration containing the repository root.

    Returns:
        Tuple of `(certificate_path, private_key_path)`.

    Raises:
        DevCliError: If PowerShell is unavailable or PEM conversion fails.
    """

    pfx_path = ensure_keycloak_https_certificate_exported(config)
    powershell_executable = get_powershell_executable()
    if powershell_executable is None:
        raise DevCliError("PowerShell is required to export PostgreSQL TLS certificate material on this machine.")

    certificate_path = get_postgres_server_certificate_path(config)
    private_key_path = get_postgres_server_key_path(config)
    certificate_path.parent.mkdir(parents=True, exist_ok=True)

    powershell_script = (
        "$ErrorActionPreference='Stop'; "
        f"$pfxPath = '{pfx_path}'; "
        f"$password = ConvertTo-SecureString '{KEYCLOAK_DEV_CERT_PASSWORD}' -AsPlainText -Force; "
        f"$certPath = '{certificate_path}'; "
        f"$keyPath = '{private_key_path}'; "
        "$cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2("
        "$pfxPath, $password, "
        "[System.Security.Cryptography.X509Certificates.X509KeyStorageFlags]::Exportable"
        "); "
        "[System.IO.File]::WriteAllText($certPath, $cert.ExportCertificatePem()); "
        "$rsa = [System.Security.Cryptography.X509Certificates.RSACertificateExtensions]::GetRSAPrivateKey($cert); "
        "if ($null -eq $rsa) { throw 'The exported localhost certificate did not contain an RSA private key.' }; "
        "[System.IO.File]::WriteAllText($keyPath, $rsa.ExportPkcs8PrivateKeyPem())"
    )

    write_step("Exporting localhost TLS certificate material for PostgreSQL")
    run_command(
        [powershell_executable, "-NoProfile", "-Command", powershell_script],
        cwd=config.repo_root,
        check=True,
        capture_output=False,
        text=True,
    )
    return certificate_path, private_key_path


def ensure_mailpit_tls_material_exported(config: DevConfig) -> tuple[Path, Path]:
    """Create and trust a local TLS certificate for Mailpit HTTPS and SMTP STARTTLS.

    Args:
        config: CLI configuration containing the repository root.

    Returns:
        Tuple of ``(certificate_path, private_key_path)``.

    Raises:
        DevCliError: If PowerShell is unavailable or certificate generation fails.
    """

    powershell_executable = get_powershell_executable()
    if powershell_executable is None:
        raise DevCliError("PowerShell is required to export Mailpit TLS certificate material on this machine.")

    certificate_path = get_mailpit_server_certificate_path(config)
    private_key_path = get_mailpit_server_key_path(config)
    certificate_path.parent.mkdir(parents=True, exist_ok=True)

    if certificate_path.exists() and private_key_path.exists():
        powershell_script = (
            "$ErrorActionPreference='Stop'; "
            f"$certPath = '{certificate_path}'; "
            "$certificate = [System.Security.Cryptography.X509Certificates.X509Certificate2]::new($certPath); "
            "$store = [System.Security.Cryptography.X509Certificates.X509Store]::new('Root', 'CurrentUser'); "
            "$store.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite); "
            "$matches = $store.Certificates.Find("
            "[System.Security.Cryptography.X509Certificates.X509FindType]::FindByThumbprint, "
            "$certificate.Thumbprint, "
            "$false"
            "); "
            "if ($matches.Count -eq 0) { $store.Add($certificate) }; "
            "$store.Close()"
        )
        write_step("Trusting existing local Mailpit TLS certificate")
    else:
        powershell_script = (
            "$ErrorActionPreference='Stop'; "
            f"$certPath = '{certificate_path}'; "
            f"$keyPath = '{private_key_path}'; "
            "$rsa = [System.Security.Cryptography.RSA]::Create(2048); "
            "$request = [System.Security.Cryptography.X509Certificates.CertificateRequest]::new("
            "'CN=localhost', "
            "$rsa, "
            "[System.Security.Cryptography.HashAlgorithmName]::SHA256, "
            "[System.Security.Cryptography.RSASignaturePadding]::Pkcs1"
            "); "
            "$basicConstraints = [System.Security.Cryptography.X509Certificates.X509BasicConstraintsExtension]::new($false, $false, 0, $true); "
            "$keyUsage = [System.Security.Cryptography.X509Certificates.X509KeyUsageExtension]::new("
            "[System.Security.Cryptography.X509Certificates.X509KeyUsageFlags]::DigitalSignature -bor "
            "[System.Security.Cryptography.X509Certificates.X509KeyUsageFlags]::KeyEncipherment, "
            "$true"
            "); "
            "$ekuCollection = [System.Security.Cryptography.OidCollection]::new(); "
            "$null = $ekuCollection.Add([System.Security.Cryptography.Oid]::new('1.3.6.1.5.5.7.3.1')); "
            "$enhancedKeyUsage = [System.Security.Cryptography.X509Certificates.X509EnhancedKeyUsageExtension]::new($ekuCollection, $true); "
            "$sanBuilder = [System.Security.Cryptography.X509Certificates.SubjectAlternativeNameBuilder]::new(); "
            "$sanBuilder.AddDnsName('localhost'); "
            "$sanBuilder.AddDnsName('mailpit'); "
            "$sanBuilder.AddDnsName('board_tpl_mailpit'); "
            "$request.CertificateExtensions.Add($basicConstraints); "
            "$request.CertificateExtensions.Add($keyUsage); "
            "$request.CertificateExtensions.Add($enhancedKeyUsage); "
            "$request.CertificateExtensions.Add($sanBuilder.Build()); "
            "$request.CertificateExtensions.Add([System.Security.Cryptography.X509Certificates.X509SubjectKeyIdentifierExtension]::new($request.PublicKey, $false)); "
            "$notBefore = [System.DateTimeOffset]::UtcNow.AddDays(-1); "
            "$notAfter = $notBefore.AddYears(5); "
            "$certificate = $request.CreateSelfSigned($notBefore, $notAfter); "
            "[System.IO.File]::WriteAllText($certPath, $certificate.ExportCertificatePem()); "
            "[System.IO.File]::WriteAllText($keyPath, $rsa.ExportPkcs8PrivateKeyPem()); "
            "$store = [System.Security.Cryptography.X509Certificates.X509Store]::new('Root', 'CurrentUser'); "
            "$store.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite); "
            "$matches = $store.Certificates.Find("
            "[System.Security.Cryptography.X509Certificates.X509FindType]::FindByThumbprint, "
            "$certificate.Thumbprint, "
            "$false"
            "); "
            "if ($matches.Count -eq 0) { $store.Add($certificate) }; "
            "$store.Close()"
        )
        write_step("Exporting local TLS certificate material for Mailpit")

    run_command(
        [powershell_executable, "-NoProfile", "-Command", powershell_script],
        cwd=config.repo_root,
        check=True,
        capture_output=False,
        text=True,
    )
    return certificate_path, private_key_path


def probe_http_url(url: str, *, timeout_seconds: int = 5) -> tuple[bool, str | None]:
    """Check whether an HTTP endpoint is reachable.

    Args:
        url: URL to probe.
        timeout_seconds: Request timeout in seconds.

    Returns:
        Tuple of ``(reachable, detail)`` where ``detail`` is a failure reason when unreachable.
    """

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
        return False, detail or f"PowerShell probe exited with code {result.returncode}"

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
        return False, detail or f"curl exited with code {result.returncode}"

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
        return False, str(ex)


def start_backend_api_process(config: DevConfig) -> tuple[subprocess.Popen, Path]:
    """Start the backend API as a background process for temporary workflows.

    Args:
        config: CLI configuration containing backend project paths.

    Returns:
        Tuple of the launched process and the log file path.

    Raises:
        DevCliError: If ``dotnet`` is unavailable or the project file is missing.
    """

    assert_command_available("dotnet")
    backend_root = config.repo_root / "backend"
    project_path = config.repo_root / config.backend_project
    if not project_path.exists():
        raise DevCliError(f"Backend project not found: {project_path}")

    logs_dir = config.repo_root / ".dev-cli-logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / "backend-api.log"
    process = start_background_command(
        cmd=["dotnet", "run", "--project", str(project_path), "--no-restore", "--no-launch-profile"],
        cwd=backend_root,
        log_path=log_path,
        env=build_subprocess_env(
            extra={
                "ASPNETCORE_URLS": config.backend_base_url,
                "ASPNETCORE_ENVIRONMENT": "Development",
            }
        ),
    )
    return process, log_path


def stop_background_process(process: subprocess.Popen) -> None:
    """Terminate a background process started by the developer CLI.

    Args:
        process: Process to stop.

    Returns:
        None.
    """

    if process.poll() is not None:
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

    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

    process = subprocess.Popen(
        resolved_cmd,
        cwd=str(cwd),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        creationflags=creationflags,
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
            "Start the backend in another terminal with 'python ./scripts/dev.py up --skip-restore' "
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
    """Restore the backend solution.

    Args:
        config: CLI configuration containing backend solution paths.

    Returns:
        None.

    Raises:
        DevCliError: If ``dotnet`` is unavailable or restore fails.
    """

    assert_command_available("dotnet")
    backend_root = config.repo_root / "backend"
    solution_path = config.repo_root / config.backend_solution
    write_step("Restoring backend solution")
    run_command(["dotnet", "restore", str(solution_path)], cwd=backend_root)


def start_dependencies(config: DevConfig, *, include_keycloak: bool = True) -> None:
    """Start/reuse local dependencies and wait until they are ready.

    Args:
        config: CLI configuration containing compose and local dependency settings.
        include_keycloak: Whether to start and wait for Keycloak readiness.

    Returns:
        None.

    Raises:
        DevCliError: If Docker/compose is unavailable, the compose file is missing,
            or a required local dependency fails to start/become ready.
    """

    ensure_docker_daemon_available()
    ensure_postgres_tls_material_exported(config)
    ensure_mailpit_tls_material_exported(config)
    if include_keycloak and is_https_url(config.keycloak_ready_url):
        ensure_keycloak_https_certificate_exported(config)
    compose_full_path = config.repo_root / config.compose_file
    if not compose_full_path.exists():
        raise DevCliError(f"Compose file not found: {compose_full_path}")

    existing_state = get_docker_container_state(config.postgres_container_name)
    if existing_state == "running":
        write_step(f"Reusing existing PostgreSQL container '{config.postgres_container_name}' (already running)")
        wait_for_postgres(
            container_name=config.postgres_container_name,
            user=config.postgres_user,
            database=config.postgres_database,
        )
    elif existing_state is not None:
        write_step(
            f"Starting existing PostgreSQL container '{config.postgres_container_name}' "
            f"(state: {existing_state})"
        )
        run_command(["docker", "start", config.postgres_container_name])
        wait_for_postgres(
            container_name=config.postgres_container_name,
            user=config.postgres_user,
            database=config.postgres_database,
        )
    else:
        write_step("Starting PostgreSQL via docker compose")
        invoke_docker_compose(config, ["up", "-d", "postgres"])
        wait_for_postgres(
            container_name=config.postgres_container_name,
            user=config.postgres_user,
            database=config.postgres_database,
        )

    mailpit_state = get_docker_container_state(config.mailpit_container_name)
    if mailpit_state == "running":
        write_step(f"Reusing existing Mailpit container '{config.mailpit_container_name}' (already running)")
    elif mailpit_state is not None:
        write_step(
            f"Starting existing Mailpit container '{config.mailpit_container_name}' "
            f"(state: {mailpit_state})"
        )
        run_command(["docker", "start", config.mailpit_container_name])
    else:
        write_step("Starting Mailpit via docker compose")
        invoke_docker_compose(config, ["up", "-d", "mailpit"])

    wait_for_http_ready(url=config.mailpit_ready_url, description="Mailpit")

    if include_keycloak:
        keycloak_state = get_docker_container_state(config.keycloak_container_name)
        if keycloak_state == "running":
            write_step(f"Reusing existing Keycloak container '{config.keycloak_container_name}' (already running)")
        elif keycloak_state is not None:
            write_step(
                f"Starting existing Keycloak container '{config.keycloak_container_name}' "
                f"(state: {keycloak_state})"
            )
            run_command(["docker", "start", config.keycloak_container_name])
        else:
            write_step("Starting Keycloak via docker compose")
            invoke_docker_compose(config, ["up", "-d", "keycloak"])

        wait_for_http_ready(
            url=config.keycloak_ready_url,
            description="Keycloak",
            timeout_seconds=KEYCLOAK_READY_TIMEOUT_SECONDS,
        )


def stop_dependencies(config: DevConfig) -> None:
    """Stop docker compose dependencies while preserving named volumes.

    Args:
        config: CLI configuration containing compose and PostgreSQL settings.

    Returns:
        None.

    Raises:
        DevCliError: If the compose command fails.
    """

    write_step("Stopping local dependencies via docker compose")
    invoke_docker_compose(config, ["down"])
    remaining_state = get_docker_container_state(config.postgres_container_name)
    if remaining_state is not None:
        print(
            f"Note: container '{config.postgres_container_name}' still exists "
            "(likely not created by this compose project)."
        )
        print(f"Stop it manually if desired: docker stop {config.postgres_container_name}")
    mailpit_state = get_docker_container_state(config.mailpit_container_name)
    if mailpit_state is not None:
        print(
            f"Note: container '{config.mailpit_container_name}' still exists "
            "(likely not created by this compose project)."
        )
        print(f"Stop it manually if desired: docker stop {config.mailpit_container_name}")
    keycloak_state = get_docker_container_state(config.keycloak_container_name)
    if keycloak_state is not None:
        print(
            f"Note: container '{config.keycloak_container_name}' still exists "
            "(likely not created by this compose project)."
        )
        print(f"Stop it manually if desired: docker stop {config.keycloak_container_name}")


def show_status(config: DevConfig) -> None:
    """Show docker compose and dependency readiness status.

    Args:
        config: CLI configuration containing compose and dependency settings.

    Returns:
        None.
    """

    write_step("docker compose status")
    invoke_docker_compose(config, ["ps"])

    state = get_docker_container_state(config.postgres_container_name)
    if state is None:
        print(f"Container '{config.postgres_container_name}' was not found.")
        return

    write_step("Named PostgreSQL container status")
    print(f"{config.postgres_container_name} : {state}")

    write_step("PostgreSQL readiness")
    result = run_command(
        [
            "docker",
            "exec",
            config.postgres_container_name,
            "pg_isready",
            "-U",
            config.postgres_user,
            "-d",
            config.postgres_database,
        ],
        check=False,
        capture_output=False,
        text=True,
    )
    if result.returncode != 0:
        print("Warning: PostgreSQL container is not ready (or container is not running).")

    mailpit_state = get_docker_container_state(config.mailpit_container_name)
    if mailpit_state is None:
        print(f"Container '{config.mailpit_container_name}' was not found.")
        return

    write_step("Named Mailpit container status")
    print(f"{config.mailpit_container_name} : {mailpit_state}")

    write_step("Mailpit readiness")
    mailpit_ready, mailpit_detail = probe_http_url(config.mailpit_ready_url)
    if mailpit_ready:
        print(f"{config.mailpit_ready_url} : ready")
    else:
        print(f"Warning: Mailpit readiness check failed: {mailpit_detail or 'unreachable'}")

    keycloak_state = get_docker_container_state(config.keycloak_container_name)
    if keycloak_state is None:
        print(f"Container '{config.keycloak_container_name}' was not found.")
        return

    write_step("Named Keycloak container status")
    print(f"{config.keycloak_container_name} : {keycloak_state}")

    write_step("Keycloak readiness")
    keycloak_ready, keycloak_detail = probe_http_url(config.keycloak_ready_url)
    if keycloak_ready:
        print(f"{config.keycloak_ready_url} : ready")
    else:
        print(f"Warning: Keycloak readiness check failed: {keycloak_detail or 'unreachable'}")


def run_backend_api(config: DevConfig, *, do_restore: bool) -> None:
    """Run the backend API project, optionally restoring first.

    Args:
        config: CLI configuration containing backend project paths.
        do_restore: Whether to run ``dotnet restore`` before starting the API.

    Returns:
        None.

    Raises:
        DevCliError: If ``dotnet`` is unavailable, the project file is missing,
            or restore/run commands fail.
    """

    assert_command_available("dotnet")
    if is_https_url(config.backend_base_url):
        ensure_dotnet_dev_certificate_trusted()

    backend_root = config.repo_root / "backend"
    project_path = config.repo_root / config.backend_project
    if not project_path.exists():
        raise DevCliError(f"Backend project not found: {project_path}")

    if do_restore:
        write_step("Restoring backend project")
        run_command(["dotnet", "restore", str(project_path)], cwd=backend_root)

    write_step(f"Starting backend API at {config.backend_base_url} (Ctrl+C to stop)")
    run_command(
        ["dotnet", "run", "--project", str(project_path), "--no-launch-profile"],
        cwd=backend_root,
        check=True,
        env=build_subprocess_env(
            extra={
                "ASPNETCORE_URLS": config.backend_base_url,
                "ASPNETCORE_ENVIRONMENT": "Development",
            }
        ),
    )


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

    if bootstrap:
        ensure_submodules(config)

    assert_command_available("dotnet")
    assert_command_available("npm")
    if is_https_url(config.frontend_base_url):
        ensure_dotnet_dev_certificate_trusted()

    frontend_root = config.repo_root / config.frontend_root
    project_path = config.repo_root / config.frontend_web_project
    solution_path = config.repo_root / config.frontend_solution
    package_path = config.repo_root / config.frontend_package_json

    if not frontend_root.exists():
        raise DevCliError(f"Frontend submodule not found: {frontend_root}")
    if not project_path.exists():
        raise DevCliError(f"Frontend web project not found: {project_path}")
    if not solution_path.exists():
        raise DevCliError(f"Frontend solution not found: {solution_path}")
    if not package_path.exists():
        raise DevCliError(f"Frontend package manifest not found: {package_path}")

    if do_npm_install:
        npm_cmd = ["npm", "ci"] if (frontend_root / "package-lock.json").exists() else ["npm", "install"]
        write_step("Installing frontend npm dependencies")
        run_command(npm_cmd, cwd=frontend_root)

    if do_css_build:
        write_step("Building frontend Tailwind CSS")
        run_command(["npm", "run", "css:build"], cwd=frontend_root)

    if do_restore:
        write_step("Restoring frontend web project")
        run_command(["dotnet", "restore", str(project_path)], cwd=frontend_root)

    keycloak_ready, keycloak_detail = probe_http_url(config.keycloak_ready_url)
    if not keycloak_ready:
        print(
            "Warning: local Keycloak is not reachable. "
            "Frontend sign-in will stay unavailable until auth dependencies are started."
        )
        if keycloak_detail:
            print(f"Keycloak probe detail: {keycloak_detail}")
        print("Start auth dependencies with: python ./scripts/dev.py up --dependencies-only")

    css_watch_process: subprocess.Popen | None = None
    css_watch_log_path: Path | None = None
    try:
        if hot_reload:
            logs_dir = config.repo_root / ".dev-cli-logs"
            css_watch_log_path = logs_dir / "frontend-css-watch.log"
            write_step("Starting frontend Tailwind watch in the background")
            css_watch_process = start_background_command(
                cmd=["npm", "run", "css:watch"],
                cwd=frontend_root,
                log_path=css_watch_log_path,
            )
            print(f"Tailwind watch log: {css_watch_log_path}")

        launch_mode = "with hot reload" if hot_reload else "without hot reload"
        write_step(f"Starting frontend web UI {launch_mode} at {config.frontend_base_url} (Ctrl+C to stop)")
        while True:
            result = run_command(
                get_frontend_web_launch_command(project_path, hot_reload=hot_reload),
                cwd=frontend_root,
                check=False,
                env=build_frontend_web_environment(frontend_url=config.frontend_base_url, hot_reload=hot_reload),
            )
            if result.returncode == 0:
                break

            if hot_reload and is_known_dotnet_watch_enc_crash(return_code=result.returncode):
                print(
                    "dotnet watch exited due a known Roslyn hot-reload compiler crash. "
                    "Restarting watch automatically in 2 seconds..."
                )
                time.sleep(2)
                continue

            raise DevCliError(
                f"Frontend web UI exited unexpectedly (exit code {result.returncode})."
            )
    finally:
        if css_watch_process is not None:
            write_step("Stopping frontend Tailwind watch")
            stop_background_process(css_watch_process)


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
    """Run dependencies, backend API, and frontend web UI together for local development.

    Args:
        config: CLI configuration containing repository paths and defaults.
        bootstrap: Whether to initialize submodules before running.
        do_backend_restore: Whether to restore the backend solution before launch.
        do_frontend_npm_install: Whether to install frontend JavaScript dependencies first.
        do_frontend_css_build: Whether to build Tailwind CSS before launching the frontend.
        do_frontend_restore: Whether to restore the frontend web project before launch.
        hot_reload: Whether to enable frontend hot reload, including Tailwind watch.
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

    assert_command_available("dotnet")
    assert_command_available("npm")
    if is_https_url(frontend_url):
        ensure_dotnet_dev_certificate_trusted()

    start_dependencies(config)

    if do_backend_restore:
        restore_backend(config)

    frontend_root = config.repo_root / config.frontend_root
    project_path = config.repo_root / config.frontend_web_project
    if not frontend_root.exists():
        raise DevCliError(f"Frontend submodule not found: {frontend_root}")
    if not project_path.exists():
        raise DevCliError(f"Frontend web project not found: {project_path}")

    if do_frontend_npm_install:
        npm_cmd = ["npm", "ci"] if (frontend_root / "package-lock.json").exists() else ["npm", "install"]
        write_step("Installing frontend npm dependencies")
        run_command(npm_cmd, cwd=frontend_root)

    if do_frontend_css_build:
        write_step("Building frontend Tailwind CSS")
        run_command(["npm", "run", "css:build"], cwd=frontend_root)

    if do_frontend_restore:
        write_step("Restoring frontend web project")
        run_command(["dotnet", "restore", str(project_path)], cwd=frontend_root)

    backend_process: subprocess.Popen | None = None
    frontend_process: subprocess.Popen | None = None
    css_watch_process: subprocess.Popen | None = None
    backend_log_path: Path | None = None
    frontend_log_path: Path | None = None
    css_watch_log_path: Path | None = None

    try:
        write_step("Starting backend API in the background")
        backend_process, backend_log_path = start_background_command_with_log(
            cmd=["dotnet", "run", "--project", str(config.repo_root / config.backend_project), "--no-restore", "--no-launch-profile"],
            cwd=config.repo_root / "backend",
            log_name="backend-api.log",
            env=build_subprocess_env(
                extra={
                    "ASPNETCORE_URLS": backend_url,
                    "ASPNETCORE_ENVIRONMENT": "Development",
                }
            ),
            config=config,
        )
        print(f"Backend log: {backend_log_path}")
        wait_for_http_ready(url=f"{backend_url.rstrip('/')}/health/live", description="Backend API")

        keycloak_ready, keycloak_detail = probe_http_url(config.keycloak_ready_url)
        if not keycloak_ready:
            print("Warning: local Keycloak is not reachable. Frontend sign-in will remain unavailable.")
            if keycloak_detail:
                print(f"Keycloak probe detail: {keycloak_detail}")

        if hot_reload:
            css_watch_log_path = (config.repo_root / ".dev-cli-logs") / "frontend-css-watch.log"
            write_step("Starting frontend Tailwind watch in the background")
            css_watch_process = start_background_command(
                cmd=["npm", "run", "css:watch"],
                cwd=frontend_root,
                log_path=css_watch_log_path,
            )
            print(f"Tailwind watch log: {css_watch_log_path}")

        launch_mode = "with hot reload" if hot_reload else "without hot reload"
        write_step(f"Starting frontend web UI {launch_mode} in the background")
        frontend_process, frontend_log_path = start_frontend_web_process_with_log(
            config,
            frontend_url=frontend_url,
            hot_reload=hot_reload,
        )
        print(f"Frontend log: {frontend_log_path}")
        wait_for_http_ready(url=frontend_url, description="Frontend web UI")

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
        if css_watch_process is not None and css_watch_log_path is not None:
            state["css_watch"] = {
                "pid": css_watch_process.pid,
                "log_path": str(css_watch_log_path),
            }

        state_path = save_web_stack_state(config, state=state)
        print(f"Web stack state: {state_path}")

        if open_browser_on_ready:
            write_step(f"Opening browser to {frontend_url}")
            webbrowser.open(frontend_url)

        print("Local web stack is running. Press Ctrl+C to stop backend, frontend, and CSS watch.")
        while True:
            time.sleep(2)

            if backend_process.poll() is not None:
                raise DevCliError(
                    f"Backend API exited unexpectedly. Review log: {backend_log_path}"
                )

            if frontend_process.poll() is not None:
                frontend_return_code = frontend_process.returncode or 0
                if hot_reload and is_known_dotnet_watch_enc_crash(
                    return_code=frontend_return_code,
                    log_path=frontend_log_path,
                ):
                    write_step(
                        "Frontend dotnet watch hit a known Roslyn hot-reload compiler crash; restarting automatically"
                    )
                    frontend_process, frontend_log_path = start_frontend_web_process_with_log(
                        config,
                        frontend_url=frontend_url,
                        hot_reload=hot_reload,
                    )
                    print(f"Frontend log: {frontend_log_path}")
                    wait_for_http_ready(url=frontend_url, description="Frontend web UI")

                    state["frontend"] = {
                        "pid": frontend_process.pid,
                        "url": frontend_url,
                        "log_path": str(frontend_log_path),
                    }
                    save_web_stack_state(config, state=state)
                    continue

                raise DevCliError(
                    f"Frontend web UI exited unexpectedly (exit code {frontend_return_code}). "
                    f"Review log: {frontend_log_path}"
                )
    except KeyboardInterrupt:
        print("\nStopping local web stack.")
    finally:
        clear_web_stack_state(config)
        if frontend_process is not None:
            write_step("Stopping frontend web UI")
            stop_background_process(frontend_process)
        if css_watch_process is not None:
            write_step("Stopping frontend Tailwind watch")
            stop_background_process(css_watch_process)
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
        stop_dependencies_too: Whether to also stop Docker Compose dependencies.

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

    return start_background_command_with_log(
        cmd=get_frontend_web_launch_command(project_path, hot_reload=hot_reload),
        cwd=frontend_root,
        log_name="frontend-web.log",
        config=config,
        env=build_frontend_web_environment(frontend_url=frontend_url, hot_reload=hot_reload),
    )


def run_tests(config: DevConfig, *, run_integration: bool, restore: bool = True) -> None:
    """Run backend unit tests and optionally integration tests.

    Args:
        config: CLI configuration containing backend test project paths.
        run_integration: Whether to run integration tests after unit tests.
        restore: Whether each ``dotnet test`` invocation should restore packages first.

    Returns:
        None.

    Raises:
        DevCliError: If ``dotnet`` is unavailable or any required test command fails.
    """

    assert_command_available("dotnet")
    backend_root = config.repo_root / "backend"
    unit_project = config.repo_root / "backend/tests/Board.ThirdPartyLibrary.Api.Tests/Board.ThirdPartyLibrary.Api.Tests.csproj"
    integration_project = (
        config.repo_root
        / "backend/tests/Board.ThirdPartyLibrary.Api.IntegrationTests/Board.ThirdPartyLibrary.Api.IntegrationTests.csproj"
    )
    restore_args = [] if restore else ["--no-restore"]

    write_step("Running backend unit tests")
    run_command(
        ["dotnet", "test", str(unit_project), *restore_args, "--filter", "Category!=Integration"],
        cwd=backend_root,
    )

    if run_integration:
        write_step("Running backend integration tests (Docker/Testcontainers required)")
        run_command(
            ["dotnet", "test", str(integration_project), *restore_args, "--filter", "Category=Integration"],
            cwd=backend_root,
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


def validate_backend_xml_docs(config: DevConfig) -> None:
    """Build the backend API project with XML documentation warnings enabled.

    Args:
        config: CLI configuration containing backend project paths.

    Returns:
        None.

    Raises:
        DevCliError: If ``dotnet`` is unavailable or the documentation validation build fails.
    """

    assert_command_available("dotnet")
    backend_root = config.repo_root / "backend"
    project_path = config.repo_root / config.backend_project

    write_step("Validating backend XML documentation coverage")
    run_command(
        [
            "dotnet",
            "build",
            str(project_path),
            "--no-restore",
            "/warnaserror:CS1573,CS1591",
        ],
        cwd=backend_root,
    )


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
    start_backend: bool,
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
        start_backend: Whether to start the local backend automatically for the run.
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

    backend_process: subprocess.Popen | None = None
    if start_backend:
        if not is_local_http_url(base_url):
            raise DevCliError("--start-backend can only be used with a local base URL.")
        if is_https_url(base_url):
            ensure_dotnet_dev_certificate_trusted()
        start_dependencies(config, include_keycloak=False)
        write_step("Starting backend API in the background for contract tests")
        backend_process, backend_log_path = start_backend_api_process(config)
        try:
            wait_for_http_ready(url=base_url, description="backend API", timeout_seconds=60)
        except DevCliError as ex:
            stop_background_process(backend_process)
            log_excerpt = ""
            if backend_log_path.exists():
                log_excerpt = backend_log_path.read_text(encoding="utf-8", errors="replace").strip()
            raise DevCliError(
                f"{ex}\nBackend startup log: {backend_log_path}"
                + (f"\n{log_excerpt}" if log_excerpt else "")
            ) from ex
    else:
        ensure_api_base_url_reachable(base_url)

    write_step("Running API contract tests with Postman CLI")
    try:
        run_command(
            [
                "postman",
                "collection",
                "run",
                str(collection_path),
                "--environment",
                str(environment_path),
                "--env-var",
                f"baseUrl={base_url}",
                "--env-var",
                f"contractExecutionMode={contract_execution_mode}",
                "--bail",
                "failure",
                "--reporters",
                "cli,junit",
                "--reporter-junit-export",
                str(report_path),
                "--working-dir",
                str(api_root),
                *(["--insecure"] if is_local_http_url(base_url) and is_https_url(base_url) else []),
            ],
            cwd=api_root,
        )
    finally:
        if backend_process is not None:
            write_step("Stopping background backend API")
            stop_background_process(backend_process)


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
        config: CLI configuration containing repository and compose settings.

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
        write_step("Docker Compose version")
        result = run_command(["docker", "compose", "version"], check=False, capture_output=False)
        if result.returncode != 0:
            issues.append("Docker Compose is unavailable (`docker compose version` failed)")
        daemon_check = run_command(["docker", "info"], check=False, capture_output=True, text=True)
        if daemon_check.returncode != 0:
            issues.append("Docker daemon is not reachable (start Docker Desktop/Engine)")

    compose_full_path = config.repo_root / config.compose_file
    if compose_full_path.exists():
        print(f"Compose file found: {compose_full_path}")
    else:
        print(f"Compose file missing: {compose_full_path}")
        issues.append(f"Compose file not found: {compose_full_path}")

    print()
    write_step("Doctor summary")
    if issues:
        print(f"FAIL ({len(issues)} issue(s) detected)")
        for idx, issue in enumerate(issues, start=1):
            print(f"{idx}. {issue}")
        print()
        print("Suggested next steps:")
        print("  python ./scripts/dev.py bootstrap")
        print("  python ./scripts/dev.py web --hot-reload")
        print("  python ./scripts/dev.py frontend --hot-reload")
        print("  python ./scripts/dev.py up --dependencies-only")
        print("  python ./scripts/dev.py up --skip-restore")
        print("  python ./scripts/dev.py all-tests")
        print("  python ./scripts/dev.py api-test --start-backend --skip-lint")
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
        print("  python ./scripts/dev.py web --hot-reload")
        print("  python ./scripts/dev.py frontend --hot-reload")
        print("  python ./scripts/dev.py up --dependencies-only")
        print("  python ./scripts/dev.py up --skip-restore")
        print("  python ./scripts/dev.py all-tests")
        print("  python ./scripts/dev.py api-test --start-backend --skip-lint")
        print("  python ./scripts/dev.py api-lint")


def run_verify(
    config: DevConfig,
    *,
    run_integration: bool,
    run_contract_tests: bool,
    environment_path: Path,
    base_url: str,
    contract_execution_mode: str,
    report_path: Path,
    start_backend: bool,
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
        start_backend: Whether to auto-start the backend for contract runs.

    Returns:
        None.
    """

    restore_backend(config)
    validate_backend_xml_docs(config)
    run_tests(config, run_integration=run_integration, restore=False)
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
        start_backend=start_backend,
    )


def run_all_tests(
    config: DevConfig,
    *,
    bootstrap: bool,
    environment_path: Path,
    base_url: str,
    contract_execution_mode: str,
    report_path: Path,
    start_backend: bool,
) -> None:
    """Run the full cross-repository validation workflow in one command.

    Args:
        config: CLI configuration containing backend, frontend, and API paths.
        bootstrap: Whether to initialize submodules first when needed.
        environment_path: Postman environment file for contract runs.
        base_url: Base URL used for API contract execution.
        contract_execution_mode: Contract execution mode (`live` or `mock`).
        report_path: JUnit report output path for Postman CLI contract runs.
        start_backend: Whether to auto-start backend/dependencies for contract runs.

    Returns:
        None.
    """

    if bootstrap:
        ensure_submodules(config)

    restore_backend(config)
    validate_backend_xml_docs(config)
    run_tests(config, run_integration=True, restore=False)

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
        start_backend=start_backend,
    )


def ensure_postgres_running_for_db_ops(config: DevConfig) -> None:
    """Ensure PostgreSQL is running before DB helper commands execute.

    Args:
        config: CLI configuration containing PostgreSQL container settings.

    Returns:
        None.

    Raises:
        DevCliError: If the configured PostgreSQL container is not running or
            readiness checks fail.
    """

    state = get_docker_container_state(config.postgres_container_name)
    if state != "running":
        raise DevCliError(
            f"PostgreSQL container '{config.postgres_container_name}' is not running. "
            "Start it first with 'python ./scripts/dev.py up --dependencies-only' (or 'up')."
        )
    wait_for_postgres(
        container_name=config.postgres_container_name,
        user=config.postgres_user,
        database=config.postgres_database,
    )


def default_backup_path(repo_root: Path, database_name: str) -> Path:
    """Build a timestamped default SQL backup path inside ``./backups/``.

    Args:
        repo_root: Repository root directory.
        database_name: Database name to include in the filename.

    Returns:
        A timestamped SQL backup file path under ``<repo_root>/backups``.
    """

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return repo_root / "backups" / f"{database_name}-{timestamp}.sql"


def db_backup(config: DevConfig, *, output_path: Path | None) -> None:
    """Create a SQL backup using ``pg_dump`` from the Dockerized PostgreSQL instance.

    Args:
        config: CLI configuration containing PostgreSQL container settings.
        output_path: Optional explicit backup output path. When ``None``, a
            timestamped path under ``./backups`` is generated.

    Returns:
        None.

    Raises:
        DevCliError: If Docker is unavailable, PostgreSQL is not running/ready,
            or the backup command fails.
    """

    assert_command_available("docker")
    ensure_postgres_running_for_db_ops(config)

    target = (output_path or default_backup_path(config.repo_root, config.postgres_database)).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    write_step(f"Backing up database '{config.postgres_database}' to {target}")
    cmd = [
        "docker",
        "exec",
        config.postgres_container_name,
        "pg_dump",
        "-U",
        config.postgres_user,
        "-d",
        config.postgres_database,
        "--format=plain",
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-privileges",
        "--encoding=UTF8",
    ]

    with target.open("wb") as out_file:
        result = subprocess.run(cmd, stdout=out_file, stderr=subprocess.PIPE, check=False)

    if result.returncode != 0:
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass
        stderr_text = (result.stderr or b"").decode(errors="replace").strip()
        raise DevCliError(
            f"Database backup failed ({result.returncode}): {quote_cmd(cmd)}"
            + (f"\n{stderr_text}" if stderr_text else "")
        )

    print(f"Backup complete: {target}")


def db_restore(config: DevConfig, *, input_path: Path) -> None:
    """Restore a SQL backup into the configured database using ``psql``.

    Args:
        config: CLI configuration containing PostgreSQL container settings.
        input_path: Path to the SQL backup file to restore.

    Returns:
        None.

    Raises:
        DevCliError: If the backup file is missing, Docker is unavailable,
            PostgreSQL is not running/ready, or the restore command fails.
    """

    assert_command_available("docker")
    source = input_path.resolve()
    if not source.exists():
        raise DevCliError(f"Backup file not found: {source}")

    ensure_postgres_running_for_db_ops(config)
    write_step(f"Restoring database '{config.postgres_database}' from {source}")
    cmd = [
        "docker",
        "exec",
        "-i",
        config.postgres_container_name,
        "psql",
        "-v",
        "ON_ERROR_STOP=1",
        "-U",
        config.postgres_user,
        "-d",
        config.postgres_database,
    ]

    with source.open("rb") as in_file:
        result = subprocess.run(cmd, stdin=in_file, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)

    if result.returncode != 0:
        stderr_text = (result.stderr or b"").decode(errors="replace").strip()
        raise DevCliError(
            f"Database restore failed ({result.returncode}): {quote_cmd(cmd)}"
            + (f"\n{stderr_text}" if stderr_text else "")
        )

    print("Restore complete.")


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
    shared.add_argument(
        "--compose-file",
        "-ComposeFile",
        default="backend/docker-compose.yml",
        help="Docker Compose file path",
    )
    shared.add_argument(
        "--postgres-container-name",
        "-PostgresContainerName",
        default="board_tpl_postgres",
        help="PostgreSQL container name",
    )
    shared.add_argument("--postgres-user", "-PostgresUser", default="board_tpl_user", help="PostgreSQL user")
    shared.add_argument(
        "--postgres-database",
        "-PostgresDatabase",
        default="board_tpl",
        help="PostgreSQL database name",
    )
    shared.add_argument(
        "--keycloak-container-name",
        "-KeycloakContainerName",
        default="board_tpl_keycloak",
        help="Keycloak container name",
    )
    shared.add_argument(
        "--keycloak-ready-url",
        "-KeycloakReadyUrl",
        default="https://localhost:8443/realms/board-third-party-library/.well-known/openid-configuration",
        help="Keycloak readiness URL",
    )
    shared.add_argument(
        "--backend-project",
        "-BackendProject",
        default="backend/src/Board.ThirdPartyLibrary.Api/Board.ThirdPartyLibrary.Api.csproj",
        help="Backend API project path",
    )
    shared.add_argument(
        "--backend-solution",
        "-BackendSolution",
        default="backend/Board.ThirdPartyLibrary.Backend.sln",
        help="Backend solution path",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "bootstrap",
        parents=[shared],
        help="Initialize submodules and restore backend solution",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    up = subparsers.add_parser(
        "up",
        parents=[shared],
        help="Start/reuse PostgreSQL and Keycloak and run backend API",
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
        help="Skip dotnet restore before dotnet watch run",
    )

    frontend = subparsers.add_parser(
        "frontend",
        parents=[shared],
        help="Run the frontend web UI from the repository root",
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
        help="Skip the pre-launch Tailwind CSS build",
    )
    frontend.add_argument(
        "--skip-restore",
        "-SkipRestore",
        action="store_true",
        help="Skip dotnet restore before dotnet watch run",
    )
    frontend.add_argument(
        "--hot-reload",
        "-HotReload",
        action="store_true",
        help="Enable frontend hot reload, including Tailwind watch, while the app is running",
    )

    web = subparsers.add_parser(
        "web",
        parents=[shared],
        help="Run dependencies, backend API, and frontend web UI together",
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
        help="Skip backend dotnet restore before startup",
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
        help="Skip the pre-launch Tailwind CSS build",
    )
    web.add_argument(
        "--skip-frontend-restore",
        "-SkipFrontendRestore",
        action="store_true",
        help="Skip frontend dotnet restore before startup",
    )
    web.add_argument(
        "--hot-reload",
        "-HotReload",
        action="store_true",
        help="Enable frontend hot reload, including Tailwind watch, while the app is running",
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
        default="https://localhost:7085",
        help="Backend URL to bind and probe",
    )
    web.add_argument(
        "--frontend-url",
        "-FrontendUrl",
        default="https://localhost:7277",
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
        help="Also stop Docker Compose dependencies after stopping app processes",
    )

    subparsers.add_parser(
        "down",
        parents=[shared],
        help="Stop local dependencies via docker compose (preserves named volumes)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    subparsers.add_parser(
        "status",
        parents=[shared],
        help="Show docker compose and local dependency readiness status",
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
        help="Run backend/frontend tests, docs validation, API lint, and API contract tests",
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
        default="api/postman/environments/board-third-party-library_local.postman_environment.json",
        help="Postman environment file path used for contract tests",
    )
    all_tests.add_argument(
        "--base-url",
        "-BaseUrl",
        default="https://localhost:7085",
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
        "--no-start-backend",
        "-NoStartBackend",
        action="store_true",
        help="Do not auto-start local dependencies/backend for contract tests",
    )

    verify = subparsers.add_parser(
        "verify",
        parents=[shared],
        help="Run backend XML doc validation, backend tests, API lint, and optional contract tests",
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
        default="api/postman/environments/board-third-party-library_local.postman_environment.json",
        help="Postman environment file path used when contract tests run",
    )
    verify.add_argument(
        "--base-url",
        "-BaseUrl",
        default="https://localhost:7085",
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
        "--start-backend",
        "-StartBackend",
        action="store_true",
        help="Start local dependencies and the backend automatically for contract tests",
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
        default="api/postman/environments/board-third-party-library_local.postman_environment.json",
        help="Postman environment file path",
    )
    api_test.add_argument(
        "--base-url",
        "-BaseUrl",
        default="https://localhost:7085",
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
        "--start-backend",
        "-StartBackend",
        action="store_true",
        help="Start local dependencies and the backend API automatically for the collection run",
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
        default="api/postman/environments/board-third-party-library_mock-admin.postman_environment.json",
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

    backup = subparsers.add_parser(
        "db-backup",
        parents=[shared],
        help="Create a SQL backup of the local PostgreSQL database",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    backup.add_argument(
        "output",
        nargs="?",
        type=Path,
        help="Output .sql path (defaults to ./backups/<db>-<utc-timestamp>.sql)",
    )

    restore = subparsers.add_parser(
        "db-restore",
        parents=[shared],
        help="Restore a SQL backup into the local PostgreSQL database",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    restore.add_argument("input", type=Path, help="Path to a .sql backup file created by db-backup")

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
        compose_file=args.compose_file,
        postgres_container_name=args.postgres_container_name,
        postgres_user=args.postgres_user,
        postgres_database=args.postgres_database,
        mailpit_container_name="board_tpl_mailpit",
        mailpit_ready_url="https://localhost:8025/readyz",
        keycloak_container_name=args.keycloak_container_name,
        keycloak_ready_url=args.keycloak_ready_url,
        backend_project=args.backend_project,
        backend_solution=args.backend_solution,
        frontend_root="frontend",
        frontend_web_project="frontend/src/Board.ThirdPartyLibrary.Frontend.Web/Board.ThirdPartyLibrary.Frontend.Web.csproj",
        frontend_solution="frontend/Board.ThirdPartyLibrary.Frontend.slnx",
        frontend_package_json="frontend/package.json",
        backend_base_url="https://localhost:7085",
        frontend_base_url="https://localhost:7277",
        api_root="api",
        api_spec="api/postman/specs/board-third-party-library-api.v1.openapi.yaml",
        api_contract_collection="api/postman/collections/board-third-party-library-api.contract-tests.postman_collection.json",
        api_local_environment="api/postman/environments/board-third-party-library_local.postman_environment.json",
        api_mock_environment="api/postman/environments/board-third-party-library_mock.postman_environment.json",
        api_mock_admin_environment="api/postman/environments/board-third-party-library_mock-admin.postman_environment.json",
        api_mock_provision_script="api/scripts/postman-provision-mock.mjs",
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
                start_backend=not args.no_start_backend,
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
                start_backend=args.start_backend,
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
                start_backend=args.start_backend,
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
        elif args.command == "db-backup":
            db_backup(config, output_path=args.output)
        elif args.command == "db-restore":
            db_restore(config, input_path=args.input)
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
