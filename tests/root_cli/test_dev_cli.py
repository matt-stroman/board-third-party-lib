"""Focused unit coverage for maintained developer CLI helpers."""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
import urllib.parse
from unittest import mock


def load_dev_cli_module():
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    module_path = repo_root / "scripts" / "dev.py"
    spec = importlib.util.spec_from_file_location("board_enthusiasts_dev_cli", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load scripts/dev.py for testing.")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


dev = load_dev_cli_module()


class DevCliMigrationHelperTests(unittest.TestCase):
    """Covers the pure helper logic used by the maintained developer CLI."""

    @staticmethod
    def create_args() -> argparse.Namespace:
        """Create a minimal argument namespace for config construction."""

        return argparse.Namespace()

    def test_is_local_supabase_url_reports_expected_values(self) -> None:
        self.assertTrue(dev.is_local_http_url("http://127.0.0.1:54321"))
        self.assertTrue(dev.is_local_http_url("https://localhost:7277"))
        self.assertFalse(dev.is_local_http_url("https://staging.boardenthusiasts.com"))

    def test_config_from_args_keeps_root_relative_migration_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()

            config = dev.config_from_args(args, repo_root)

            self.assertEqual("frontend", config.migration_spa_root)
            self.assertEqual("backend/apps/workers-api", config.migration_workers_root)
            self.assertEqual("backend/supabase", config.supabase_root)
            self.assertEqual("config/.env.local.example", config.local_env_example)
            self.assertEqual("config/.env.staging.example", config.staging_env_example)
            self.assertEqual("config/.env.example", config.production_env_example)
            self.assertEqual("config/.env.local", config.local_env_file)
            self.assertEqual("config/.env.staging", config.staging_env_file)
            self.assertEqual("config/.env", config.production_env_file)
            self.assertEqual("cloudflare/fallback-pages", config.cloudflare_fallback_pages_root)

    def test_apply_runtime_base_url_overrides_respects_local_port_env(self) -> None:
        args = self.create_args()
        config = dev.config_from_args(args, pathlib.Path.cwd())

        with mock.patch.dict(
            dev.os.environ,
            {
                "BOARD_ENTHUSIASTS_LOCAL_WORKERS_PORT": "58877",
                "BOARD_ENTHUSIASTS_LOCAL_FRONTEND_PORT": "54173",
            },
            clear=False,
        ):
            overridden = dev.apply_runtime_base_url_overrides(config)

        self.assertEqual("http://127.0.0.1:58877", overridden.backend_base_url)
        self.assertEqual("http://127.0.0.1:58877", overridden.migration_workers_base_url)
        self.assertEqual("http://127.0.0.1:54173", overridden.frontend_base_url)
        self.assertEqual("http://127.0.0.1:54173", overridden.migration_spa_base_url)

    def test_build_migration_workspace_command_uses_workspace_name(self) -> None:
        command = dev.build_workspace_npm_command(
            script_name="dev",
            workspace_name="@board-enthusiasts/spa",
        )

        self.assertEqual(
            ["npm", "run", "dev", "--workspace", "@board-enthusiasts/spa"],
            command,
        )

    def test_resolve_supabase_command_prefix_prefers_standalone_cli(self) -> None:
        with mock.patch.object(dev.shutil, "which", side_effect=lambda name: "C:/tools/supabase.exe" if name == "supabase" else None):
            self.assertEqual(["supabase"], dev.resolve_supabase_command_prefix())

    def test_resolve_supabase_command_prefix_uses_non_interactive_npx_fallback(self) -> None:
        def fake_which(name: str) -> str | None:
            if name == "supabase":
                return None
            if name == "npx":
                return "C:/Program Files/nodejs/npx.cmd"
            return None

        with mock.patch.object(dev.shutil, "which", side_effect=fake_which):
            self.assertEqual(["npx", "--yes", "supabase"], dev.resolve_supabase_command_prefix())

    def test_is_process_running_returns_false_when_windows_tasklist_times_out(self) -> None:
        with (
            mock.patch.object(dev.os, "name", "nt"),
            mock.patch.object(
                dev,
                "run_command",
                side_effect=subprocess.TimeoutExpired(
                    cmd=["tasklist", "/FI", "PID eq 1234"],
                    timeout=dev.PROCESS_STATUS_TIMEOUT_SECONDS,
                ),
            ),
        ):
            self.assertFalse(dev.is_process_running(1234))

    def test_stop_process_by_pid_raises_guidance_when_windows_taskkill_times_out(self) -> None:
        with (
            mock.patch.object(dev.os, "name", "nt"),
            mock.patch.object(dev, "is_process_running", return_value=True),
            mock.patch.object(
                dev,
                "run_command",
                side_effect=subprocess.TimeoutExpired(
                    cmd=["taskkill", "/PID", "1234", "/T", "/F"],
                    timeout=dev.PROCESS_STOP_TIMEOUT_SECONDS,
                ),
            ),
        ):
            with self.assertRaises(dev.DevCliError) as raised:
                dev.stop_process_by_pid(1234)

        self.assertIn("Timed out while stopping a tracked local process", str(raised.exception))
        self.assertIn("web clean", str(raised.exception))

    def test_handle_api_down_succeeds_when_runtime_downgrade_cannot_refresh(self) -> None:
        config = dev.config_from_args(self.create_args(), pathlib.Path.cwd())

        with (
            mock.patch.object(dev, "stop_frontend_service") as stop_frontend,
            mock.patch.object(dev, "stop_backend_service") as stop_backend,
            mock.patch.object(
                dev,
                "restart_runtime_profile",
                side_effect=dev.DevCliError("Docker daemon is not reachable."),
            ) as restart_runtime,
            mock.patch.object(dev, "clear_runtime_profile_state") as clear_runtime_state,
            mock.patch("builtins.print") as print_mock,
        ):
            dev.handle_api_down(config, include_dependencies=False)

        stop_frontend.assert_called_once_with(config)
        stop_backend.assert_called_once_with(config)
        restart_runtime.assert_called_once_with(config, profile=dev.SUPABASE_PROFILE_AUTH)
        clear_runtime_state.assert_called_once_with(config)
        printed = "\n".join(str(call.args[0]) for call in print_mock.call_args_list if call.args)
        self.assertIn("API runtime stopped.", printed)
        self.assertIn("Auth/database availability could not be refreshed", printed)

    def test_handle_auth_down_succeeds_when_runtime_downgrade_cannot_refresh(self) -> None:
        config = dev.config_from_args(self.create_args(), pathlib.Path.cwd())

        with (
            mock.patch.object(dev, "stop_frontend_service") as stop_frontend,
            mock.patch.object(dev, "stop_backend_service") as stop_backend,
            mock.patch.object(
                dev,
                "restart_runtime_profile",
                side_effect=dev.DevCliError("Docker daemon is not reachable."),
            ) as restart_runtime,
            mock.patch.object(dev, "clear_runtime_profile_state") as clear_runtime_state,
            mock.patch("builtins.print") as print_mock,
        ):
            dev.handle_auth_down(config, include_dependencies=False)

        stop_frontend.assert_called_once_with(config)
        stop_backend.assert_called_once_with(config)
        restart_runtime.assert_called_once_with(config, profile=dev.SUPABASE_PROFILE_DATABASE)
        clear_runtime_state.assert_called_once_with(config)
        printed = "\n".join(str(call.args[0]) for call in print_mock.call_args_list if call.args)
        self.assertIn("Auth runtime stopped.", printed)
        self.assertIn("Database availability could not be refreshed", printed)

    def test_apply_environment_file_preserves_existing_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = pathlib.Path(temp_dir) / ".env.local"
            env_path.write_text("FIRST=from-file\nSECOND=from-file\n", encoding="utf-8")

            with mock.patch.dict(dev.os.environ, {"SECOND": "from-shell"}, clear=False):
                parsed = dev.apply_environment_file(env_path)
                self.assertEqual("from-file", dev.os.environ["FIRST"])
                self.assertEqual("from-shell", dev.os.environ["SECOND"])

            self.assertEqual({"FIRST": "from-file", "SECOND": "from-file"}, parsed)

    def test_require_environment_values_treats_placeholders_as_missing(self) -> None:
        with mock.patch.dict(
            dev.os.environ,
            {
                "PRESENT": "value",
                "PLACEHOLDER": "replace-me",
                "OPTIONAL_STYLE": "optional-for-staging",
            },
            clear=True,
        ):
            with self.assertRaises(dev.DevCliError) as raised:
                dev.require_environment_values("PRESENT", "PLACEHOLDER", "OPTIONAL_STYLE", context="Deploy test")

        self.assertIn("PLACEHOLDER", str(raised.exception))
        self.assertIn("OPTIONAL_STYLE", str(raised.exception))

    def test_is_github_environment_secret_matches_expected_split(self) -> None:
        self.assertTrue(dev.is_github_environment_secret("SUPABASE_SECRET_KEY"))
        self.assertTrue(dev.is_github_environment_secret("DEPLOY_SMOKE_SECRET"))
        self.assertFalse(dev.is_github_environment_secret("SUPABASE_PUBLISHABLE_KEY"))
        self.assertFalse(dev.is_github_environment_secret("BREVO_SIGNUPS_LIST_ID"))

    def test_deploy_required_env_names_keep_smoke_password_staging_only(self) -> None:
        self.assertNotIn("DEPLOY_SMOKE_USER_PASSWORD", dev.DEPLOY_REQUIRED_ENV_NAMES)
        self.assertIn("DEPLOY_SMOKE_USER_PASSWORD", dev.resolve_deploy_required_environment_names(target="staging"))
        self.assertNotIn("DEPLOY_SMOKE_USER_PASSWORD", dev.resolve_deploy_required_environment_names(target="production"))

    def test_build_deploy_fingerprint_omits_optional_missing_smoke_password_secret(self) -> None:
        config = dev.config_from_args(self.create_args(), pathlib.Path.cwd())
        env_values = {
            "BOARD_ENTHUSIASTS_SPA_BASE_URL": "https://boardenthusiasts.com",
            "BOARD_ENTHUSIASTS_WORKERS_BASE_URL": "https://api.boardenthusiasts.com",
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_PROJECT_REF": "project-ref",
            "SUPABASE_PUBLISHABLE_KEY": "publishable-key",
            "SUPABASE_AVATARS_BUCKET": "avatars",
            "SUPABASE_CARD_IMAGES_BUCKET": "cards",
            "SUPABASE_HERO_IMAGES_BUCKET": "heroes",
            "SUPABASE_LOGO_IMAGES_BUCKET": "logos",
            "BREVO_SIGNUPS_LIST_ID": "list-id",
            "ALLOWED_WEB_ORIGINS": "https://boardenthusiasts.com",
            "SUPPORT_REPORT_RECIPIENT": "support@boardenthusiasts.com",
            "SUPPORT_REPORT_SENDER_EMAIL": "noreply@boardenthusiasts.com",
            "SUPPORT_REPORT_SENDER_NAME": "Board Enthusiasts",
            "VITE_LANDING_MODE": "false",
            "SUPABASE_SECRET_KEY": "secret-key",
            "SUPABASE_DB_PASSWORD": "db-password",
            "SUPABASE_ACCESS_TOKEN": "supabase-access-token",
            "CLOUDFLARE_API_TOKEN": "cloudflare-token",
            "TURNSTILE_SECRET_KEY": "turnstile-secret-key",
            "BREVO_API_KEY": "brevo-api-key",
            "DEPLOY_SMOKE_SECRET": "deploy-smoke-secret",
        }

        with (
            mock.patch.object(
                dev,
                "get_git_repository_fingerprint",
                return_value={"revision": "abc123", "dirty": False, "status_hash": None},
            ),
            mock.patch.object(dev.json, "dumps", wraps=dev.json.dumps) as json_dumps,
        ):
            fingerprint = dev.build_deploy_fingerprint(
                config,
                target="production",
                source_branch="main",
                env_values=env_values,
            )

        payload = json_dumps.call_args.args[0]
        self.assertRegex(fingerprint, r"^[0-9a-f]{64}$")
        self.assertNotIn("DEPLOY_SMOKE_USER_PASSWORD", payload["secrets"])
        self.assertEqual(
            dev.hashlib.sha256(b"deploy-smoke-secret").hexdigest()[:16],
            payload["secrets"]["DEPLOY_SMOKE_SECRET"],
        )

    def test_collect_present_environment_values_ignores_placeholders_and_keeps_oauth_values(self) -> None:
        with mock.patch.dict(
            dev.os.environ,
            {
                "SUPABASE_AUTH_DISCORD_CLIENT_ID": "discord-client-id",
                "SUPABASE_AUTH_DISCORD_CLIENT_SECRET": "discord-client-secret",
                "SUPABASE_AUTH_GITHUB_CLIENT_ID": "github-client-id",
                "SUPABASE_AUTH_GITHUB_CLIENT_SECRET": "github-client-secret",
                "VITE_SUPABASE_AUTH_DISCORD_ENABLED": "true",
                "SUPABASE_AUTH_GOOGLE_CLIENT_ID": "replace-me",
            },
            clear=True,
        ):
            collected = dev.collect_present_environment_values(*dev.OPTIONAL_DEPLOY_ENV_NAMES)

        self.assertEqual("discord-client-id", collected["SUPABASE_AUTH_DISCORD_CLIENT_ID"])
        self.assertEqual("discord-client-secret", collected["SUPABASE_AUTH_DISCORD_CLIENT_SECRET"])
        self.assertEqual("github-client-id", collected["SUPABASE_AUTH_GITHUB_CLIENT_ID"])
        self.assertEqual("github-client-secret", collected["SUPABASE_AUTH_GITHUB_CLIENT_SECRET"])
        self.assertEqual("true", collected["VITE_SUPABASE_AUTH_DISCORD_ENABLED"])
        self.assertNotIn("SUPABASE_AUTH_GOOGLE_CLIENT_ID", collected)

    def test_run_bootstrap_super_admin_command_invokes_root_managed_script(self) -> None:
        config = dev.config_from_args(self.create_args(), pathlib.Path.cwd())

        with (
            mock.patch.object(dev, "ensure_migration_workspace_scaffolding"),
            mock.patch.object(dev, "install_migration_workspace_dependencies"),
            mock.patch.object(dev, "prompt_bootstrap_super_admin_password", return_value="StrongPassword!234"),
            mock.patch.object(
                dev,
                "require_environment_values",
                return_value={
                    "SUPABASE_URL": "https://example.supabase.co",
                    "SUPABASE_SECRET_KEY": "service-role-key",
                },
            ),
            mock.patch.object(dev, "run_command") as run_command,
        ):
            dev.run_bootstrap_super_admin_command(
                config,
                target="production",
                email="super-admin@example.com",
                user_name="bootstrap-admin",
                display_name="Bootstrap Admin",
                first_name="Bootstrap",
                last_name="Admin",
            )

        run_command.assert_called_once_with(
            [
                "npx",
                "tsx",
                "backend/scripts/bootstrap-super-admin.ts",
                "--supabase-url",
                "https://example.supabase.co",
                "--secret-key",
                "service-role-key",
                "--email",
                "super-admin@example.com",
                "--password-stdin",
                "--user-name",
                "bootstrap-admin",
                "--display-name",
                "Bootstrap Admin",
                "--first-name",
                "Bootstrap",
                "--last-name",
                "Admin",
            ],
            cwd=config.repo_root,
            env=mock.ANY,
            input_data="StrongPassword!234",
        )

    def test_resolve_bootstrap_super_admin_email_prompts_when_omitted(self) -> None:
        with (
            mock.patch.object(dev.sys.stdin, "isatty", return_value=True),
            mock.patch.object(dev, "input", side_effect=["", "operator@boardenthusiasts.com"]),
        ):
            email = dev.resolve_bootstrap_super_admin_email(email=None, target="production")

        self.assertEqual("operator@boardenthusiasts.com", email)

    def test_prompt_bootstrap_super_admin_password_retries_until_confirmation_matches(self) -> None:
        with (
            mock.patch.object(dev.sys.stdin, "isatty", return_value=True),
            mock.patch.object(
                dev.getpass,
                "getpass",
                side_effect=["", "StrongPassword!234", "WrongPassword!234", "StrongPassword!234", "StrongPassword!234"],
            ),
        ):
            password = dev.prompt_bootstrap_super_admin_password(
                target="production",
                email="operator@boardenthusiasts.com",
            )

        self.assertEqual("StrongPassword!234", password)

    def test_manual_deploy_workflow_exports_and_writes_smoke_credentials(self) -> None:
        workflow_path = pathlib.Path(__file__).resolve().parents[2] / ".github" / "workflows" / "manual-deploy.yml"
        workflow = workflow_path.read_text(encoding="utf-8")

        self.assertIn("SUPABASE_AUTH_DISCORD_CLIENT_ID: ${{ vars.SUPABASE_AUTH_DISCORD_CLIENT_ID }}", workflow)
        self.assertIn("SUPABASE_AUTH_DISCORD_CLIENT_SECRET: ${{ secrets.SUPABASE_AUTH_DISCORD_CLIENT_SECRET }}", workflow)
        self.assertIn('"SUPABASE_AUTH_DISCORD_CLIENT_ID",', workflow)
        self.assertIn('"SUPABASE_AUTH_DISCORD_CLIENT_SECRET",', workflow)
        self.assertIn("DEPLOY_SMOKE_PLAYER_EMAIL: ${{ vars.DEPLOY_SMOKE_PLAYER_EMAIL }}", workflow)
        self.assertIn("DEPLOY_SMOKE_DEVELOPER_EMAIL: ${{ vars.DEPLOY_SMOKE_DEVELOPER_EMAIL }}", workflow)
        self.assertIn("DEPLOY_SMOKE_MODERATOR_EMAIL: ${{ vars.DEPLOY_SMOKE_MODERATOR_EMAIL }}", workflow)
        self.assertIn("DEPLOY_SMOKE_SECRET: ${{ secrets.DEPLOY_SMOKE_SECRET }}", workflow)
        self.assertIn("DEPLOY_SMOKE_USER_PASSWORD: ${{ secrets.DEPLOY_SMOKE_USER_PASSWORD }}", workflow)
        self.assertIn('"DEPLOY_SMOKE_PLAYER_EMAIL",', workflow)
        self.assertIn('"DEPLOY_SMOKE_DEVELOPER_EMAIL",', workflow)
        self.assertIn('"DEPLOY_SMOKE_MODERATOR_EMAIL",', workflow)
        self.assertIn('"DEPLOY_SMOKE_SECRET",', workflow)
        self.assertIn('"DEPLOY_SMOKE_USER_PASSWORD",', workflow)

    def test_staging_environment_example_keeps_cors_origins_staging_only(self) -> None:
        env_example_path = pathlib.Path(__file__).resolve().parents[2] / "config" / ".env.staging.example"
        env_example = env_example_path.read_text(encoding="utf-8")

        self.assertIn(
            "ALLOWED_WEB_ORIGINS=http://localhost:5173,https://staging.boardenthusiasts.com",
            env_example,
        )

    def test_build_deploy_subprocess_environment_includes_supabase_oauth_credentials(self) -> None:
        environment = dev.build_deploy_subprocess_environment(
            {
                "SUPABASE_ACCESS_TOKEN": "supabase-access-token",
                "SUPABASE_AUTH_DISCORD_CLIENT_ID": "discord-client-id",
                "SUPABASE_AUTH_DISCORD_CLIENT_SECRET": "discord-client-secret",
                "SUPABASE_AUTH_GITHUB_CLIENT_ID": "github-client-id",
                "SUPABASE_AUTH_GITHUB_CLIENT_SECRET": "github-client-secret",
                "SUPABASE_AUTH_GOOGLE_CLIENT_ID": "google-client-id",
                "SUPABASE_AUTH_GOOGLE_CLIENT_SECRET": "google-client-secret",
                "CLOUDFLARE_API_TOKEN": "cloudflare-api-token",
                "CLOUDFLARE_ACCOUNT_ID": "cloudflare-account-id",
            }
        )

        self.assertEqual("discord-client-id", environment["SUPABASE_AUTH_DISCORD_CLIENT_ID"])
        self.assertEqual("discord-client-secret", environment["SUPABASE_AUTH_DISCORD_CLIENT_SECRET"])
        self.assertEqual("github-client-id", environment["SUPABASE_AUTH_GITHUB_CLIENT_ID"])
        self.assertEqual("github-client-secret", environment["SUPABASE_AUTH_GITHUB_CLIENT_SECRET"])
        self.assertEqual("google-client-id", environment["SUPABASE_AUTH_GOOGLE_CLIENT_ID"])
        self.assertEqual("google-client-secret", environment["SUPABASE_AUTH_GOOGLE_CLIENT_SECRET"])

    def test_build_deploy_frontend_environment_infers_staging_when_explicit_app_env_is_missing(self) -> None:
        environment = dev.build_deploy_frontend_environment(
            {
                "BOARD_ENTHUSIASTS_WORKERS_BASE_URL": "https://api.staging.boardenthusiasts.com",
                "SUPABASE_URL": "https://example-project.supabase.co",
                "SUPABASE_PUBLISHABLE_KEY": "publishable-key",
                "VITE_TURNSTILE_SITE_KEY": "turnstile-site-key",
                "VITE_LANDING_MODE": "true",
            }
        )

        self.assertEqual("staging", environment["VITE_APP_ENV"])
        self.assertEqual("https://api.staging.boardenthusiasts.com", environment["VITE_API_BASE_URL"])
        self.assertEqual("https://example-project.supabase.co", environment["VITE_SUPABASE_URL"])
        self.assertEqual("publishable-key", environment["VITE_SUPABASE_PUBLISHABLE_KEY"])
        self.assertEqual("turnstile-site-key", environment["VITE_TURNSTILE_SITE_KEY"])
        self.assertEqual("true", environment["VITE_LANDING_MODE"])

    def test_render_supabase_deploy_config_uses_target_auth_urls_and_provider_flags(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            config = dev.config_from_args(self.create_args(), repo_root)
            supabase_root = repo_root / config.supabase_root
            supabase_root.mkdir(parents=True, exist_ok=True)
            (supabase_root / "config.toml").write_text(
                "\n".join(
                    [
                        "[auth]",
                        'site_url = "http://127.0.0.1:4173"',
                        "additional_redirect_urls = [",
                        '  "http://127.0.0.1:4173",',
                        "]",
                        "",
                        "[auth.external.github]",
                        "enabled = true",
                        'client_id = "env(SUPABASE_AUTH_GITHUB_CLIENT_ID)"',
                        'secret = "env(SUPABASE_AUTH_GITHUB_CLIENT_SECRET)"',
                        "",
                        "[auth.external.discord]",
                        "enabled = true",
                        'client_id = "env(SUPABASE_AUTH_DISCORD_CLIENT_ID)"',
                        'secret = "env(SUPABASE_AUTH_DISCORD_CLIENT_SECRET)"',
                        "",
                        "[auth.external.google]",
                        "enabled = false",
                        'client_id = "env(SUPABASE_AUTH_GOOGLE_CLIENT_ID)"',
                        'secret = "env(SUPABASE_AUTH_GOOGLE_CLIENT_SECRET)"',
                    ]
                ),
                encoding="utf-8",
            )

            rendered = dev.render_supabase_deploy_config(
                config,
                env_values={
                    "BOARD_ENTHUSIASTS_SPA_BASE_URL": "https://staging.boardenthusiasts.com",
                    "ALLOWED_WEB_ORIGINS": "http://localhost:4173,https://staging.boardenthusiasts.com",
                    "SUPABASE_AUTH_DISCORD_CLIENT_ID": "discord-client-id",
                    "SUPABASE_AUTH_GITHUB_CLIENT_ID": "github-client-id",
                    "SUPABASE_AUTH_GOOGLE_CLIENT_ID": "",
                },
            )

        self.assertIn('site_url = "https://staging.boardenthusiasts.com"', rendered)
        self.assertIn('"https://staging.boardenthusiasts.com/auth/signin"', rendered)
        self.assertNotIn('"https://www.boardenthusiasts.com/auth/signin?mode=recovery"', rendered)
        self.assertIn("[auth.external.github]\nenabled = true", rendered)
        self.assertIn("[auth.external.discord]\nenabled = true", rendered)
        self.assertIn("[auth.external.google]\nenabled = false", rendered)

    def test_deploy_stage_list_includes_supabase_config_before_schema(self) -> None:
        self.assertIn("supabase_config", dev.DEPLOY_TRANSACTIONAL_STAGES)
        self.assertLess(
            dev.DEPLOY_TRANSACTIONAL_STAGES.index("supabase_config"),
            dev.DEPLOY_TRANSACTIONAL_STAGES.index("supabase_schema"),
        )

    def test_deploy_env_resolution_keeps_optional_oauth_values(self) -> None:
        with mock.patch.dict(
            dev.os.environ,
            {
                "BOARD_ENTHUSIASTS_SPA_BASE_URL": "https://staging.boardenthusiasts.com",
                "BOARD_ENTHUSIASTS_WORKERS_BASE_URL": "https://api.staging.boardenthusiasts.com",
                "SUPABASE_PROJECT_REF": "project-ref",
                "SUPABASE_URL": "https://project-ref.supabase.co",
                "SUPABASE_PUBLISHABLE_KEY": "publishable-key",
                "SUPABASE_SECRET_KEY": "secret-key",
                "SUPABASE_DB_PASSWORD": "db-password",
                "SUPABASE_ACCESS_TOKEN": "supabase-access-token",
                "SUPABASE_AVATARS_BUCKET": "avatars",
                "SUPABASE_CARD_IMAGES_BUCKET": "cards",
                "SUPABASE_HERO_IMAGES_BUCKET": "heroes",
                "SUPABASE_LOGO_IMAGES_BUCKET": "logos",
                "CLOUDFLARE_ACCOUNT_ID": "account-id",
                "CLOUDFLARE_API_TOKEN": "cloudflare-token",
                "VITE_TURNSTILE_SITE_KEY": "turnstile-site-key",
                "TURNSTILE_SECRET_KEY": "turnstile-secret-key",
                "BREVO_API_KEY": "brevo-api-key",
                "BREVO_SIGNUPS_LIST_ID": "list-id",
                "ALLOWED_WEB_ORIGINS": "https://staging.boardenthusiasts.com",
                "SUPPORT_REPORT_RECIPIENT": "support@boardenthusiasts.com",
                "SUPPORT_REPORT_SENDER_EMAIL": "noreply@boardenthusiasts.com",
                "SUPPORT_REPORT_SENDER_NAME": "Board Enthusiasts",
                "DEPLOY_SMOKE_SECRET": "deploy-smoke-secret",
                "DEPLOY_SMOKE_USER_PASSWORD": "deploy-smoke-password",
                "VITE_LANDING_MODE": "false",
                "SUPABASE_AUTH_DISCORD_CLIENT_ID": "discord-client-id",
                "SUPABASE_AUTH_DISCORD_CLIENT_SECRET": "discord-client-secret",
                "SUPABASE_AUTH_GITHUB_CLIENT_ID": "github-client-id",
                "SUPABASE_AUTH_GITHUB_CLIENT_SECRET": "github-client-secret",
            },
            clear=True,
        ):
            env_values = {
                **dev.collect_present_environment_values(*dev.OPTIONAL_DEPLOY_ENV_NAMES),
                **dev.require_environment_values(*dev.DEPLOY_REQUIRED_ENV_NAMES, context="Staging deployment"),
            }

        self.assertEqual("discord-client-id", env_values["SUPABASE_AUTH_DISCORD_CLIENT_ID"])
        self.assertEqual("discord-client-secret", env_values["SUPABASE_AUTH_DISCORD_CLIENT_SECRET"])
        self.assertEqual("github-client-id", env_values["SUPABASE_AUTH_GITHUB_CLIENT_ID"])
        self.assertEqual("github-client-secret", env_values["SUPABASE_AUTH_GITHUB_CLIENT_SECRET"])

    def test_infer_supabase_url_from_project_ref_for_hosted_env(self) -> None:
        with mock.patch.dict(
            dev.os.environ,
            {
                "BOARD_ENTHUSIASTS_APP_ENV": "staging",
                "SUPABASE_PROJECT_REF": "project-ref-123",
            },
            clear=True,
        ):
            self.assertEqual(
                "https://project-ref-123.supabase.co",
                dev.infer_supabase_url_from_environment(),
            )

    def test_infer_supabase_url_respects_explicit_override_for_custom_domains(self) -> None:
        with mock.patch.dict(
            dev.os.environ,
            {
                "BOARD_ENTHUSIASTS_APP_ENV": "production",
                "SUPABASE_PROJECT_REF": "project-ref-123",
                "SUPABASE_URL": "https://supabase.boardenthusiasts.com",
            },
            clear=True,
        ):
            self.assertEqual(
                "https://supabase.boardenthusiasts.com",
                dev.infer_supabase_url_from_environment(),
            )

    def test_get_supabase_project_ref_from_url_reads_default_hosted_project_ref(self) -> None:
        self.assertEqual(
            "project-ref-123",
            dev.get_supabase_project_ref_from_url("https://project-ref-123.supabase.co"),
        )

    def test_assert_supabase_project_alignment_rejects_mismatched_runtime_project(self) -> None:
        with self.assertRaises(dev.DevCliError) as raised:
            dev.assert_supabase_project_alignment(
                {
                    "SUPABASE_PROJECT_REF": "production-ref",
                    "SUPABASE_URL": "https://staging-ref.supabase.co",
                }
            )

        message = str(raised.exception)
        self.assertIn("SUPABASE_PROJECT_REF targets 'production-ref'", message)
        self.assertIn("SUPABASE_URL points at 'staging-ref'", message)

    def test_assert_supabase_project_alignment_logs_runtime_target_details(self) -> None:
        with mock.patch.object(dev, "write_step") as write_step:
            dev.assert_supabase_project_alignment(
                {
                    "SUPABASE_PROJECT_REF": "project-ref-123",
                    "SUPABASE_URL": "https://project-ref-123.supabase.co",
                }
            )

        write_step.assert_called_once_with(
            "Supabase runtime target: "
            "SUPABASE_PROJECT_REF=project-ref-123; "
            "SUPABASE_URL=https://project-ref-123.supabase.co; "
            "URL-derived project ref=project-ref-123"
        )

    def test_infer_supabase_url_does_not_override_local_environment(self) -> None:
        with mock.patch.dict(
            dev.os.environ,
            {
                "BOARD_ENTHUSIASTS_APP_ENV": "local",
                "SUPABASE_PROJECT_REF": "local-dev",
            },
            clear=True,
        ):
            self.assertIsNone(dev.infer_supabase_url_from_environment())

    def test_resolve_deploy_source_branch_prefers_explicit_argument(self) -> None:
        config = dev.config_from_args(self.create_args(), pathlib.Path.cwd())

        with mock.patch.dict(dev.os.environ, {"GITHUB_REF_NAME": "staging"}, clear=False):
            self.assertEqual(
                "release/1.2.3",
                dev.resolve_deploy_source_branch(config, explicit_source_branch="release/1.2.3"),
            )

    def test_resolve_deploy_source_branch_uses_github_ref_name_when_present(self) -> None:
        config = dev.config_from_args(self.create_args(), pathlib.Path.cwd())

        with mock.patch.dict(dev.os.environ, {"GITHUB_REF_NAME": "staging"}, clear=True):
            self.assertEqual("staging", dev.resolve_deploy_source_branch(config))

    def test_resolve_deploy_source_branch_falls_back_to_git_branch(self) -> None:
        config = dev.config_from_args(self.create_args(), pathlib.Path.cwd())

        git_branch_result = subprocess.CompletedProcess(
            args=["git", "branch", "--show-current"],
            returncode=0,
            stdout="release/v1.0.0\n",
            stderr="",
        )
        with mock.patch.dict(dev.os.environ, {}, clear=True):
            with mock.patch.object(dev, "run_command", return_value=git_branch_result) as run_command_mock:
                self.assertEqual("release/v1.0.0", dev.resolve_deploy_source_branch(config))

        run_command_mock.assert_called_once()

    def test_resolve_deploy_source_branch_requires_explicit_branch_when_detached(self) -> None:
        config = dev.config_from_args(self.create_args(), pathlib.Path.cwd())

        git_branch_result = subprocess.CompletedProcess(
            args=["git", "branch", "--show-current"],
            returncode=0,
            stdout="\n",
            stderr="",
        )
        with mock.patch.dict(dev.os.environ, {}, clear=True):
            with mock.patch.object(dev, "run_command", return_value=git_branch_result):
                with self.assertRaises(dev.DevCliError) as raised:
                    dev.resolve_deploy_source_branch(config)

        self.assertIn("--source-branch", str(raised.exception))

    def test_auto_load_command_environment_normalizes_inferred_supabase_url(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)
            staging_env_path = repo_root / config.staging_env_file
            staging_env_path.parent.mkdir(parents=True, exist_ok=True)
            staging_env_path.write_text(
                "BOARD_ENTHUSIASTS_APP_ENV=staging\nSUPABASE_PROJECT_REF=project-ref-123\n",
                encoding="utf-8",
            )

            with mock.patch.dict(dev.os.environ, {}, clear=True):
                loaded_path = dev.auto_load_command_environment(
                    config,
                    command_name="deploy",
                    deploy_target="staging",
                )
                self.assertEqual("https://project-ref-123.supabase.co", dev.os.environ["SUPABASE_URL"])

            self.assertEqual(staging_env_path, loaded_path)

    def test_normalize_deploy_stage_state_requires_upgrade_for_new_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            config = dev.config_from_args(self.create_args(), repo_root)
            dev.save_deploy_state(
                config,
                target="staging",
                state={
                    "target": "staging",
                    "fingerprint": "old-fingerprint",
                    "completed_stages": ["supabase_schema"],
                },
            )

            with self.assertRaises(dev.DevCliError) as raised:
                dev.normalize_deploy_stage_state(
                    config,
                    target="staging",
                    fingerprint="new-fingerprint",
                    force=False,
                    upgrade=False,
                )

        self.assertIn("--upgrade", str(raised.exception))

    def test_normalize_deploy_stage_state_resets_completed_stages_for_upgrade(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            config = dev.config_from_args(self.create_args(), repo_root)
            dev.save_deploy_state(
                config,
                target="staging",
                state={
                    "target": "staging",
                    "fingerprint": "old-fingerprint",
                    "completed_stages": ["supabase_schema", "pages_project"],
                },
            )

            completed_stages, state = dev.normalize_deploy_stage_state(
                config,
                target="staging",
                fingerprint="new-fingerprint",
                force=False,
                upgrade=True,
            )

        self.assertEqual(set(), completed_stages)
        self.assertEqual("new-fingerprint", state["fingerprint"])

    def test_build_migration_frontend_environment_can_force_landing_mode(self) -> None:
        args = self.create_args()
        config = dev.config_from_args(args, pathlib.Path.cwd())

        with mock.patch.dict(dev.os.environ, {"VITE_TURNSTILE_SITE_KEY": "site-key"}, clear=False):
            environment = dev.build_migration_frontend_environment(
                config,
                runtime_env={
                    "SUPABASE_URL": "http://127.0.0.1:54321",
                    "SUPABASE_PUBLISHABLE_KEY": "publishable-key",
                },
                landing_mode=True,
            )

        self.assertEqual("http://127.0.0.1:8787", environment["VITE_API_BASE_URL"])
        self.assertEqual("http://127.0.0.1:54321", environment["VITE_SUPABASE_URL"])
        self.assertEqual("publishable-key", environment["VITE_SUPABASE_PUBLISHABLE_KEY"])
        self.assertEqual("site-key", environment["VITE_TURNSTILE_SITE_KEY"])
        self.assertEqual("true", environment["VITE_LANDING_MODE"])

    def test_get_deploy_worker_config_path_rewrites_main_relative_to_generated_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)
            template_path = repo_root / config.cloudflare_workers_template
            template_path.parent.mkdir(parents=True, exist_ok=True)
            template_path.write_text(
                "\n".join(
                    [
                        '{',
                        '  "name": "board-enthusiasts-api-staging",',
                        '  "main": "../../apps/workers-api/src/worker.ts",',
                        '  "workers_dev": true,',
                        '  "preview_urls": false,',
                        '  "routes": [],',
                        '  "vars": {',
                        '    "APP_ENV": "staging",',
                        '    "SUPABASE_URL": "env(SUPABASE_URL)"',
                        "  }",
                        "}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            rendered_path = dev.get_deploy_worker_config_path(
                config,
                target="staging",
                env_values={
                    "BOARD_ENTHUSIASTS_WORKERS_BASE_URL": "https://api.staging.boardenthusiasts.com",
                    "SUPABASE_URL": "https://example.supabase.co",
                },
            )
            rendered = rendered_path.read_text(encoding="utf-8")

        self.assertIn('"main": "../backend/apps/workers-api/src/worker.ts"', rendered)
        self.assertIn('"routes": [{"pattern": "api.staging.boardenthusiasts.com", "custom_domain": true}]', rendered)
        self.assertIn('"SUPABASE_URL": "https://example.supabase.co"', rendered)

    def test_get_deploy_worker_config_path_keeps_empty_routes_for_workers_dev_urls(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)
            template_path = repo_root / config.cloudflare_workers_template
            template_path.parent.mkdir(parents=True, exist_ok=True)
            template_path.write_text(
                "\n".join(
                    [
                        '{',
                        '  "name": "board-enthusiasts-api-staging",',
                        '  "main": "../../apps/workers-api/src/worker.ts",',
                        '  "workers_dev": true,',
                        '  "preview_urls": false,',
                        '  "routes": [],',
                        '  "vars": {',
                        '    "APP_ENV": "staging",',
                        '    "SUPABASE_URL": "env(SUPABASE_URL)"',
                        "  }",
                        "}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            rendered_path = dev.get_deploy_worker_config_path(
                config,
                target="staging",
                env_values={
                    "BOARD_ENTHUSIASTS_WORKERS_BASE_URL": "https://board-enthusiasts-api-staging.example.workers.dev",
                    "SUPABASE_URL": "https://example.supabase.co",
                },
            )
            rendered = rendered_path.read_text(encoding="utf-8")

        self.assertIn('"routes": []', rendered)

    def test_get_deploy_worker_config_path_requires_values_for_env_placeholders(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)
            template_path = repo_root / config.cloudflare_workers_template
            template_path.parent.mkdir(parents=True, exist_ok=True)
            template_path.write_text(
                "\n".join(
                    [
                        "{",
                        '  "vars": {',
                        '    "SUPABASE_URL": "env(SUPABASE_URL)"',
                        "  }",
                        "}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaises(dev.DevCliError) as raised:
                dev.get_deploy_worker_config_path(
                    config,
                    target="staging",
                    env_values={"BOARD_ENTHUSIASTS_WORKERS_BASE_URL": "https://api.staging.boardenthusiasts.com"},
                )

        self.assertIn("SUPABASE_URL", str(raised.exception))

    def test_build_worker_custom_domain_routes_supports_production_hostnames(self) -> None:
        routes = dev.build_worker_custom_domain_routes(worker_base_url="https://api.boardenthusiasts.com")

        self.assertEqual(routes, [{"pattern": "api.boardenthusiasts.com", "custom_domain": True}])

    def test_build_cloudflare_pages_branch_alias_hostname_normalizes_release_branch(self) -> None:
        alias = dev.build_cloudflare_pages_branch_alias_hostname(
            project_name="board-enthusiasts-staging",
            source_branch="staging/1.0.0-landing-page.0",
        )

        self.assertEqual(alias, "staging-1-0-0-landing-page-0.board-enthusiasts-staging.pages.dev")

    def test_parse_cloudflare_pages_alias_hostname_uses_wranger_reported_alias(self) -> None:
        output = (
            "✨ Deployment complete! Take a peek over at https://0b1901b2.board-enthusiasts.pages.dev\n"
            "✨ Deployment alias URL: https://production-1-0-0-landing-pag.board-enthusiasts.pages.dev\n"
        )

        alias = dev.parse_cloudflare_pages_alias_hostname(output)

        self.assertEqual(alias, "production-1-0-0-landing-pag.board-enthusiasts.pages.dev")

    def test_get_expected_cloudflare_pages_alias_hostname_uses_project_hostname_for_main(self) -> None:
        alias = dev.get_expected_cloudflare_pages_alias_hostname(
            project_name="board-enthusiasts-fallback",
            source_branch="main",
        )

        self.assertEqual(alias, "board-enthusiasts-fallback.pages.dev")

    def test_get_expected_cloudflare_pages_alias_hostname_uses_branch_alias_for_non_main(self) -> None:
        alias = dev.get_expected_cloudflare_pages_alias_hostname(
            project_name="board-enthusiasts-fallback",
            source_branch="feature/fallback-pages",
        )

        self.assertEqual(alias, "feature-fallback-pages.board-enthusiasts-fallback.pages.dev")

    def test_ensure_cloudflare_pages_custom_domain_attaches_missing_hostname(self) -> None:
        env_values = {
            "BOARD_ENTHUSIASTS_SPA_BASE_URL": "https://staging.boardenthusiasts.com",
            "CLOUDFLARE_ACCOUNT_ID": "account-id",
            "CLOUDFLARE_API_TOKEN": "token",
        }

        with mock.patch.object(dev, "get_cloudflare_pages_project_domains", return_value=[]), mock.patch.object(
            dev,
            "request_json",
            return_value={"success": True},
        ) as request_json:
            dev.ensure_cloudflare_pages_custom_domain(env_values, target="staging")

        request_json.assert_called_once_with(
            url="https://api.cloudflare.com/client/v4/accounts/account-id/pages/projects/board-enthusiasts-staging/domains",
            method="POST",
            headers={
                "Authorization": "Bearer token",
                "Content-Type": "application/json",
            },
            payload={"name": "staging.boardenthusiasts.com"},
        )

    def test_ensure_cloudflare_pages_project_skips_creation_when_project_exists(self) -> None:
        config = dev.config_from_args(self.create_args(), pathlib.Path.cwd())
        env_values = {
            "CLOUDFLARE_ACCOUNT_ID": "account-id",
            "CLOUDFLARE_API_TOKEN": "token",
        }

        with mock.patch.object(
            dev,
            "get_cloudflare_pages_project",
            return_value={"name": "board-enthusiasts-staging"},
        ) as get_project, mock.patch.object(dev, "request_json") as request_json:
            dev.ensure_cloudflare_pages_project(config, target="staging", env=env_values)

        get_project.assert_called_once_with(env_values, project_name="board-enthusiasts-staging")
        request_json.assert_not_called()

    def test_ensure_named_cloudflare_pages_project_creates_missing_project(self) -> None:
        env_values = {
            "CLOUDFLARE_ACCOUNT_ID": "account-id",
            "CLOUDFLARE_API_TOKEN": "token",
        }

        with mock.patch.object(
            dev,
            "get_cloudflare_pages_project",
            return_value=None,
        ), mock.patch.object(
            dev,
            "request_json",
            return_value={"success": True},
        ) as request_json:
            dev.ensure_named_cloudflare_pages_project(
                env_values,
                project_name="board-enthusiasts-fallback",
                production_branch="main",
            )

        request_json.assert_called_once_with(
            url="https://api.cloudflare.com/client/v4/accounts/account-id/pages/projects",
            method="POST",
            headers={
                "Authorization": "Bearer token",
                "Content-Type": "application/json",
            },
            payload={
                "name": "board-enthusiasts-fallback",
                "production_branch": "main",
            },
        )

    def test_ensure_cloudflare_pages_project_treats_already_exists_as_success(self) -> None:
        config = dev.config_from_args(self.create_args(), pathlib.Path.cwd())
        env_values = {
            "CLOUDFLARE_ACCOUNT_ID": "account-id",
            "CLOUDFLARE_API_TOKEN": "token",
        }

        with mock.patch.object(
            dev,
            "get_cloudflare_pages_project",
            return_value=None,
        ), mock.patch.object(
            dev,
            "request_json",
            side_effect=dev.DevCliError(
                "HTTP 409 Conflict for https://api.cloudflare.com/client/v4/accounts/account-id/pages/projects: "
                "{\"success\":false,\"errors\":[{\"code\":8000002,\"message\":\"A project with this name already exists. Choose a different project name.\"}]}"
            ),
        ):
            dev.ensure_cloudflare_pages_project(config, target="staging", env=env_values)

    def test_deploy_fallback_pages_prints_maintained_urls(self) -> None:
        config = dev.config_from_args(self.create_args(), pathlib.Path.cwd())
        env_values = {
            "CLOUDFLARE_ACCOUNT_ID": "account-id",
            "CLOUDFLARE_API_TOKEN": "token",
        }

        with mock.patch.object(
            dev,
            "require_environment_values",
            return_value=env_values,
        ), mock.patch.object(
            dev,
            "get_cloudflare_pages_projects",
        ) as get_cloudflare_pages_projects, mock.patch.object(
            dev,
            "ensure_named_cloudflare_pages_project",
        ) as ensure_named_cloudflare_pages_project, mock.patch.object(
            dev,
            "run_named_pages_deploy",
            return_value="preview.board-enthusiasts-fallback.pages.dev",
        ) as run_named_pages_deploy, mock.patch.object(
            dev,
            "write_step",
        ), mock.patch("builtins.print") as print_mock:
            alias = dev.deploy_fallback_pages(
                config,
                project_name="board-enthusiasts-fallback",
                source_branch="feature/fallback-pages",
            )

        self.assertEqual("preview.board-enthusiasts-fallback.pages.dev", alias)
        get_cloudflare_pages_projects.assert_called_once_with(env_values)
        ensure_named_cloudflare_pages_project.assert_called_once_with(
            env_values,
            project_name="board-enthusiasts-fallback",
        )
        run_named_pages_deploy.assert_called_once()
        printed_lines = [" ".join(str(arg) for arg in call.args) for call in print_mock.call_args_list]
        self.assertIn("- Base page: https://preview.board-enthusiasts-fallback.pages.dev/", printed_lines)
        self.assertIn(
            "- Cloudflare 5xx page: https://preview.board-enthusiasts-fallback.pages.dev/cloudflare/5xx.html",
            printed_lines,
        )

    def test_sync_cloudflare_pages_domain_dns_updates_existing_record_target(self) -> None:
        env_values = {
            "BOARD_ENTHUSIASTS_SPA_BASE_URL": "https://staging.boardenthusiasts.com",
            "CLOUDFLARE_ACCOUNT_ID": "account-id",
            "CLOUDFLARE_API_TOKEN": "token",
        }

        with mock.patch.object(
            dev,
            "get_cloudflare_zone_for_hostname",
            return_value={"id": "zone-id", "name": "staging.boardenthusiasts.com"},
        ), mock.patch.object(
            dev,
            "get_cloudflare_dns_records",
            return_value=[
                {
                    "id": "dns-id",
                    "type": "CNAME",
                    "name": "staging.boardenthusiasts.com",
                    "content": "staging.boardenthusiasts.pages.dev",
                    "proxied": True,
                }
            ],
        ), mock.patch.object(dev, "request_json", return_value={"success": True}) as request_json:
            dev.sync_cloudflare_pages_domain_dns(
                env_values,
                target="staging",
                alias_target="staging-1-0-0-landing-pag.board-enthusiasts-staging.pages.dev",
            )

        request_json.assert_called_once_with(
            url="https://api.cloudflare.com/client/v4/zones/zone-id/dns_records/dns-id",
            method="PUT",
            headers={
                "Authorization": "Bearer token",
                "Content-Type": "application/json",
            },
            payload={
                "type": "CNAME",
                "name": "staging.boardenthusiasts.com",
                "content": "staging-1-0-0-landing-pag.board-enthusiasts-staging.pages.dev",
                "proxied": True,
                "ttl": 1,
            },
        )

    def test_assert_pages_custom_domain_prerequisites_rejects_non_cname_records(self) -> None:
        env_values = {
            "BOARD_ENTHUSIASTS_SPA_BASE_URL": "https://boardenthusiasts.com",
            "CLOUDFLARE_ACCOUNT_ID": "account-id",
            "CLOUDFLARE_API_TOKEN": "token",
        }

        with mock.patch.object(
            dev,
            "get_cloudflare_zone_for_hostname",
            return_value={"id": "zone-id", "name": "boardenthusiasts.com"},
        ), mock.patch.object(
            dev,
            "get_cloudflare_dns_records",
            return_value=[{"id": "dns-id", "type": "A", "name": "boardenthusiasts.com"}],
        ):
            with self.assertRaises(dev.DevCliError) as raised:
                dev.assert_pages_custom_domain_prerequisites(env_values)

        self.assertIn("proxied CNAME target", str(raised.exception))

    def test_assert_pages_custom_domain_prerequisites_allows_manageable_apex_routing_records(self) -> None:
        env_values = {
            "BOARD_ENTHUSIASTS_SPA_BASE_URL": "https://boardenthusiasts.com",
            "CLOUDFLARE_ACCOUNT_ID": "account-id",
            "CLOUDFLARE_API_TOKEN": "token",
        }

        with mock.patch.object(
            dev,
            "get_cloudflare_zone_for_hostname",
            return_value={"id": "zone-id", "name": "boardenthusiasts.com"},
        ), mock.patch.object(
            dev,
            "get_cloudflare_dns_records",
            return_value=[
                {"id": "a1", "type": "A", "name": "boardenthusiasts.com", "proxied": True},
                {"id": "a2", "type": "A", "name": "boardenthusiasts.com", "proxied": True},
                {"id": "mx1", "type": "MX", "name": "boardenthusiasts.com"},
                {"id": "txt1", "type": "TXT", "name": "boardenthusiasts.com"},
            ],
        ):
            dev.assert_pages_custom_domain_prerequisites(env_values)

    def test_sync_cloudflare_pages_domain_dns_replaces_manageable_apex_routing_records(self) -> None:
        env_values = {
            "BOARD_ENTHUSIASTS_SPA_BASE_URL": "https://boardenthusiasts.com",
            "CLOUDFLARE_ACCOUNT_ID": "account-id",
            "CLOUDFLARE_API_TOKEN": "token",
        }

        with mock.patch.object(
            dev,
            "get_cloudflare_zone_for_hostname",
            return_value={"id": "zone-id", "name": "boardenthusiasts.com"},
        ), mock.patch.object(
            dev,
            "get_cloudflare_dns_records",
            return_value=[
                {"id": "a1", "type": "A", "name": "boardenthusiasts.com", "proxied": True, "content": "15.197.148.33"},
                {"id": "a2", "type": "A", "name": "boardenthusiasts.com", "proxied": True, "content": "3.33.130.190"},
                {"id": "mx1", "type": "MX", "name": "boardenthusiasts.com"},
            ],
        ), mock.patch.object(dev, "request_json") as request_json:
            dev.sync_cloudflare_pages_domain_dns(
                env_values,
                target="production",
                alias_target="production-1-0-0-landing-pag.board-enthusiasts.pages.dev",
            )

        self.assertEqual(3, request_json.call_count)
        request_json.assert_any_call(
            url="https://api.cloudflare.com/client/v4/zones/zone-id/dns_records/a1",
            method="DELETE",
            headers={
                "Authorization": "Bearer token",
                "Content-Type": "application/json",
            },
        )
        request_json.assert_any_call(
            url="https://api.cloudflare.com/client/v4/zones/zone-id/dns_records/a2",
            method="DELETE",
            headers={
                "Authorization": "Bearer token",
                "Content-Type": "application/json",
            },
        )
        request_json.assert_any_call(
            url="https://api.cloudflare.com/client/v4/zones/zone-id/dns_records",
            method="POST",
            headers={
                "Authorization": "Bearer token",
                "Content-Type": "application/json",
            },
            payload={
                "type": "CNAME",
                "name": "boardenthusiasts.com",
                "content": "production-1-0-0-landing-pag.board-enthusiasts.pages.dev",
                "proxied": True,
                "ttl": 1,
            },
        )

    def test_assert_worker_custom_domain_dns_prerequisites_skips_existing_live_custom_domain(self) -> None:
        env_values = {
            "BOARD_ENTHUSIASTS_WORKERS_BASE_URL": "https://api.staging.boardenthusiasts.com",
            "CLOUDFLARE_API_TOKEN": "token",
            "CLOUDFLARE_ACCOUNT_ID": "account-id",
        }

        with mock.patch.object(dev, "probe_http_endpoint", return_value=(True, None)) as probe_http_endpoint, mock.patch.object(
            dev, "request_json"
        ) as request_json:
            dev.assert_worker_custom_domain_dns_prerequisites(env_values)

        probe_http_endpoint.assert_called_once()
        request_json.assert_not_called()

    def test_assert_worker_custom_domain_dns_prerequisites_reports_conflicting_dns_records(self) -> None:
        env_values = {
            "BOARD_ENTHUSIASTS_WORKERS_BASE_URL": "https://api.staging.boardenthusiasts.com",
            "CLOUDFLARE_API_TOKEN": "token",
            "CLOUDFLARE_ACCOUNT_ID": "account-id",
        }

        def request_json_side_effect(*, url: str, headers: dict[str, str] | None = None, **_: object) -> object:
            self.assertIsNotNone(headers)
            if "client/v4/zones?" in url:
                zone_name = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("name", [""])[0]
                if zone_name == "boardenthusiasts.com":
                    return {
                        "result": [
                            {
                                "id": "zone-id",
                                "name": "boardenthusiasts.com",
                                "account": {"id": "account-id"},
                            }
                        ]
                    }
                return {"result": []}
            if "client/v4/zones/zone-id/dns_records" in url:
                return {"result": [{"id": "dns-id", "type": "CNAME", "name": "api.staging.boardenthusiasts.com"}]}
            self.fail(f"Unexpected Cloudflare API URL: {url}")

        with mock.patch.object(dev, "probe_http_endpoint", return_value=(False, "tls handshake failed")), mock.patch.object(
            dev,
            "request_json",
            side_effect=request_json_side_effect,
        ):
            with self.assertRaises(dev.DevCliError) as raised:
                dev.assert_worker_custom_domain_dns_prerequisites(env_values)

        self.assertIn("Delete the existing DNS record", str(raised.exception))

    def test_assert_worker_custom_domain_dns_prerequisites_allows_cloudflare_managed_worker_records(self) -> None:
        env_values = {
            "BOARD_ENTHUSIASTS_WORKERS_BASE_URL": "https://api.staging.boardenthusiasts.com",
            "CLOUDFLARE_API_TOKEN": "token",
            "CLOUDFLARE_ACCOUNT_ID": "account-id",
        }

        def request_json_side_effect(*, url: str, headers: dict[str, str] | None = None, **_: object) -> object:
            self.assertIsNotNone(headers)
            if "client/v4/zones?" in url:
                zone_name = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("name", [""])[0]
                if zone_name == "boardenthusiasts.com":
                    return {
                        "result": [
                            {
                                "id": "zone-id",
                                "name": "boardenthusiasts.com",
                                "account": {"id": "account-id"},
                            }
                        ]
                    }
                return {"result": []}
            if "client/v4/zones/zone-id/dns_records" in url:
                return {
                    "result": [
                        {
                            "id": "dns-id",
                            "type": "AAAA",
                            "name": "api.staging.boardenthusiasts.com",
                            "meta": {"origin_worker_id": "worker-id", "read_only": True},
                        }
                    ]
                }
            self.fail(f"Unexpected Cloudflare API URL: {url}")

        with mock.patch.object(dev, "probe_http_endpoint", return_value=(False, "tls handshake failed")), mock.patch.object(
            dev,
            "request_json",
            side_effect=request_json_side_effect,
        ):
            dev.assert_worker_custom_domain_dns_prerequisites(env_values)

    def test_run_deploy_preflight_does_not_require_custom_domains_to_resolve_before_deploy(self) -> None:
        args = self.create_args()
        config = dev.config_from_args(args, pathlib.Path.cwd())
        env_values = {
            "BOARD_ENTHUSIASTS_SPA_BASE_URL": "https://boardenthusiasts.com",
            "BOARD_ENTHUSIASTS_WORKERS_BASE_URL": "https://api.boardenthusiasts.com",
        }
        subprocess_env = {"CLOUDFLARE_API_TOKEN": "token"}

        with mock.patch.object(dev, "assert_github_environment_sync") as assert_github_environment_sync, mock.patch.object(
            dev, "get_cloudflare_pages_projects"
        ) as get_cloudflare_pages_projects, mock.patch.object(
            dev, "assert_pages_custom_domain_prerequisites"
        ) as assert_pages_custom_domain_prerequisites, mock.patch.object(
            dev, "assert_worker_custom_domain_dns_prerequisites"
        ) as assert_worker_custom_domain_dns_prerequisites, mock.patch.object(
            dev, "assert_supabase_publishable_access"
        ) as assert_supabase_publishable_access, mock.patch.object(
            dev, "assert_supabase_secret_access"
        ) as assert_supabase_secret_access, mock.patch.object(
            dev, "assert_supabase_project_alignment"
        ) as assert_supabase_project_alignment, mock.patch.object(
            dev, "assert_turnstile_secret_access"
        ) as assert_turnstile_secret_access, mock.patch.object(
            dev, "assert_brevo_configuration"
        ) as assert_brevo_configuration, mock.patch.object(dev, "run_supabase_link") as run_supabase_link:
            dev.run_deploy_preflight(
                config,
                target="production",
                env_values=env_values,
                subprocess_env=subprocess_env,
            )

        assert_github_environment_sync.assert_called_once_with(config, target="production")
        get_cloudflare_pages_projects.assert_called_once_with(env_values)
        assert_pages_custom_domain_prerequisites.assert_called_once_with(env_values)
        assert_worker_custom_domain_dns_prerequisites.assert_called_once_with(env_values)
        assert_supabase_publishable_access.assert_called_once_with(env_values)
        assert_supabase_secret_access.assert_called_once_with(env_values)
        assert_supabase_project_alignment.assert_called_once_with(env_values)
        assert_turnstile_secret_access.assert_called_once_with(env_values)
        assert_brevo_configuration.assert_called_once_with(env_values)
        run_supabase_link.assert_called_once_with(config, env_values=env_values, subprocess_env=subprocess_env)

    def test_assert_hosted_required_schema_checks_runtime_tables(self) -> None:
        env_values = {
            "SUPABASE_URL": "https://project-ref.supabase.co",
            "SUPABASE_SECRET_KEY": "secret-key",
        }
        requested_urls: list[str] = []

        class _Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        def fake_urlopen(request, timeout=15):
            requested_urls.append(request.full_url)
            return _Response()

        with mock.patch.object(dev.urllib.request, "urlopen", side_effect=fake_urlopen):
            dev.assert_hosted_required_schema(env_values)

        self.assertEqual(
            [
                "https://project-ref.supabase.co/rest/v1/titles?select=*&limit=1",
                "https://project-ref.supabase.co/rest/v1/studios?select=*&limit=1",
                "https://project-ref.supabase.co/rest/v1/home_spotlight_entries?select=*&limit=1",
                "https://project-ref.supabase.co/rest/v1/home_offering_spotlight_entries?select=*&limit=1",
                "https://project-ref.supabase.co/rest/v1/analytics_event_types?select=*&limit=1",
                "https://project-ref.supabase.co/rest/v1/analytics_events?select=*&limit=1",
                "https://project-ref.supabase.co/rest/v1/developer_analytics_saved_views?select=*&limit=1",
                "https://project-ref.supabase.co/rest/v1/player_followed_studios?select=*&limit=1",
                "https://project-ref.supabase.co/rest/v1/be_home_presence_sessions?select=*&limit=1",
                "https://project-ref.supabase.co/rest/v1/be_home_device_identities?select=*&limit=1",
                "https://project-ref.supabase.co/rest/v1/title_detail_views?select=*&limit=1",
                "https://project-ref.supabase.co/rest/v1/title_get_clicks?select=*&limit=1",
            ],
            requested_urls,
        )

    def test_deploy_migration_target_verifies_hosted_schema_after_supabase_push(self) -> None:
        args = self.create_args()
        config = dev.config_from_args(args, pathlib.Path.cwd())
        env_values = {
            "BOARD_ENTHUSIASTS_SPA_BASE_URL": "https://boardenthusiasts.com",
            "BOARD_ENTHUSIASTS_WORKERS_BASE_URL": "https://api.boardenthusiasts.com",
            "SUPABASE_PROJECT_REF": "project-ref",
            "SUPABASE_URL": "https://project-ref.supabase.co",
            "SUPABASE_PUBLISHABLE_KEY": "publishable-key",
            "SUPABASE_SECRET_KEY": "secret-key",
            "SUPABASE_DB_PASSWORD": "db-password",
            "SUPABASE_ACCESS_TOKEN": "supabase-access-token",
            "SUPABASE_AVATARS_BUCKET": "avatars",
            "SUPABASE_CARD_IMAGES_BUCKET": "cards",
            "SUPABASE_HERO_IMAGES_BUCKET": "heroes",
            "SUPABASE_LOGO_IMAGES_BUCKET": "logos",
            "CLOUDFLARE_ACCOUNT_ID": "account-id",
            "CLOUDFLARE_API_TOKEN": "cloudflare-token",
            "VITE_TURNSTILE_SITE_KEY": "turnstile-site-key",
            "TURNSTILE_SECRET_KEY": "turnstile-secret-key",
            "BREVO_API_KEY": "brevo-api-key",
            "BREVO_SIGNUPS_LIST_ID": "list-id",
            "ALLOWED_WEB_ORIGINS": "https://boardenthusiasts.com",
            "SUPPORT_REPORT_RECIPIENT": "support@boardenthusiasts.com",
            "SUPPORT_REPORT_SENDER_EMAIL": "noreply@boardenthusiasts.com",
            "SUPPORT_REPORT_SENDER_NAME": "Board Enthusiasts",
            "DEPLOY_SMOKE_SECRET": "deploy-smoke-secret",
            "DEPLOY_SMOKE_PLAYER_EMAIL": "player@example.com",
            "DEPLOY_SMOKE_DEVELOPER_EMAIL": "developer@example.com",
            "DEPLOY_SMOKE_MODERATOR_EMAIL": "moderator@example.com",
            "DEPLOY_SMOKE_USER_PASSWORD": "deploy-smoke-password",
            "VITE_LANDING_MODE": "false",
        }

        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(dev, "assert_command_available"))
            stack.enter_context(mock.patch.object(dev, "ensure_migration_workspace_scaffolding"))
            stack.enter_context(mock.patch.object(dev, "install_migration_workspace_dependencies"))
            stack.enter_context(mock.patch.object(dev, "collect_present_environment_values", return_value={}))
            stack.enter_context(mock.patch.object(dev, "require_environment_values", return_value=env_values))
            stack.enter_context(mock.patch.object(dev, "build_deploy_subprocess_environment", return_value={"env": "value"}))
            stack.enter_context(mock.patch.object(dev, "resolve_deploy_source_branch", return_value="main"))
            stack.enter_context(mock.patch.object(dev, "run_deploy_preflight"))
            stack.enter_context(mock.patch.object(dev, "run_deploy_dry_run"))
            stack.enter_context(mock.patch.object(dev, "build_deploy_fingerprint", return_value="fingerprint"))
            stack.enter_context(mock.patch.object(dev, "normalize_deploy_stage_state", return_value=(set(), {})))
            stack.enter_context(
                mock.patch.object(dev, "get_deploy_worker_config_path", return_value=pathlib.Path("wrangler.generated.jsonc"))
            )
            stack.enter_context(mock.patch.object(dev, "run_supabase_remote_config_push"))
            stack.enter_context(mock.patch.object(dev, "run_supabase_link"))
            run_supabase_remote_push = stack.enter_context(mock.patch.object(dev, "run_supabase_remote_push"))
            assert_hosted_required_schema = stack.enter_context(mock.patch.object(dev, "assert_hosted_required_schema"))
            stack.enter_context(mock.patch.object(dev, "run_supabase_bucket_provisioning"))
            stack.enter_context(mock.patch.object(dev, "run_supabase_hosted_demo_seeding"))
            stack.enter_context(mock.patch.object(dev, "ensure_cloudflare_pages_project"))
            stack.enter_context(mock.patch.object(dev, "sync_worker_secret"))
            stack.enter_context(mock.patch.object(dev, "run_workers_deploy"))
            stack.enter_context(mock.patch.object(dev, "run_pages_deploy", return_value="pages-alias.example"))
            stack.enter_context(mock.patch.object(dev, "finalize_pages_custom_domain"))
            stack.enter_context(mock.patch.object(dev, "update_deploy_stage_completion"))
            stack.enter_context(mock.patch.object(dev, "run_workers_deploy_smoke"))
            stack.enter_context(mock.patch.object(dev, "run_pages_deploy_smoke"))
            dev.deploy_migration_target(
                config,
                target="production",
                source_branch=None,
                force=False,
                upgrade=False,
                preflight_only=False,
                dry_run_only=False,
            )

        run_supabase_remote_push.assert_called_once()
        assert_hosted_required_schema.assert_called_once_with(env_values)

    def test_hosted_deploy_deploys_workers_before_syncing_worker_secrets(self) -> None:
        config = dev.config_from_args(self.create_args(), pathlib.Path.cwd())
        env_values = {
            "BOARD_ENTHUSIASTS_SPA_BASE_URL": "https://boardenthusiasts.com",
            "BOARD_ENTHUSIASTS_WORKERS_BASE_URL": "https://api.boardenthusiasts.com",
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_PROJECT_REF": "project-ref",
            "SUPABASE_PUBLISHABLE_KEY": "publishable-key",
            "SUPABASE_SECRET_KEY": "secret-key",
            "SUPABASE_DB_PASSWORD": "db-password",
            "SUPABASE_ACCESS_TOKEN": "supabase-access-token",
            "SUPABASE_AVATARS_BUCKET": "avatars",
            "SUPABASE_CARD_IMAGES_BUCKET": "cards",
            "SUPABASE_HERO_IMAGES_BUCKET": "heroes",
            "SUPABASE_LOGO_IMAGES_BUCKET": "logos",
            "CLOUDFLARE_ACCOUNT_ID": "account-id",
            "CLOUDFLARE_API_TOKEN": "cloudflare-token",
            "VITE_TURNSTILE_SITE_KEY": "turnstile-site-key",
            "TURNSTILE_SECRET_KEY": "turnstile-secret-key",
            "BREVO_API_KEY": "brevo-api-key",
            "BREVO_SIGNUPS_LIST_ID": "list-id",
            "ALLOWED_WEB_ORIGINS": "https://boardenthusiasts.com",
            "SUPPORT_REPORT_RECIPIENT": "support@boardenthusiasts.com",
            "SUPPORT_REPORT_SENDER_EMAIL": "noreply@boardenthusiasts.com",
            "SUPPORT_REPORT_SENDER_NAME": "Board Enthusiasts",
            "DEPLOY_SMOKE_SECRET": "deploy-smoke-secret",
            "DEPLOY_SMOKE_PLAYER_EMAIL": "player@example.com",
            "DEPLOY_SMOKE_DEVELOPER_EMAIL": "developer@example.com",
            "DEPLOY_SMOKE_MODERATOR_EMAIL": "moderator@example.com",
            "DEPLOY_SMOKE_USER_PASSWORD": "deploy-smoke-password",
            "VITE_LANDING_MODE": "false",
        }
        call_order: list[tuple[str, str | None]] = []

        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(dev, "assert_command_available"))
            stack.enter_context(mock.patch.object(dev, "ensure_migration_workspace_scaffolding"))
            stack.enter_context(mock.patch.object(dev, "install_migration_workspace_dependencies"))
            stack.enter_context(mock.patch.object(dev, "collect_present_environment_values", return_value={}))
            stack.enter_context(mock.patch.object(dev, "require_environment_values", return_value=env_values))
            stack.enter_context(mock.patch.object(dev, "build_deploy_subprocess_environment", return_value={"env": "value"}))
            stack.enter_context(mock.patch.object(dev, "resolve_deploy_source_branch", return_value="main"))
            stack.enter_context(mock.patch.object(dev, "run_deploy_preflight"))
            stack.enter_context(mock.patch.object(dev, "run_deploy_dry_run"))
            stack.enter_context(mock.patch.object(dev, "build_deploy_fingerprint", return_value="fingerprint"))
            stack.enter_context(mock.patch.object(dev, "normalize_deploy_stage_state", return_value=(set(), {})))
            stack.enter_context(
                mock.patch.object(dev, "get_deploy_worker_config_path", return_value=pathlib.Path("wrangler.generated.jsonc"))
            )
            stack.enter_context(mock.patch.object(dev, "run_supabase_remote_config_push"))
            stack.enter_context(mock.patch.object(dev, "run_supabase_link"))
            stack.enter_context(mock.patch.object(dev, "run_supabase_remote_push"))
            stack.enter_context(mock.patch.object(dev, "assert_hosted_required_schema"))
            stack.enter_context(mock.patch.object(dev, "run_supabase_bucket_provisioning"))
            stack.enter_context(mock.patch.object(dev, "run_supabase_hosted_demo_seeding"))
            stack.enter_context(mock.patch.object(dev, "ensure_cloudflare_pages_project"))
            stack.enter_context(mock.patch.object(dev, "run_pages_deploy", return_value="pages-alias.example"))
            stack.enter_context(mock.patch.object(dev, "finalize_pages_custom_domain"))
            stack.enter_context(mock.patch.object(dev, "update_deploy_stage_completion"))
            stack.enter_context(mock.patch.object(dev, "run_workers_deploy_smoke"))
            stack.enter_context(mock.patch.object(dev, "run_pages_deploy_smoke"))
            stack.enter_context(mock.patch.object(dev, "write_step"))
            stack.enter_context(
                mock.patch.object(
                    dev,
                    "run_workers_deploy",
                    side_effect=lambda *args, **kwargs: call_order.append(("deploy", None)),
                )
            )
            stack.enter_context(
                mock.patch.object(
                    dev,
                    "sync_worker_secret",
                    side_effect=lambda *args, **kwargs: call_order.append(("secret", kwargs["secret_name"])),
                )
            )

            dev.deploy_migration_target(
                config,
                target="production",
                source_branch=None,
                force=False,
                upgrade=False,
                preflight_only=False,
                dry_run_only=False,
            )

        self.assertEqual(("deploy", None), call_order[0])
        self.assertEqual(
            [
                ("secret", "SUPABASE_SECRET_KEY"),
                ("secret", "TURNSTILE_SECRET_KEY"),
                ("secret", "BREVO_API_KEY"),
                ("secret", "DEPLOY_SMOKE_SECRET"),
            ],
            call_order[1:5],
        )

    def test_get_cloudflare_pages_projects_raises_actionable_guidance_when_api_access_fails(self) -> None:
        env_values = {
            "CLOUDFLARE_ACCOUNT_ID": "account-id",
            "CLOUDFLARE_API_TOKEN": "token",
        }

        with mock.patch.object(
            dev,
            "request_json",
            side_effect=dev.DevCliError(
                "HTTP 403 Forbidden for https://api.cloudflare.com/client/v4/accounts/account-id/pages/projects: "
                '{"success":false,"errors":[{"message":"Authentication error"}]}'
            ),
        ):
            with self.assertRaises(dev.DevCliError) as raised:
                dev.get_cloudflare_pages_projects(env_values)

        message = str(raised.exception)
        self.assertIn("Cloudflare Pages project listing failed", message)
        self.assertIn("Pages read access", message)
        self.assertIn("Original error", message)

    def test_get_cloudflare_pages_projects_retries_once_after_timeout(self) -> None:
        env_values = {
            "CLOUDFLARE_ACCOUNT_ID": "account-id",
            "CLOUDFLARE_API_TOKEN": "token",
        }

        with (
            mock.patch.object(
                dev,
                "request_json",
                side_effect=[
                    dev.DevCliError("Request timed out for https://api.cloudflare.com/client/v4/accounts/account-id/pages/projects after 30 seconds."),
                    {"result": [{"name": "board-enthusiasts-staging"}]},
                ],
            ) as request_json,
            mock.patch.object(dev, "write_step") as write_step,
            mock.patch.object(dev.time, "sleep") as sleep,
        ):
            projects = dev.get_cloudflare_pages_projects(env_values)

        self.assertEqual([{"name": "board-enthusiasts-staging"}], projects)
        self.assertEqual(2, request_json.call_count)
        write_step.assert_called_once()
        sleep.assert_called_once_with(2)

    def test_request_json_wraps_timeouts_in_cli_error(self) -> None:
        with mock.patch.object(
            dev.urllib.request,
            "urlopen",
            side_effect=TimeoutError("The read operation timed out"),
        ):
            with self.assertRaises(dev.DevCliError) as raised:
                dev.request_json(url="https://api.cloudflare.com/client/v4/accounts/example/pages/projects", timeout_seconds=15)

        message = str(raised.exception)
        self.assertIn("Request timed out", message)
        self.assertIn("15 seconds", message)

    def test_request_workers_deploy_smoke_json_retries_timeout_once(self) -> None:
        timeout_error = dev.DevCliError(
            "Request timed out for https://api.boardenthusiasts.com/player/wishlist after 30 seconds. "
            "Check your network connection and verify the target service is reachable."
        )

        with (
            mock.patch.object(dev, "request_json", side_effect=[timeout_error, {"titles": []}]) as request_json,
            mock.patch.object(dev, "write_step") as write_step,
            mock.patch.object(dev.time, "sleep") as sleep,
        ):
            payload = dev.request_workers_deploy_smoke_json(url="https://api.boardenthusiasts.com/player/wishlist")

        self.assertEqual({"titles": []}, payload)
        self.assertEqual(2, request_json.call_count)
        request_json.assert_called_with(
            url="https://api.boardenthusiasts.com/player/wishlist",
            method="GET",
            headers=None,
            payload=None,
            data=None,
            timeout_seconds=30,
        )
        write_step.assert_called_once_with(
            "Workers smoke request timed out; retrying once: https://api.boardenthusiasts.com/player/wishlist"
        )
        sleep.assert_called_once_with(5)

    def test_request_workers_deploy_smoke_json_does_not_retry_non_timeout_errors(self) -> None:
        error = dev.DevCliError("HTTP 500 Internal Server Error for https://api.boardenthusiasts.com/player/wishlist: no detail")

        with (
            mock.patch.object(dev, "request_json", side_effect=error) as request_json,
            mock.patch.object(dev, "write_step") as write_step,
            mock.patch.object(dev.time, "sleep") as sleep,
        ):
            with self.assertRaises(dev.DevCliError) as raised:
                dev.request_workers_deploy_smoke_json(url="https://api.boardenthusiasts.com/player/wishlist")

        self.assertIs(error, raised.exception)
        request_json.assert_called_once()
        write_step.assert_not_called()
        sleep.assert_not_called()

    def test_run_workers_deploy_smoke_preserves_smoke_secret_for_support_issue_probe(self) -> None:
        env_values = {
            "BOARD_ENTHUSIASTS_WORKERS_BASE_URL": "https://api.staging.boardenthusiasts.com",
            "BOARD_ENTHUSIASTS_SPA_BASE_URL": "https://staging.boardenthusiasts.com",
            "DEPLOY_SMOKE_SECRET": "smoke-secret",
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_PUBLISHABLE_KEY": "publishable-key",
            "SUPABASE_SECRET_KEY": "secret-key",
            "BREVO_API_KEY": "brevo-api-key",
            "VITE_LANDING_MODE": "true",
        }
        contact = {"id": "contact-1", "lifecycle_status": "waitlisted"}

        with mock.patch.object(dev, "wait_for_workers_deploy_smoke_base_url"), mock.patch.object(
            dev,
            "request_json",
            side_effect=[
                {"status": "ready"},
                {"accepted": True},
                {"accepted": True},
            ],
        ) as request_json, mock.patch.object(
            dev,
            "get_supabase_marketing_contact",
            side_effect=[contact, contact],
        ), mock.patch.object(
            dev,
            "get_supabase_marketing_contact_role_interests",
            return_value=["player"],
        ), mock.patch.object(
            dev,
            "get_brevo_contact",
            return_value={"id": 42},
        ), mock.patch.object(
            dev,
            "delete_supabase_marketing_contact",
        ), mock.patch.object(
            dev,
            "delete_brevo_contact",
        ), mock.patch.object(
            dev.time,
            "time",
            return_value=1773474581,
        ):
            dev.run_workers_deploy_smoke(
                dev.config_from_args(self.create_args(), pathlib.Path.cwd()),
                target="staging",
                env_values=env_values,
            )

        support_call = request_json.call_args_list[2]
        self.assertEqual("https://api.staging.boardenthusiasts.com/support/issues", support_call.kwargs["url"])
        self.assertEqual("smoke-secret", support_call.kwargs["headers"]["x-board-enthusiasts-deploy-smoke-secret"])

    def test_run_workers_deploy_smoke_requires_full_mvp_credentials_for_staging_when_landing_disabled(self) -> None:
        env_values = {
            "BOARD_ENTHUSIASTS_WORKERS_BASE_URL": "https://api.staging.boardenthusiasts.com",
            "BOARD_ENTHUSIASTS_SPA_BASE_URL": "https://staging.boardenthusiasts.com",
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_PUBLISHABLE_KEY": "publishable-key",
            "VITE_LANDING_MODE": "false",
        }

        with self.assertRaises(dev.DevCliError) as raised:
            dev.run_workers_deploy_smoke(
                dev.config_from_args(self.create_args(), pathlib.Path.cwd()),
                target="staging",
                env_values=env_values,
            )

        self.assertIn("Full-MVP deploy smoke requires smoke-account credentials", str(raised.exception))

    def test_run_workers_deploy_smoke_falls_back_to_public_mvp_for_production_without_smoke_accounts(self) -> None:
        env_values = {
            "BOARD_ENTHUSIASTS_WORKERS_BASE_URL": "https://api.boardenthusiasts.com",
            "BOARD_ENTHUSIASTS_SPA_BASE_URL": "https://boardenthusiasts.com",
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_PUBLISHABLE_KEY": "publishable-key",
            "VITE_LANDING_MODE": "false",
        }

        with (
            mock.patch.object(dev, "run_public_mvp_workers_deploy_smoke") as run_public_mvp_workers_deploy_smoke,
            mock.patch.object(dev, "run_full_mvp_workers_deploy_smoke") as run_full_mvp_workers_deploy_smoke,
        ):
            dev.run_workers_deploy_smoke(
                dev.config_from_args(self.create_args(), pathlib.Path.cwd()),
                target="production",
                env_values=env_values,
            )

        run_public_mvp_workers_deploy_smoke.assert_called_once()
        run_full_mvp_workers_deploy_smoke.assert_not_called()

    def test_run_workers_deploy_smoke_loads_full_mvp_smoke_accounts_from_process_environment(self) -> None:
        env_values = {
            "BOARD_ENTHUSIASTS_WORKERS_BASE_URL": "https://api.staging.boardenthusiasts.com",
            "BOARD_ENTHUSIASTS_SPA_BASE_URL": "https://staging.boardenthusiasts.com",
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_PUBLISHABLE_KEY": "publishable-key",
            "DEPLOY_SMOKE_USER_PASSWORD": "shared-password",
            "VITE_LANDING_MODE": "false",
        }

        with (
            mock.patch.dict(
                os.environ,
                {
                    "DEPLOY_SMOKE_PLAYER_EMAIL": "testing+staging-player@boardenthusiasts.com",
                    "DEPLOY_SMOKE_DEVELOPER_EMAIL": "testing+staging-developer@boardenthusiasts.com",
                    "DEPLOY_SMOKE_MODERATOR_EMAIL": "testing+staging-moderator@boardenthusiasts.com",
                    "DEPLOY_SMOKE_USER_PASSWORD": "shared-password",
                },
                clear=False,
            ),
            mock.patch.object(dev, "run_full_mvp_workers_deploy_smoke") as run_full_mvp_workers_deploy_smoke,
        ):
            dev.run_workers_deploy_smoke(
                dev.config_from_args(self.create_args(), pathlib.Path.cwd()),
                target="staging",
                env_values=env_values,
            )

        forwarded_env_values = run_full_mvp_workers_deploy_smoke.call_args.kwargs["env_values"]
        self.assertEqual(
            "testing+staging-player@boardenthusiasts.com",
            forwarded_env_values["DEPLOY_SMOKE_PLAYER_EMAIL"],
        )
        self.assertEqual(
            "testing+staging-developer@boardenthusiasts.com",
            forwarded_env_values["DEPLOY_SMOKE_DEVELOPER_EMAIL"],
        )
        self.assertEqual(
            "testing+staging-moderator@boardenthusiasts.com",
            forwarded_env_values["DEPLOY_SMOKE_MODERATOR_EMAIL"],
        )

    def test_run_pages_deploy_smoke_checks_full_mvp_routes_when_landing_disabled(self) -> None:
        env_values = {
            "BOARD_ENTHUSIASTS_SPA_BASE_URL": "https://staging.boardenthusiasts.com",
            "VITE_LANDING_MODE": "false",
        }

        with mock.patch.object(dev, "wait_for_pages_shell") as wait_for_pages_shell:
            dev.run_pages_deploy_smoke(target="staging", env_values=env_values)

        self.assertEqual(
            [
                mock.call("https://staging.boardenthusiasts.com"),
                mock.call("https://staging.boardenthusiasts.com/offerings"),
                mock.call("https://staging.boardenthusiasts.com/browse"),
                mock.call("https://staging.boardenthusiasts.com/studios"),
                mock.call("https://staging.boardenthusiasts.com/install"),
                mock.call("https://staging.boardenthusiasts.com/support"),
                mock.call("https://staging.boardenthusiasts.com/studios/blue-harbor-games"),
                mock.call("https://staging.boardenthusiasts.com/browse/blue-harbor-games/lantern-drift"),
                mock.call("https://staging.boardenthusiasts.com/player"),
                mock.call("https://staging.boardenthusiasts.com/developer"),
                mock.call("https://staging.boardenthusiasts.com/moderate"),
            ],
            wait_for_pages_shell.call_args_list,
        )

    def test_run_pages_deploy_smoke_checks_public_routes_for_production(self) -> None:
        env_values = {
            "BOARD_ENTHUSIASTS_SPA_BASE_URL": "https://boardenthusiasts.com",
            "VITE_LANDING_MODE": "false",
        }

        with mock.patch.object(dev, "wait_for_pages_shell") as wait_for_pages_shell:
            dev.run_pages_deploy_smoke(target="production", env_values=env_values)

        self.assertEqual(
            [
                mock.call("https://boardenthusiasts.com"),
                mock.call("https://boardenthusiasts.com/offerings"),
                mock.call("https://boardenthusiasts.com/browse"),
                mock.call("https://boardenthusiasts.com/studios"),
                mock.call("https://boardenthusiasts.com/install"),
                mock.call("https://boardenthusiasts.com/support"),
            ],
            wait_for_pages_shell.call_args_list,
        )

    def test_run_full_mvp_workers_deploy_smoke_uses_current_title_and_release_routes(self) -> None:
        env_values = {
            "BOARD_ENTHUSIASTS_WORKERS_BASE_URL": "https://api.staging.boardenthusiasts.com",
            "BOARD_ENTHUSIASTS_SPA_BASE_URL": "https://staging.boardenthusiasts.com",
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_PUBLISHABLE_KEY": "publishable-key",
            "DEPLOY_SMOKE_PLAYER_EMAIL": "testing+staging-player@boardenthusiasts.com",
            "DEPLOY_SMOKE_DEVELOPER_EMAIL": "testing+staging-developer@boardenthusiasts.com",
            "DEPLOY_SMOKE_MODERATOR_EMAIL": "testing+staging-moderator@boardenthusiasts.com",
            "DEPLOY_SMOKE_USER_PASSWORD": "shared-password",
        }
        request_calls: list[dict[str, object | None]] = []
        release_create_count = 0
        report_create_count = 0

        def fake_request_json(*, url: str, method: str = "GET", headers: dict[str, str] | None = None, payload: object = None, **_: object) -> object:
            nonlocal release_create_count, report_create_count
            request_calls.append({"url": url, "method": method, "headers": headers, "payload": payload})

            if url.endswith("/health/ready"):
                return {"status": "ready"}
            if url == "https://api.staging.boardenthusiasts.com/":
                return {"service": "board-enthusiasts-workers-api"}
            if url.endswith("/genres"):
                return {"genres": [{"slug": "utility"}]}
            if url.endswith("/age-rating-authorities"):
                return {"ageRatingAuthorities": [{"code": "ESRB"}]}
            if url.endswith("/spotlights/home"):
                return {"entries": []}
            if url.endswith("/internal/home-offering-spotlights"):
                return {"entries": []}
            if url.endswith("/internal/be-home/metrics"):
                return {"metrics": {"communityActiveNowTotal": 0}}
            if url.endswith("/studios") and method == "GET":
                return {"studios": []}
            if "/catalog?pageNumber=1&pageSize=4&sort=title-asc" in url:
                return {
                    "titles": [
                        {
                            "id": "public-title",
                            "slug": "lantern-drift",
                            "studioSlug": "blue-harbor-games",
                            "acquisitionUrl": "https://blue-harbor-games.example/lantern-drift",
                        }
                    ]
                }
            if url.endswith("/identity/me/notifications"):
                return {"notifications": [{"id": "notification-1"}]}
            if url.endswith("/developer/studios"):
                return {"studios": []}
            if url.endswith("/studios") and method == "POST":
                return {"studio": {"id": "studio-1"}}
            if url.endswith("/links") and method == "POST":
                return {"link": {"id": "link-1"}}
            if url.endswith("/developer/studios/studio-1/titles") and method == "POST":
                return {"title": {"id": "title-1"}}
            if url.endswith("/metadata/current") and method == "PUT":
                return {"title": {"currentMetadataRevision": 2}}
            if url.endswith("/releases") and method == "POST":
                release_create_count += 1
                return {"release": {"id": f"release-{release_create_count}"}}
            if url.endswith("/releases") and method == "GET":
                return {"releases": [{"version": "0.1.0-smoke"}, {"version": "0.1.1-smoke"}]}
            if url.endswith("/player/reports") and method == "POST":
                report_create_count += 1
                return {"report": {"id": f"report-{report_create_count}"}}
            if "/moderation/developers?search=" in url:
                return {
                    "developers": [
                        {
                            "email": "testing+staging-developer@boardenthusiasts.com",
                            "developerSubject": "developer-subject-1",
                        }
                    ]
                }
            return {}

        with (
            mock.patch.object(dev, "wait_for_workers_deploy_smoke_base_url"),
            mock.patch.object(
                dev,
                "fetch_supabase_access_token",
                side_effect=["player-token", "developer-token", "moderator-token"],
            ),
            mock.patch.object(dev, "request_json", side_effect=fake_request_json),
            mock.patch.object(dev.time, "time", return_value=1773474581),
        ):
            dev.run_full_mvp_workers_deploy_smoke(target="staging", env_values=env_values)

        title_update_call = next(
            call
            for call in request_calls
            if call["url"] == "https://api.staging.boardenthusiasts.com/developer/titles/title-1" and call["method"] == "PUT"
        )
        self.assertEqual({"contentKind": "game", "visibility": "unlisted"}, title_update_call["payload"])

        title_create_call = next(
            call
            for call in request_calls
            if call["url"] == "https://api.staging.boardenthusiasts.com/developer/studios/studio-1/titles" and call["method"] == "POST"
        )
        self.assertNotIn("visibility", title_create_call["payload"])
        self.assertNotIn("lifecycleStatus", title_create_call["payload"])
        self.assertEqual(False, title_create_call["payload"]["metadata"]["maxPlayersOrMore"])

        title_metadata_call = next(
            call
            for call in request_calls
            if call["url"] == "https://api.staging.boardenthusiasts.com/developer/titles/title-1/metadata/current"
            and call["method"] == "PUT"
        )
        self.assertEqual(False, title_metadata_call["payload"]["maxPlayersOrMore"])

        title_media_call = next(
            call
            for call in request_calls
            if call["url"] == "https://api.staging.boardenthusiasts.com/developer/titles/title-1/media/card"
            and call["method"] == "PUT"
        )
        self.assertEqual(1200, title_media_call["payload"]["height"])

        requested_urls = [str(call["url"]) for call in request_calls]
        self.assertIn("https://api.staging.boardenthusiasts.com/developer/titles/title-1/activate", requested_urls)
        self.assertIn("https://api.staging.boardenthusiasts.com/developer/titles/title-1/archive", requested_urls)
        self.assertIn("https://api.staging.boardenthusiasts.com/developer/titles/title-1/unarchive", requested_urls)
        self.assertNotIn("https://api.staging.boardenthusiasts.com/developer/titles/title-1/releases/release-1/publish", requested_urls)
        self.assertNotIn("https://api.staging.boardenthusiasts.com/developer/titles/title-1/releases/release-1/withdraw", requested_urls)

    def test_run_full_mvp_workers_deploy_smoke_allows_empty_production_catalog(self) -> None:
        env_values = {
            "BOARD_ENTHUSIASTS_WORKERS_BASE_URL": "https://api.boardenthusiasts.com",
            "BOARD_ENTHUSIASTS_SPA_BASE_URL": "https://boardenthusiasts.com",
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_PUBLISHABLE_KEY": "publishable-key",
            "DEPLOY_SMOKE_PLAYER_EMAIL": "testing+player@boardenthusiasts.com",
            "DEPLOY_SMOKE_DEVELOPER_EMAIL": "testing+developer@boardenthusiasts.com",
            "DEPLOY_SMOKE_MODERATOR_EMAIL": "testing+moderator@boardenthusiasts.com",
            "DEPLOY_SMOKE_USER_PASSWORD": "shared-password",
        }
        request_calls: list[dict[str, object | None]] = []
        release_create_count = 0
        report_create_count = 0

        def fake_request_json(*, url: str, method: str = "GET", headers: dict[str, str] | None = None, payload: object = None, **_: object) -> object:
            nonlocal release_create_count, report_create_count
            request_calls.append({"url": url, "method": method, "headers": headers, "payload": payload})

            if url.endswith("/health/ready"):
                return {"status": "ready"}
            if url == "https://api.boardenthusiasts.com/":
                return {"service": "board-enthusiasts-workers-api"}
            if url.endswith("/genres"):
                return {"genres": [{"slug": "utility"}]}
            if url.endswith("/age-rating-authorities"):
                return {"ageRatingAuthorities": [{"code": "ESRB"}]}
            if url.endswith("/spotlights/home"):
                return {"entries": []}
            if url.endswith("/internal/home-offering-spotlights"):
                return {"entries": []}
            if url.endswith("/internal/be-home/metrics"):
                return {"metrics": {"communityActiveNowTotal": 0}}
            if url.endswith("/studios") and method == "GET":
                return {"studios": []}
            if "/catalog?pageNumber=1&pageSize=4&sort=title-asc" in url:
                return {"titles": []}
            if url.endswith("/identity/me/notifications"):
                return {"notifications": [{"id": "notification-1"}]}
            if url.endswith("/developer/studios"):
                return {"studios": []}
            if url.endswith("/studios") and method == "POST":
                return {"studio": {"id": "studio-1"}}
            if url.endswith("/links") and method == "POST":
                return {"link": {"id": "link-1"}}
            if url.endswith("/developer/studios/studio-1/titles") and method == "POST":
                return {"title": {"id": "title-1"}}
            if url.endswith("/metadata/current") and method == "PUT":
                return {"title": {"currentMetadataRevision": 2}}
            if url.endswith("/releases") and method == "POST":
                release_create_count += 1
                return {"release": {"id": f"release-{release_create_count}"}}
            if url.endswith("/releases") and method == "GET":
                return {"releases": [{"version": "0.1.0-smoke"}, {"version": "0.1.1-smoke"}]}
            if url.endswith("/player/reports") and method == "POST":
                report_create_count += 1
                return {"report": {"id": f"report-{report_create_count}"}}
            if "/moderation/developers?search=" in url:
                return {
                    "developers": [
                        {
                            "email": "testing+developer@boardenthusiasts.com",
                            "developerSubject": "developer-subject-1",
                        }
                    ]
                }
            return {}

        with (
            mock.patch.object(dev, "wait_for_workers_deploy_smoke_base_url"),
            mock.patch.object(
                dev,
                "fetch_supabase_access_token",
                side_effect=["player-token", "developer-token", "moderator-token"],
            ),
            mock.patch.object(dev, "request_json", side_effect=fake_request_json),
            mock.patch.object(dev.time, "time", return_value=1773474581),
        ):
            dev.run_full_mvp_workers_deploy_smoke(target="production", env_values=env_values)

        requested_urls = [str(call["url"]) for call in request_calls]
        self.assertIn("https://api.boardenthusiasts.com/player/library", requested_urls)
        self.assertIn("https://api.boardenthusiasts.com/player/wishlist", requested_urls)
        self.assertNotIn("https://api.boardenthusiasts.com/player/library/titles/", "".join(requested_urls))
        self.assertNotIn("https://api.boardenthusiasts.com/player/wishlist/titles/", "".join(requested_urls))
        self.assertNotIn("https://api.boardenthusiasts.com/catalog/", "".join(requested_urls))

    def test_run_full_mvp_workers_deploy_smoke_uses_library_eligible_public_title_for_production(self) -> None:
        env_values = {
            "BOARD_ENTHUSIASTS_WORKERS_BASE_URL": "https://api.boardenthusiasts.com",
            "BOARD_ENTHUSIASTS_SPA_BASE_URL": "https://boardenthusiasts.com",
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_PUBLISHABLE_KEY": "publishable-key",
            "DEPLOY_SMOKE_PLAYER_EMAIL": "testing+player@boardenthusiasts.com",
            "DEPLOY_SMOKE_DEVELOPER_EMAIL": "testing+developer@boardenthusiasts.com",
            "DEPLOY_SMOKE_MODERATOR_EMAIL": "testing+moderator@boardenthusiasts.com",
            "DEPLOY_SMOKE_USER_PASSWORD": "shared-password",
        }
        request_calls: list[dict[str, object | None]] = []
        release_create_count = 0
        report_create_count = 0

        def fake_request_json(*, url: str, method: str = "GET", headers: dict[str, str] | None = None, payload: object = None, **_: object) -> object:
            nonlocal release_create_count, report_create_count
            request_calls.append({"url": url, "method": method, "headers": headers, "payload": payload})

            if url.endswith("/health/ready"):
                return {"status": "ready"}
            if url == "https://api.boardenthusiasts.com/":
                return {"service": "board-enthusiasts-workers-api"}
            if url.endswith("/genres"):
                return {"genres": [{"slug": "utility"}]}
            if url.endswith("/age-rating-authorities"):
                return {"ageRatingAuthorities": [{"code": "ESRB"}]}
            if url.endswith("/spotlights/home"):
                return {"entries": []}
            if url.endswith("/internal/home-offering-spotlights"):
                return {"entries": []}
            if url.endswith("/internal/be-home/metrics"):
                return {"metrics": {"communityActiveNowTotal": 0}}
            if url.endswith("/studios") and method == "GET":
                return {"studios": []}
            if "/catalog?pageNumber=1&pageSize=4&sort=title-asc" in url:
                return {
                    "titles": [
                        {
                            "id": "coming-soon-title",
                            "slug": "beacon-boardwalk",
                            "studioSlug": "north-maple-interactive",
                            "acquisitionUrl": None,
                        },
                        {
                            "id": "available-title",
                            "slug": "lantern-drift",
                            "studioSlug": "blue-harbor-games",
                            "acquisitionUrl": "https://blue-harbor-games.example/lantern-drift",
                        },
                    ]
                }
            if url.endswith("/identity/me/notifications"):
                return {"notifications": [{"id": "notification-1"}]}
            if url.endswith("/developer/studios"):
                return {"studios": []}
            if url.endswith("/studios") and method == "POST":
                return {"studio": {"id": "studio-1"}}
            if url.endswith("/links") and method == "POST":
                return {"link": {"id": "link-1"}}
            if url.endswith("/developer/studios/studio-1/titles") and method == "POST":
                return {"title": {"id": "title-1"}}
            if url.endswith("/metadata/current") and method == "PUT":
                return {"title": {"currentMetadataRevision": 2}}
            if url.endswith("/releases") and method == "POST":
                release_create_count += 1
                return {"release": {"id": f"release-{release_create_count}"}}
            if url.endswith("/releases") and method == "GET":
                return {"releases": [{"version": "0.1.0-smoke"}, {"version": "0.1.1-smoke"}]}
            if url.endswith("/player/reports") and method == "POST":
                report_create_count += 1
                return {"report": {"id": f"report-{report_create_count}"}}
            if "/moderation/developers?search=" in url:
                return {
                    "developers": [
                        {
                            "email": "testing+developer@boardenthusiasts.com",
                            "developerSubject": "developer-subject-1",
                        }
                    ]
                }
            return {}

        with (
            mock.patch.object(dev, "wait_for_workers_deploy_smoke_base_url"),
            mock.patch.object(
                dev,
                "fetch_supabase_access_token",
                side_effect=["player-token", "developer-token", "moderator-token"],
            ),
            mock.patch.object(dev, "request_json", side_effect=fake_request_json),
            mock.patch.object(dev.time, "time", return_value=1773474581),
        ):
            dev.run_full_mvp_workers_deploy_smoke(target="production", env_values=env_values)

        requested_urls = [str(call["url"]) for call in request_calls]
        self.assertIn(
            "https://api.boardenthusiasts.com/catalog/north-maple-interactive/beacon-boardwalk",
            requested_urls,
        )
        self.assertIn(
            "https://api.boardenthusiasts.com/studios/north-maple-interactive",
            requested_urls,
        )
        self.assertIn(
            "https://api.boardenthusiasts.com/player/library/titles/available-title",
            requested_urls,
        )
        self.assertNotIn(
            "https://api.boardenthusiasts.com/player/library/titles/coming-soon-title",
            requested_urls,
        )
        self.assertIn(
            "https://api.boardenthusiasts.com/player/wishlist/titles/coming-soon-title",
            requested_urls,
        )

    def test_has_local_required_schema_includes_marketing_contacts(self) -> None:
        runtime_env = {
            "SUPABASE_URL": "http://127.0.0.1:54321",
            "SUPABASE_SECRET_KEY": "secret-key",
        }
        requested_urls: list[str] = []

        class _Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        def fake_urlopen(request, timeout=10):
            requested_urls.append(request.full_url)
            return _Response()

        with mock.patch.object(dev.urllib.request, "urlopen", side_effect=fake_urlopen):
            self.assertTrue(dev.has_local_required_schema(runtime_env))

        self.assertEqual(
            [
                "http://127.0.0.1:54321/rest/v1/titles?select=*&limit=1",
                "http://127.0.0.1:54321/rest/v1/genres?select=*&limit=1",
                "http://127.0.0.1:54321/rest/v1/age_rating_authorities?select=*&limit=1",
                "http://127.0.0.1:54321/rest/v1/marketing_contacts?select=*&limit=1",
                "http://127.0.0.1:54321/rest/v1/catalog_media_type_definitions?select=*&limit=1",
                "http://127.0.0.1:54321/rest/v1/catalog_media_entries?select=*&limit=1",
            ],
            requested_urls,
        )

    def test_apply_local_supabase_migrations_runs_supabase_migration_up(self) -> None:
        config = dev.config_from_args(self.create_args(), pathlib.Path.cwd())

        with (
            mock.patch.object(dev, "ensure_migration_workspace_scaffolding"),
            mock.patch.object(dev, "ensure_docker_daemon_available"),
            mock.patch.object(dev, "resolve_supabase_command_prefix", return_value=["supabase"]),
            mock.patch.object(
                dev,
                "run_command",
                return_value=mock.Mock(returncode=0, stdout="Applying migration 20260407153000", stderr=""),
            ) as run_command,
            mock.patch.object(dev, "print_console_text") as print_console_text,
        ):
            dev.apply_local_supabase_migrations(config)

        run_command.assert_called_once_with(
            ["supabase", "migration", "up"],
            cwd=config.repo_root / config.supabase_root,
            check=False,
            capture_output=True,
        )
        print_console_text.assert_called_once_with("Applying migration 20260407153000")

    def test_ensure_local_demo_seed_data_applies_local_migrations_before_seed_probe(self) -> None:
        config = dev.config_from_args(self.create_args(), pathlib.Path.cwd())
        runtime_env = {
            "SUPABASE_URL": "http://127.0.0.1:54321",
            "SUPABASE_SECRET_KEY": "secret-key",
        }

        with (
            mock.patch.object(dev, "wait_for_local_supabase_http_ready") as wait_ready,
            mock.patch.object(dev, "apply_local_supabase_migrations") as apply_local_migrations,
            mock.patch.object(dev, "has_local_required_schema", return_value=True) as has_required_schema,
            mock.patch.object(dev, "has_local_demo_seed_data", return_value=True) as has_seed_data,
            mock.patch.object(dev, "seed_migration_data") as seed_migration_data,
        ):
            dev.ensure_local_demo_seed_data(config, runtime_env=runtime_env)

        self.assertEqual(
            [mock.call(runtime_env=runtime_env), mock.call(runtime_env=runtime_env)],
            wait_ready.call_args_list,
        )
        apply_local_migrations.assert_called_once_with(config)
        has_required_schema.assert_called_once_with(runtime_env)
        has_seed_data.assert_called_once_with(runtime_env=runtime_env)
        seed_migration_data.assert_not_called()

    def test_ensure_local_demo_seed_data_raises_when_required_schema_is_still_missing_after_migrations(self) -> None:
        config = dev.config_from_args(self.create_args(), pathlib.Path.cwd())
        runtime_env = {
            "SUPABASE_URL": "http://127.0.0.1:54321",
            "SUPABASE_SECRET_KEY": "secret-key",
        }

        with (
            mock.patch.object(dev, "wait_for_local_supabase_http_ready"),
            mock.patch.object(dev, "apply_local_supabase_migrations"),
            mock.patch.object(dev, "has_local_required_schema", return_value=False),
            mock.patch.object(dev, "run_supabase_stack_command") as run_supabase_stack_command,
        ):
            with self.assertRaises(dev.DevCliError) as raised:
                dev.ensure_local_demo_seed_data(config, runtime_env=runtime_env)

        self.assertIn("seed-data --reset", str(raised.exception))
        run_supabase_stack_command.assert_not_called()

    def test_request_json_does_not_force_browser_user_agent(self) -> None:
        captured_user_agent: str | None = None

        class _Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self) -> bytes:
                return b'{"ok": true}'

        def fake_urlopen(request, timeout=15, context=None):
            nonlocal captured_user_agent
            captured_user_agent = request.headers.get("User-agent")
            return _Response()

        with mock.patch.object(dev.urllib.request, "urlopen", side_effect=fake_urlopen):
            payload = dev.request_json(url="https://example.com/api")

        self.assertEqual({"ok": True}, payload)
        self.assertIsNone(captured_user_agent)

    def test_is_expected_pages_shell_html_accepts_vite_spa_shell(self) -> None:
        html = """
<!doctype html>
<html lang="en">
  <head>
    <title>Board Enthusiasts | Community Hub for Board Players and Builders</title>
    <script type="module" crossorigin src="/assets/index-abc123.js"></script>
    <link rel="stylesheet" crossorigin href="/assets/index-def456.css">
  </head>
  <body>
    <div id="root"></div>
  </body>
</html>
"""

        self.assertTrue(dev.is_expected_pages_shell_html(html))

    def test_is_expected_pages_shell_html_rejects_unrelated_shell_without_brand_marker(self) -> None:
        html = """
<!doctype html>
<html lang="en">
  <head>
    <title>Example App</title>
    <script type="module" crossorigin src="/assets/index-abc123.js"></script>
    <link rel="stylesheet" crossorigin href="/assets/index-def456.css">
  </head>
  <body>
    <div id="root"></div>
  </body>
</html>
"""

        self.assertFalse(dev.is_expected_pages_shell_html(html))

    def test_is_expected_pages_shell_html_rejects_cloudflare_placeholder(self) -> None:
        html = """
<html>
  <head><title>Nothing is here yet</title></head>
  <body>Nothing is here yet</body>
</html>
"""

        self.assertFalse(dev.is_expected_pages_shell_html(html))

    def test_build_supabase_profile_start_command_matches_supported_profiles(self) -> None:
        prefix = ["npx", "supabase"]

        self.assertEqual(
            ["npx", "supabase", "db", "start"],
            dev.build_supabase_profile_start_command(
                prefix=prefix,
                profile=dev.SUPABASE_PROFILE_DATABASE,
            ),
        )
        self.assertEqual(
            [
                "npx",
                "supabase",
                "start",
                "-x",
                "studio",
                "-x",
                "storage-api",
                "-x",
                "imgproxy",
                "-x",
                "postgres-meta",
                "-x",
                "realtime",
                "-x",
                "postgrest",
                "-x",
                "edge-runtime",
                "-x",
                "logflare",
                "-x",
                "vector",
                "-x",
                "supavisor",
            ],
            dev.build_supabase_profile_start_command(
                prefix=prefix,
                profile=dev.SUPABASE_PROFILE_AUTH,
            ),
        )
        self.assertEqual(
            [
                "npx",
                "supabase",
                "start",
                "-x",
                "studio",
                "-x",
                "imgproxy",
                "-x",
                "postgres-meta",
                "-x",
                "realtime",
                "-x",
                "edge-runtime",
                "-x",
                "logflare",
                "-x",
                "vector",
                "-x",
                "supavisor",
            ],
            dev.build_supabase_profile_start_command(
                prefix=prefix,
                profile=dev.SUPABASE_PROFILE_API,
            ),
        )

        self.assertEqual(
            [
                "npx",
                "supabase",
                "start",
                "-x",
                "studio",
                "-x",
                "imgproxy",
                "-x",
                "postgres-meta",
                "-x",
                "realtime",
                "-x",
                "edge-runtime",
                "-x",
                "logflare",
                "-x",
                "vector",
                "-x",
                "supavisor",
            ],
            dev.build_supabase_profile_start_command(
                prefix=prefix,
                profile=dev.SUPABASE_PROFILE_WEB,
            ),
        )

    def test_parse_env_assignments_unquotes_supabase_status_values(self) -> None:
        parsed = dev.parse_env_assignments(
            'API_URL="http://127.0.0.1:54321"\nANON_KEY="anon"\nSERVICE_ROLE_KEY="service"\n'
        )

        self.assertEqual("http://127.0.0.1:54321", parsed["API_URL"])
        self.assertEqual("anon", parsed["ANON_KEY"])
        self.assertEqual("service", parsed["SERVICE_ROLE_KEY"])

    def test_get_supabase_status_env_backfills_current_cli_fields(self) -> None:
        args = self.create_args()
        config = dev.config_from_args(args, pathlib.Path.cwd())

        completed = subprocess.CompletedProcess(
            args=["npx", "supabase", "status", "-o", "env"],
            returncode=0,
            stdout=(
                'ANON_KEY="anon"\n'
                'PUBLISHABLE_KEY="publishable"\n'
                'SERVICE_ROLE_KEY="service"\n'
            ),
            stderr="",
        )

        with mock.patch.object(dev, "resolve_supabase_command_prefix", return_value=["npx", "supabase"]), mock.patch.object(
            dev,
            "run_command",
            return_value=completed,
        ):
            status_env = dev.get_supabase_status_env(config)

        self.assertEqual(dev.LOCAL_SUPABASE_URL, status_env["API_URL"])
        self.assertEqual("anon", status_env["ANON_KEY"])
        self.assertEqual("service", status_env["SERVICE_ROLE_KEY"])

    def test_get_supabase_status_env_times_out_with_recovery_guidance(self) -> None:
        args = self.create_args()
        config = dev.config_from_args(args, pathlib.Path.cwd())

        with mock.patch.object(dev, "resolve_supabase_command_prefix", return_value=["npx", "supabase"]), mock.patch.object(
            dev,
            "run_command",
            side_effect=subprocess.TimeoutExpired(
                cmd=["npx", "supabase", "status", "-o", "env"],
                timeout=dev.SUPABASE_STATUS_TIMEOUT_SECONDS,
            ),
        ):
            with self.assertRaises(dev.DevCliError) as raised:
                dev.get_supabase_status_env(config)

        self.assertIn("timed out", str(raised.exception).lower())
        self.assertIn("database down", str(raised.exception))

    def test_get_local_supabase_urls_and_mailpit_respect_port_overrides(self) -> None:
        with mock.patch.dict(
            dev.os.environ,
            {
                "BOARD_ENTHUSIASTS_LOCAL_SUPABASE_API_PORT": "56421",
                "BOARD_ENTHUSIASTS_LOCAL_SUPABASE_DB_PORT": "56432",
                "BOARD_ENTHUSIASTS_LOCAL_MAILPIT_PORT": "56424",
            },
            clear=False,
        ):
            self.assertEqual("http://127.0.0.1:56421", dev.get_local_supabase_url())
            self.assertEqual("http://127.0.0.1:56421/auth/v1/health", dev.get_local_supabase_auth_url())
            self.assertEqual(56432, dev.get_local_supabase_db_port())
            self.assertEqual("http://127.0.0.1:56424", dev.get_local_mailpit_url())

    def test_get_supabase_project_id_reads_config_value(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)
            supabase_root = repo_root / config.supabase_root
            supabase_root.mkdir(parents=True, exist_ok=True)
            (supabase_root / "config.toml").write_text('project_id = "board-enthusiasts-local"\n', encoding="utf-8")

            self.assertEqual("board-enthusiasts-local", dev.get_supabase_project_id(config))

    def test_build_supabase_bearer_headers_uses_apikey_and_bearer(self) -> None:
        headers = dev.build_supabase_bearer_headers(api_key="secret-key")

        self.assertEqual("secret-key", headers["apikey"])
        self.assertEqual("Bearer secret-key", headers["authorization"])
        self.assertEqual("application/json", headers["accept"])

    def test_ensure_runtime_profile_reuses_matching_runtime_when_supabase_is_healthy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)

            runtime_env = {
                "SUPABASE_URL": "http://127.0.0.1:54321",
                "SUPABASE_SECRET_KEY": "secret-key",
            }

            with (
                mock.patch.object(dev, "load_runtime_profile_state", return_value=dev.SUPABASE_PROFILE_WEB),
                mock.patch.object(dev, "stop_all_managed_application_processes") as stop_processes,
                mock.patch.object(dev, "get_local_supabase_runtime", return_value=runtime_env),
                mock.patch.object(dev, "wait_for_local_supabase_http_ready") as wait_for_ready,
                mock.patch.object(dev, "save_runtime_profile_state") as save_state,
                mock.patch.object(dev, "restart_runtime_profile") as restart_runtime_profile,
            ):
                dev.ensure_runtime_profile(config, profile=dev.SUPABASE_PROFILE_WEB)

            stop_processes.assert_called_once_with(config)
            wait_for_ready.assert_called_once_with(runtime_env=runtime_env)
            save_state.assert_called_once_with(config, profile=dev.SUPABASE_PROFILE_WEB)
            restart_runtime_profile.assert_not_called()

    def test_ensure_runtime_profile_reuses_live_web_runtime_without_state_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)

            runtime_env = {
                "SUPABASE_URL": "http://127.0.0.1:54321",
                "SUPABASE_SECRET_KEY": "secret-key",
            }

            with (
                mock.patch.object(dev, "load_runtime_profile_state", return_value=None),
                mock.patch.object(dev, "stop_all_managed_application_processes") as stop_processes,
                mock.patch.object(dev, "get_local_supabase_runtime", return_value=runtime_env),
                mock.patch.object(dev, "wait_for_local_supabase_http_ready") as wait_for_ready,
                mock.patch.object(dev, "save_runtime_profile_state") as save_state,
                mock.patch.object(dev, "restart_runtime_profile") as restart_runtime_profile,
            ):
                dev.ensure_runtime_profile(config, profile=dev.SUPABASE_PROFILE_WEB)

            stop_processes.assert_called_once_with(config)
            wait_for_ready.assert_called_once_with(runtime_env=runtime_env)
            save_state.assert_called_once_with(config, profile=dev.SUPABASE_PROFILE_WEB)
            restart_runtime_profile.assert_not_called()

    def test_ensure_runtime_profile_restarts_matching_runtime_when_supabase_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)

            with (
                mock.patch.object(dev, "load_runtime_profile_state", return_value=dev.SUPABASE_PROFILE_WEB),
                mock.patch.object(dev, "stop_all_managed_application_processes") as stop_processes,
                mock.patch.object(
                    dev,
                    "get_local_supabase_runtime",
                    side_effect=dev.DevCliError("Local Supabase services are not running."),
                ),
                mock.patch.object(dev, "wait_for_local_supabase_http_ready") as wait_for_ready,
                mock.patch.object(dev, "save_runtime_profile_state") as save_state,
                mock.patch.object(dev, "restart_runtime_profile") as restart_runtime_profile,
            ):
                dev.ensure_runtime_profile(config, profile=dev.SUPABASE_PROFILE_WEB)

            stop_processes.assert_called_once_with(config)
            wait_for_ready.assert_not_called()
            save_state.assert_not_called()
            restart_runtime_profile.assert_called_once_with(config, profile=dev.SUPABASE_PROFILE_WEB)

    def test_ensure_runtime_profile_restarts_when_requested_profile_differs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)

            with (
                mock.patch.object(dev, "load_runtime_profile_state", return_value=dev.SUPABASE_PROFILE_AUTH),
                mock.patch.object(dev, "stop_all_managed_application_processes") as stop_processes,
                mock.patch.object(dev, "get_local_supabase_runtime") as get_local_supabase_runtime,
                mock.patch.object(dev, "wait_for_local_supabase_http_ready") as wait_for_ready,
                mock.patch.object(dev, "save_runtime_profile_state") as save_state,
                mock.patch.object(dev, "restart_runtime_profile") as restart_runtime_profile,
            ):
                dev.ensure_runtime_profile(config, profile=dev.SUPABASE_PROFILE_WEB)

            stop_processes.assert_not_called()
            get_local_supabase_runtime.assert_not_called()
            wait_for_ready.assert_not_called()
            save_state.assert_not_called()
            restart_runtime_profile.assert_called_once_with(config, profile=dev.SUPABASE_PROFILE_WEB)

    def test_run_supabase_stop_retries_transient_docker_prune_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)
            (repo_root / config.supabase_root).mkdir(parents=True, exist_ok=True)

            transient_failure = subprocess.CompletedProcess(
                args=["npx", "supabase", "stop"],
                returncode=1,
                stdout="",
                stderr="failed to prune containers: Error response from daemon: a prune operation is already running",
            )
            success = subprocess.CompletedProcess(
                args=["npx", "supabase", "stop"],
                returncode=0,
                stdout="",
                stderr="",
            )

            with (
                mock.patch.object(dev, "ensure_migration_workspace_scaffolding"),
                mock.patch.object(dev, "ensure_docker_daemon_available"),
                mock.patch.object(dev, "resolve_supabase_command_prefix", return_value=["npx", "supabase"]),
                mock.patch.object(dev, "run_command", side_effect=[transient_failure, success]) as run_command,
                mock.patch.object(dev.time, "sleep") as sleep,
            ):
                dev.run_supabase_stack_command(config, action="stop")

            self.assertEqual(2, run_command.call_count)
            sleep.assert_called_once_with(2)

    def test_run_supabase_stop_times_out_and_force_removes_project_containers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)
            (repo_root / config.supabase_root).mkdir(parents=True, exist_ok=True)

            with (
                mock.patch.object(dev, "ensure_migration_workspace_scaffolding"),
                mock.patch.object(dev, "ensure_docker_daemon_available"),
                mock.patch.object(dev, "resolve_supabase_command_prefix", return_value=["npx", "supabase"]),
                mock.patch.object(
                    dev,
                    "run_command",
                    side_effect=subprocess.TimeoutExpired(cmd=["npx", "supabase", "stop"], timeout=dev.SUPABASE_STOP_TIMEOUT_SECONDS),
                ) as run_command,
                mock.patch.object(dev, "force_remove_supabase_project_containers", return_value=True) as force_remove,
            ):
                dev.run_supabase_stack_command(config, action="stop")

            run_command.assert_called_once_with(
                ["npx", "supabase", "stop"],
                cwd=repo_root / config.supabase_root,
                check=False,
                capture_output=True,
                timeout_seconds=dev.SUPABASE_STOP_TIMEOUT_SECONDS,
            )
            force_remove.assert_called_once_with(config)

    def test_run_supabase_stop_treats_unreachable_docker_as_already_stopped(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)
            (repo_root / config.supabase_root).mkdir(parents=True, exist_ok=True)

            with (
                mock.patch.object(dev, "ensure_migration_workspace_scaffolding"),
                mock.patch.object(dev, "ensure_docker_daemon_available", side_effect=dev.DevCliError("docker unavailable")),
                mock.patch.object(dev, "resolve_supabase_command_prefix", return_value=["npx", "supabase"]),
                mock.patch.object(dev, "run_command") as run_command,
            ):
                dev.run_supabase_stack_command(config, action="stop")

            run_command.assert_not_called()

    def test_run_supabase_start_removes_stale_conflicting_containers_and_retries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)
            supabase_root = repo_root / config.supabase_root
            supabase_root.mkdir(parents=True, exist_ok=True)
            (supabase_root / "config.toml").write_text('project_id = "board-enthusiasts-local"\n', encoding="utf-8")

            conflict = subprocess.CompletedProcess(
                args=["npx", "supabase", "start"],
                returncode=1,
                stdout="",
                stderr='failed to create docker container: Error response from daemon: Conflict. The container name "/supabase_vector_board-enthusiasts-local" is already in use',
            )
            success = subprocess.CompletedProcess(
                args=["npx", "supabase", "start"],
                returncode=0,
                stdout="Started supabase local development setup.",
                stderr="",
            )

            with (
                mock.patch.object(dev, "ensure_migration_workspace_scaffolding"),
                mock.patch.object(dev, "ensure_docker_daemon_available"),
                mock.patch.object(dev, "ensure_tcp_port_bindable"),
                mock.patch.object(dev, "resolve_supabase_command_prefix", return_value=["npx", "supabase"]),
                mock.patch.object(dev, "remove_stale_supabase_project_containers") as remove_stale,
                mock.patch.object(dev, "run_command", side_effect=[conflict, success]) as run_command,
                mock.patch.object(
                    dev,
                    "get_local_supabase_runtime",
                    return_value={
                        "SUPABASE_URL": "http://127.0.0.1:54321",
                        "SUPABASE_SECRET_KEY": "secret-key",
                    },
                ),
                mock.patch.object(dev, "wait_for_local_supabase_http_ready"),
            ):
                dev.run_supabase_stack_command(config, action="start")

            self.assertEqual(2, run_command.call_count)
            remove_stale.assert_called_once_with(config)

    def test_run_supabase_start_treats_already_starting_stack_as_success(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)
            supabase_root = repo_root / config.supabase_root
            supabase_root.mkdir(parents=True, exist_ok=True)

            already_starting = subprocess.CompletedProcess(
                args=["npx", "supabase", "start"],
                returncode=1,
                stdout="supabase start is already running.",
                stderr="supabase_db_board-enthusiasts-local container is not ready: starting",
            )

            with (
                mock.patch.object(dev, "ensure_migration_workspace_scaffolding"),
                mock.patch.object(dev, "ensure_docker_daemon_available"),
                mock.patch.object(dev, "ensure_tcp_port_bindable"),
                mock.patch.object(dev, "resolve_supabase_command_prefix", return_value=["npx", "supabase"]),
                mock.patch.object(dev, "run_command", return_value=already_starting) as run_command,
                mock.patch.object(
                    dev,
                    "get_local_supabase_runtime",
                    return_value={
                        "SUPABASE_URL": "http://127.0.0.1:54321",
                        "SUPABASE_SECRET_KEY": "secret-key",
                    },
                ),
                mock.patch.object(dev, "wait_for_local_supabase_http_ready") as wait_for_ready,
            ):
                dev.run_supabase_stack_command(config, action="start")

            run_command.assert_called_once()
            wait_for_ready.assert_called_once()

    def test_run_supabase_start_uses_maintained_web_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)
            supabase_root = repo_root / config.supabase_root
            supabase_root.mkdir(parents=True, exist_ok=True)

            success = subprocess.CompletedProcess(
                args=["npx", "supabase", "start"],
                returncode=0,
                stdout="Started supabase local development setup.",
                stderr="",
            )

            with (
                mock.patch.object(dev, "ensure_migration_workspace_scaffolding"),
                mock.patch.object(dev, "ensure_docker_daemon_available"),
                mock.patch.object(dev, "ensure_tcp_port_bindable"),
                mock.patch.object(dev, "resolve_supabase_command_prefix", return_value=["npx", "supabase"]),
                mock.patch.object(dev, "run_command", return_value=success) as run_command,
                mock.patch.object(
                    dev,
                    "get_local_supabase_runtime",
                    return_value={
                        "SUPABASE_URL": "http://127.0.0.1:54321",
                        "SUPABASE_SECRET_KEY": "secret-key",
                    },
                ),
                mock.patch.object(dev, "wait_for_local_supabase_http_ready"),
            ):
                dev.run_supabase_stack_command(config, action="start")

            run_command.assert_called_once_with(
                dev.build_supabase_profile_start_command(
                    prefix=["npx", "supabase"],
                    profile=dev.SUPABASE_PROFILE_WEB,
                ),
                cwd=supabase_root,
                check=False,
                capture_output=True,
                timeout_seconds=dev.SUPABASE_START_TIMEOUT_SECONDS,
            )

    def test_run_supabase_start_retries_when_docker_is_still_reconciling_containers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)
            supabase_root = repo_root / config.supabase_root
            supabase_root.mkdir(parents=True, exist_ok=True)

            transient_failure = subprocess.CompletedProcess(
                args=["npx", "supabase", "start"],
                returncode=1,
                stdout="",
                stderr=(
                    "Stopping containers...\n"
                    "failed to prune containers: Error response from daemon: a prune operation is already running\n"
                    "failed to start docker container: Error response from daemon: No such container: deadbeef"
                ),
            )
            success = subprocess.CompletedProcess(
                args=["npx", "supabase", "start"],
                returncode=0,
                stdout="Started supabase local development setup.",
                stderr="",
            )

            with (
                mock.patch.object(dev, "ensure_migration_workspace_scaffolding"),
                mock.patch.object(dev, "ensure_docker_daemon_available"),
                mock.patch.object(dev, "ensure_tcp_port_bindable"),
                mock.patch.object(dev, "resolve_supabase_command_prefix", return_value=["npx", "supabase"]),
                mock.patch.object(dev, "run_command", side_effect=[transient_failure, success]) as run_command,
                mock.patch.object(
                    dev,
                    "get_local_supabase_runtime",
                    return_value={
                        "SUPABASE_URL": "http://127.0.0.1:54321",
                        "SUPABASE_SECRET_KEY": "secret-key",
                    },
                ),
                mock.patch.object(dev, "wait_for_local_supabase_http_ready"),
            ):
                dev.run_supabase_stack_command(config, action="start")

            self.assertEqual(2, run_command.call_count)

    def test_run_supabase_start_validates_db_port_bindability_before_starting(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)
            supabase_root = repo_root / config.supabase_root
            supabase_root.mkdir(parents=True, exist_ok=True)

            with (
                mock.patch.object(dev, "ensure_migration_workspace_scaffolding"),
                mock.patch.object(dev, "ensure_docker_daemon_available"),
                mock.patch.object(
                    dev,
                    "ensure_tcp_port_bindable",
                    side_effect=dev.DevCliError("port is excluded"),
                ) as ensure_tcp_port_bindable,
                mock.patch.object(dev, "resolve_supabase_command_prefix", return_value=["npx", "supabase"]),
                mock.patch.object(dev, "run_command") as run_command,
            ):
                with self.assertRaises(dev.DevCliError) as raised:
                    dev.run_supabase_stack_command(config, action="start")

            ensure_tcp_port_bindable.assert_called_once_with(
                host="0.0.0.0",
                port=dev.LOCAL_SUPABASE_DB_PORT,
                description="local Supabase database",
            )
            run_command.assert_not_called()
            self.assertIn("port is excluded", str(raised.exception))

    def test_run_supabase_start_times_out_cleans_up_partial_runtime_and_raises_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)
            supabase_root = repo_root / config.supabase_root
            supabase_root.mkdir(parents=True, exist_ok=True)

            stop_success = subprocess.CompletedProcess(
                args=["npx", "supabase", "stop"],
                returncode=0,
                stdout="",
                stderr="",
            )

            def fake_run_command(*args, **kwargs):
                command = list(args[0])
                if command == dev.build_supabase_profile_start_command(
                    prefix=["npx", "supabase"],
                    profile=dev.SUPABASE_PROFILE_WEB,
                ):
                    raise subprocess.TimeoutExpired(
                        cmd=command,
                        timeout=dev.SUPABASE_START_TIMEOUT_SECONDS,
                    )
                if command == ["npx", "supabase", "stop"]:
                    return stop_success
                raise AssertionError(f"Unexpected command: {command}")

            with (
                mock.patch.object(dev, "ensure_migration_workspace_scaffolding"),
                mock.patch.object(dev, "ensure_docker_daemon_available"),
                mock.patch.object(dev, "ensure_tcp_port_bindable"),
                mock.patch.object(dev, "resolve_supabase_command_prefix", return_value=["npx", "supabase"]),
                mock.patch.object(dev, "run_command", side_effect=fake_run_command) as run_command,
            ):
                with self.assertRaises(dev.DevCliError) as raised:
                    dev.run_supabase_stack_command(config, action="start")

            run_command.assert_any_call(
                dev.build_supabase_profile_start_command(
                    prefix=["npx", "supabase"],
                    profile=dev.SUPABASE_PROFILE_WEB,
                ),
                cwd=supabase_root,
                check=False,
                capture_output=True,
                timeout_seconds=dev.SUPABASE_START_TIMEOUT_SECONDS,
            )
            run_command.assert_any_call(
                ["npx", "supabase", "stop"],
                cwd=supabase_root,
                check=False,
                capture_output=True,
                timeout_seconds=dev.SUPABASE_STOP_TIMEOUT_SECONDS,
            )
            self.assertIn("Supabase start timed out while launching the local runtime", str(raised.exception))
            self.assertIn("database down", str(raised.exception))

    def test_run_supabase_db_reset_retries_when_container_removal_is_still_in_progress(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)
            supabase_root = repo_root / config.supabase_root
            supabase_root.mkdir(parents=True, exist_ok=True)

            retryable_failure = subprocess.CompletedProcess(
                args=["npx", "supabase", "db", "reset", "--local"],
                returncode=1,
                stdout="",
                stderr=(
                    "Resetting local database...\n"
                    "failed to remove container: Error response from daemon: "
                    "removal of container supabase_db_board-enthusiasts-local is already in progress"
                ),
            )
            success = subprocess.CompletedProcess(
                args=["npx", "supabase", "db", "reset", "--local"],
                returncode=0,
                stdout="Reset complete.",
                stderr="",
            )
            start_success = subprocess.CompletedProcess(
                args=["npx", "supabase", "start"],
                returncode=0,
                stdout="Started supabase local development setup.",
                stderr="",
            )

            with (
                mock.patch.object(dev, "ensure_migration_workspace_scaffolding"),
                mock.patch.object(dev, "ensure_docker_daemon_available"),
                mock.patch.object(dev, "install_migration_workspace_dependencies"),
                mock.patch.object(dev, "resolve_supabase_command_prefix", return_value=["npx", "supabase"]),
                mock.patch.object(dev, "run_command", side_effect=[retryable_failure, start_success, success]) as run_command,
                mock.patch.object(dev, "seed_migration_data") as seed_migration_data,
                mock.patch.object(
                    dev,
                    "get_local_supabase_runtime",
                    return_value={
                        "SUPABASE_URL": "http://127.0.0.1:54321",
                        "SUPABASE_SECRET_KEY": "secret-key",
                    },
                ),
                mock.patch.object(dev, "wait_for_local_supabase_http_ready"),
            ):
                dev.run_supabase_stack_command(config, action="db-reset")

            self.assertEqual(3, run_command.call_count)
            seed_migration_data.assert_called_once_with(config, seed_password=dev.LOCAL_SEED_DEFAULT_PASSWORD)

    def test_run_supabase_db_reset_retries_when_migration_state_is_inconsistent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)
            supabase_root = repo_root / config.supabase_root
            supabase_root.mkdir(parents=True, exist_ok=True)

            migration_conflict = subprocess.CompletedProcess(
                args=["npx", "supabase", "db", "reset", "--local"],
                returncode=1,
                stdout="",
                stderr=(
                    "ERROR: duplicate key value violates unique constraint \"schema_migrations_pkey\" "
                    "(SQLSTATE 23505)"
                ),
            )
            success = subprocess.CompletedProcess(
                args=["npx", "supabase", "db", "reset", "--local"],
                returncode=0,
                stdout="Reset complete.",
                stderr="",
            )
            stop_success = subprocess.CompletedProcess(
                args=["npx", "supabase", "stop"],
                returncode=0,
                stdout="Stopped local Supabase services.",
                stderr="",
            )
            start_success = subprocess.CompletedProcess(
                args=["npx", "supabase", "start"],
                returncode=0,
                stdout="Started supabase local development setup.",
                stderr="",
            )

            with (
                mock.patch.object(dev, "ensure_migration_workspace_scaffolding"),
                mock.patch.object(dev, "ensure_docker_daemon_available"),
                mock.patch.object(dev, "install_migration_workspace_dependencies"),
                mock.patch.object(dev, "resolve_supabase_command_prefix", return_value=["npx", "supabase"]),
                mock.patch.object(
                    dev,
                    "run_command",
                    side_effect=[migration_conflict, stop_success, start_success, success],
                ) as run_command,
                mock.patch.object(dev, "seed_migration_data") as seed_migration_data,
                mock.patch.object(
                    dev,
                    "get_local_supabase_runtime",
                    return_value={
                        "SUPABASE_URL": "http://127.0.0.1:54321",
                        "SUPABASE_SECRET_KEY": "secret-key",
                    },
                ),
                mock.patch.object(dev, "wait_for_local_supabase_http_ready"),
            ):
                dev.run_supabase_stack_command(config, action="db-reset")

            self.assertEqual(4, run_command.call_count)
            seed_migration_data.assert_called_once_with(config, seed_password=dev.LOCAL_SEED_DEFAULT_PASSWORD)

    def test_run_supabase_db_reset_restarts_stack_when_seed_readiness_is_transient(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)
            supabase_root = repo_root / config.supabase_root
            supabase_root.mkdir(parents=True, exist_ok=True)

            success = subprocess.CompletedProcess(
                args=["npx", "supabase", "db", "reset", "--local"],
                returncode=0,
                stdout="Reset complete.",
                stderr="",
            )
            stop_success = subprocess.CompletedProcess(
                args=["npx", "supabase", "stop"],
                returncode=0,
                stdout="Stopped local Supabase services.",
                stderr="",
            )
            start_success = subprocess.CompletedProcess(
                args=["npx", "supabase", "start"],
                returncode=0,
                stdout="Started supabase local development setup.",
                stderr="",
            )
            transient_seed_error = dev.DevCliError(
                "Timed out waiting for local Supabase HTTP services to become ready.\n"
                "Last probe failures: Supabase Storage API: HTTP 502 Bad Gateway: "
                '{"message":"An invalid response was received from the upstream server"}'
            )

            with (
                mock.patch.object(dev, "ensure_migration_workspace_scaffolding"),
                mock.patch.object(dev, "ensure_docker_daemon_available"),
                mock.patch.object(dev, "install_migration_workspace_dependencies"),
                mock.patch.object(dev, "resolve_supabase_command_prefix", return_value=["npx", "supabase"]),
                mock.patch.object(
                    dev,
                    "run_command",
                    side_effect=[success, stop_success, start_success, success],
                ) as run_command,
                mock.patch.object(
                    dev,
                    "seed_migration_data",
                    side_effect=[transient_seed_error, None],
                ) as seed_migration_data,
                mock.patch.object(
                    dev,
                    "get_local_supabase_runtime",
                    return_value={
                        "SUPABASE_URL": "http://127.0.0.1:54321",
                        "SUPABASE_SECRET_KEY": "secret-key",
                    },
                ),
                mock.patch.object(dev, "wait_for_local_supabase_http_ready"),
            ):
                dev.run_supabase_stack_command(config, action="db-reset")

            self.assertEqual(4, run_command.call_count)
            self.assertEqual(2, seed_migration_data.call_count)

    def test_has_current_migration_workspace_dependencies_tracks_lockfile_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)

            (repo_root / "package.json").write_text('{"name":"board-enthusiasts"}', encoding="utf-8")
            (repo_root / "package-lock.json").write_text('{"lockfileVersion":3}', encoding="utf-8")
            (repo_root / "node_modules").mkdir()
            (repo_root / "node_modules" / "tsx").mkdir(parents=True)
            (repo_root / "node_modules" / "tsx" / "package.json").write_text("{}", encoding="utf-8")
            (repo_root / "node_modules" / "@supabase" / "supabase-js").mkdir(parents=True)
            (repo_root / "node_modules" / "@supabase" / "supabase-js" / "package.json").write_text("{}", encoding="utf-8")
            (repo_root / "node_modules" / "@playwright" / "test").mkdir(parents=True)
            (repo_root / "node_modules" / "@playwright" / "test" / "package.json").write_text("{}", encoding="utf-8")
            (repo_root / "node_modules" / "@board-enthusiasts" / "migration-contract").mkdir(parents=True)
            (repo_root / "node_modules" / "@board-enthusiasts" / "migration-contract" / "package.json").write_text("{}", encoding="utf-8")
            (repo_root / "node_modules" / "@board-enthusiasts" / "spa").mkdir(parents=True)
            (repo_root / "node_modules" / "@board-enthusiasts" / "spa" / "package.json").write_text("{}", encoding="utf-8")
            (repo_root / "node_modules" / "@board-enthusiasts" / "workers-api").mkdir(parents=True)
            (repo_root / "node_modules" / "@board-enthusiasts" / "workers-api" / "package.json").write_text("{}", encoding="utf-8")
            (repo_root / "node_modules" / ".bin").mkdir(parents=True)
            (repo_root / "node_modules" / ".bin" / "tsx.cmd").write_text("", encoding="utf-8")
            (repo_root / "node_modules" / ".bin" / "playwright.cmd").write_text("", encoding="utf-8")

            self.assertFalse(dev.has_current_migration_workspace_dependencies(config))

            dev.record_migration_workspace_dependencies(config)

            self.assertTrue(dev.has_current_migration_workspace_dependencies(config))

            (repo_root / "package-lock.json").write_text('{"lockfileVersion":4}', encoding="utf-8")

            self.assertFalse(dev.has_current_migration_workspace_dependencies(config))

    def test_api_test_parser_defaults_to_local_workers_base_url(self) -> None:
        parser = dev.build_parser()

        args = parser.parse_args(["api-test"])

        self.assertEqual("http://127.0.0.1:8787", args.base_url)
        self.assertFalse(args.start_workers)
        self.assertEqual(dev.LOCAL_SEED_DEVELOPER_EMAIL, args.developer_email)
        self.assertEqual(dev.LOCAL_SEED_MODERATOR_EMAIL, args.moderator_email)

    def test_database_and_web_parsers_default_to_up_actions(self) -> None:
        parser = dev.build_parser()

        database_args = parser.parse_args(["database"])
        web_args = parser.parse_args(["web", "--hot-reload"])

        self.assertEqual("up", database_args.action)
        self.assertEqual("up", web_args.action)
        self.assertTrue(web_args.hot_reload)
        self.assertFalse(web_args.landing_mode)

    def test_runtime_parsers_accept_clean_action(self) -> None:
        parser = dev.build_parser()

        database_args = parser.parse_args(["database", "clean"])
        auth_args = parser.parse_args(["auth", "clean"])
        api_args = parser.parse_args(["api", "clean"])
        web_args = parser.parse_args(["web", "clean"])
        clean_all_args = parser.parse_args(["clean-all"])

        self.assertEqual("clean", database_args.action)
        self.assertEqual("clean", auth_args.action)
        self.assertEqual("clean", api_args.action)
        self.assertEqual("clean", web_args.action)
        self.assertEqual("clean-all", clean_all_args.command)

    def test_web_parser_accepts_landing_mode_flag(self) -> None:
        parser = dev.build_parser()

        web_args = parser.parse_args(["web", "--landing-mode", "--no-browser"])

        self.assertEqual("up", web_args.action)
        self.assertTrue(web_args.landing_mode)
        self.assertTrue(web_args.no_browser)

    def test_deploy_parser_defaults_to_production(self) -> None:
        parser = dev.build_parser()

        deploy_args = parser.parse_args(["deploy"])

        self.assertFalse(deploy_args.staging)
        self.assertFalse(deploy_args.force)
        self.assertFalse(deploy_args.upgrade)
        self.assertFalse(deploy_args.preflight_only)
        self.assertFalse(deploy_args.dry_run_only)

    def test_deploy_parser_accepts_staging_and_resume_flags(self) -> None:
        parser = dev.build_parser()

        deploy_args = parser.parse_args(["deploy", "--staging", "--upgrade", "--preflight-only"])
        legacy_args = parser.parse_args(["deploy-staging", "--force", "--dry-run-only"])
        legacy_pages_args = parser.parse_args(["deploy-staging", "--dry-run", "--pages-only"])
        legacy_workers_args = parser.parse_args(["deploy-staging", "--dry-run", "--workers-only"])

        self.assertTrue(deploy_args.staging)
        self.assertTrue(deploy_args.upgrade)
        self.assertTrue(deploy_args.preflight_only)
        self.assertTrue(legacy_args.force)
        self.assertTrue(legacy_args.dry_run_only)
        self.assertTrue(legacy_pages_args.dry_run_only)
        self.assertTrue(legacy_pages_args.pages_only)
        self.assertTrue(legacy_workers_args.dry_run_only)
        self.assertTrue(legacy_workers_args.workers_only)

    def test_bootstrap_super_admin_parser_uses_secure_prompt_flow(self) -> None:
        parser = dev.build_parser()

        bootstrap_args = parser.parse_args(["bootstrap-super-admin"])

        self.assertEqual("production", bootstrap_args.target)
        self.assertIsNone(bootstrap_args.email)

        with self.assertRaises(SystemExit):
            parser.parse_args(["bootstrap-super-admin", "--password", "unsafe"])

    def test_run_legacy_staging_dry_run_pages_only_builds_spa(self) -> None:
        config = dev.config_from_args(self.create_args(), pathlib.Path.cwd())
        env_values = {
            "BOARD_ENTHUSIASTS_WORKERS_BASE_URL": "https://api.staging.boardenthusiasts.com",
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_PUBLISHABLE_KEY": "publishable",
            "VITE_TURNSTILE_SITE_KEY": "turnstile-site-key",
            "VITE_LANDING_MODE": "true",
        }
        optional_env_values = {
            "SUPABASE_AUTH_DISCORD_CLIENT_ID": "discord-client-id",
            "SUPABASE_AUTH_GITHUB_CLIENT_ID": "github-client-id",
        }
        expected_env_values = {**optional_env_values, **env_values}

        with mock.patch.object(
            dev,
            "require_environment_values",
            return_value=env_values,
        ), mock.patch.object(
            dev,
            "collect_present_environment_values",
            return_value=optional_env_values,
        ), mock.patch.object(
            dev,
            "build_workspace_npm_command",
            return_value=["npm", "run", "build", "--workspace", "@board-enthusiasts/spa"],
        ) as build_workspace_npm_command, mock.patch.object(
            dev,
            "build_deploy_frontend_environment",
            return_value={"VITE_API_BASE_URL": "https://api.staging.boardenthusiasts.com"},
        ) as build_deploy_frontend_environment, mock.patch.object(dev, "run_command") as run_command:
            dev.run_legacy_staging_dry_run(config, pages_only=True, workers_only=False)

        build_workspace_npm_command.assert_called_once_with(
            script_name="build",
            workspace_name=config.migration_spa_workspace_name,
        )
        build_deploy_frontend_environment.assert_called_once_with(expected_env_values)
        run_command.assert_called_once_with(
            ["npm", "run", "build", "--workspace", "@board-enthusiasts/spa"],
            cwd=config.repo_root,
            env={"VITE_API_BASE_URL": "https://api.staging.boardenthusiasts.com"},
        )

    def test_run_legacy_staging_dry_run_workers_only_dry_runs_worker(self) -> None:
        config = dev.config_from_args(self.create_args(), pathlib.Path.cwd())
        env_values = {
            "BOARD_ENTHUSIASTS_WORKERS_BASE_URL": "https://api.staging.boardenthusiasts.com",
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_PUBLISHABLE_KEY": "publishable",
            "SUPABASE_AVATARS_BUCKET": "avatars",
            "SUPABASE_CARD_IMAGES_BUCKET": "card-images",
            "SUPABASE_HERO_IMAGES_BUCKET": "hero-images",
            "SUPABASE_LOGO_IMAGES_BUCKET": "logo-images",
            "CLOUDFLARE_ACCOUNT_ID": "account-id",
            "CLOUDFLARE_API_TOKEN": "token",
            "BREVO_SIGNUPS_LIST_ID": "3",
            "ALLOWED_WEB_ORIGINS": "https://staging.boardenthusiasts.com",
            "SUPPORT_REPORT_RECIPIENT": "support@boardenthusiasts.com",
            "SUPPORT_REPORT_SENDER_EMAIL": "noreply@boardenthusiasts.com",
            "SUPPORT_REPORT_SENDER_NAME": "Board Enthusiasts",
        }
        optional_env_values = {
            "SUPABASE_AUTH_DISCORD_CLIENT_ID": "discord-client-id",
            "SUPABASE_AUTH_DISCORD_CLIENT_SECRET": "discord-client-secret",
            "SUPABASE_AUTH_GITHUB_CLIENT_ID": "github-client-id",
            "SUPABASE_AUTH_GITHUB_CLIENT_SECRET": "github-client-secret",
        }
        expected_env_values = {**optional_env_values, **env_values}

        with mock.patch.object(
            dev,
            "require_environment_values",
            return_value=env_values,
        ), mock.patch.object(
            dev,
            "collect_present_environment_values",
            return_value=optional_env_values,
        ), mock.patch.object(
            dev,
            "build_subprocess_env",
            return_value={"CLOUDFLARE_API_TOKEN": "token", "CLOUDFLARE_ACCOUNT_ID": "account-id"},
        ) as build_subprocess_env, mock.patch.object(
            dev,
            "get_deploy_worker_config_path",
            return_value=pathlib.Path("generated-wrangler.jsonc"),
        ) as get_deploy_worker_config_path, mock.patch.object(dev, "run_command") as run_command:
            dev.run_legacy_staging_dry_run(config, pages_only=False, workers_only=True)

        build_subprocess_env.assert_called_once()
        get_deploy_worker_config_path.assert_called_once_with(config, target="staging", env_values=expected_env_values)
        run_command.assert_called_once_with(
            ["npx", "wrangler", "deploy", "--dry-run", "--config", "generated-wrangler.jsonc"],
            cwd=config.repo_root,
            env={"CLOUDFLARE_API_TOKEN": "token", "CLOUDFLARE_ACCOUNT_ID": "account-id"},
        )

    def test_env_parser_accepts_github_environment_sync_flags(self) -> None:
        parser = dev.build_parser()

        env_args = parser.parse_args(
            [
                "env",
                "staging",
                "--sync-github-environment",
                "--github-environment",
                "staging-release",
                "--repo",
                "board-enthusiasts/board-enthusiasts",
            ]
        )

        self.assertEqual("staging", env_args.target)
        self.assertTrue(env_args.sync_github_environment)
        self.assertEqual("staging-release", env_args.github_environment)
        self.assertEqual("board-enthusiasts/board-enthusiasts", env_args.repo)

    def test_sync_root_environment_file_to_github_environment_sets_vars_and_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            config = dev.config_from_args(self.create_args(), repo_root)
            env_path = repo_root / config.staging_env_file
            env_path.parent.mkdir(parents=True, exist_ok=True)
            env_path.write_text(
                "\n".join(
                    [
                        "BOARD_ENTHUSIASTS_APP_ENV=staging",
                        "SUPABASE_PUBLISHABLE_KEY=publishable",
                        "SUPABASE_SECRET_KEY=secret",
                        "SUPABASE_URL=",
                        "BREVO_SIGNUPS_LIST_ID=3",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            run_calls: list[list[str]] = []

            def fake_run_command(cmd, **kwargs):
                run_calls.append(list(cmd))
                if cmd[:3] == ["gh", "auth", "status"]:
                    return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

            with (
                mock.patch.object(dev, "assert_command_available"),
                mock.patch.object(dev, "resolve_github_cli_executable", return_value="gh"),
                mock.patch.object(dev, "run_command", side_effect=fake_run_command),
            ):
                dev.sync_root_environment_file_to_github_environment(
                    config,
                    target="staging",
                    github_environment=None,
                    github_repo="board-enthusiasts/board-enthusiasts",
                )

        self.assertEqual(["gh", "auth", "status"], run_calls[0][:3])
        self.assertIn(
            [
                "gh",
                "variable",
                "set",
                "BOARD_ENTHUSIASTS_APP_ENV",
                "--env",
                "staging",
                "--body",
                "staging",
                "--repo",
                "board-enthusiasts/board-enthusiasts",
            ],
            run_calls,
        )
        self.assertIn(
            [
                "gh",
                "variable",
                "set",
                "SUPABASE_PUBLISHABLE_KEY",
                "--env",
                "staging",
                "--body",
                "publishable",
                "--repo",
                "board-enthusiasts/board-enthusiasts",
            ],
            run_calls,
        )
        self.assertIn(
            [
                "gh",
                "secret",
                "set",
                "SUPABASE_SECRET_KEY",
                "--env",
                "staging",
                "--repo",
                "board-enthusiasts/board-enthusiasts",
            ],
            run_calls,
        )
        flattened = [" ".join(call) for call in run_calls]
        self.assertFalse(any("SUPABASE_URL" in call for call in flattened))

    def test_sync_root_environment_file_to_github_environment_rejects_local_target(self) -> None:
        config = dev.config_from_args(self.create_args(), pathlib.Path.cwd())

        with self.assertRaises(dev.DevCliError) as raised:
            dev.sync_root_environment_file_to_github_environment(
                config,
                target="local",
                github_environment=None,
                github_repo=None,
            )

        self.assertIn("hosted targets", str(raised.exception))
        self.assertIn("not local", str(raised.exception))

    def test_sync_api_workspace_without_api_key_skips_shared_mock_reprovision(self) -> None:
        config = dev.config_from_args(self.create_args(), pathlib.Path.cwd())

        with (
            mock.patch.object(dev, "assert_command_available"),
            mock.patch.object(dev, "login_postman_cli") as login_postman_cli,
            mock.patch.object(dev, "run_command") as run_command,
            mock.patch.object(dev, "provision_api_mock") as provision_api_mock,
            mock.patch.dict(dev.os.environ, {}, clear=True),
        ):
            dev.sync_api_workspace(
                config,
                postman_api_key=None,
                reprovision_shared_mock=True,
            )

        login_postman_cli.assert_not_called()
        run_command.assert_has_calls(
            [
                mock.call(["postman", "workspace", "prepare"], cwd=mock.ANY),
                mock.call(["postman", "workspace", "push", "--yes"], cwd=mock.ANY),
            ]
        )
        provision_api_mock.assert_not_called()

    def test_infer_github_repo_from_origin_supports_https_remote(self) -> None:
        config = dev.config_from_args(self.create_args(), pathlib.Path.cwd())

        with mock.patch.object(
            dev,
            "run_command",
            return_value=subprocess.CompletedProcess(
                ["git", "config", "--get", "remote.origin.url"],
                0,
                stdout="https://github.com/board-enthusiasts/board-enthusiasts.git\n",
                stderr="",
            ),
        ):
            self.assertEqual("board-enthusiasts/board-enthusiasts", dev.infer_github_repo_from_origin(config))

    def test_assert_github_environment_sync_detects_var_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            config = dev.config_from_args(self.create_args(), repo_root)
            env_path = repo_root / config.staging_env_file
            env_path.parent.mkdir(parents=True, exist_ok=True)
            env_path.write_text(
                "\n".join(
                    [
                        "BOARD_ENTHUSIASTS_APP_ENV=staging",
                        "SUPABASE_PUBLISHABLE_KEY=publishable",
                        "SUPABASE_SECRET_KEY=secret",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            def fake_run_command(cmd, **kwargs):
                normalized = list(cmd)
                if normalized[:3] == ["gh", "auth", "status"]:
                    return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")
                if normalized[:2] == ["git", "config"]:
                    return subprocess.CompletedProcess(cmd, 0, stdout="https://github.com/board-enthusiasts/board-enthusiasts.git\n", stderr="")
                if normalized[:2] == ["gh", "api"]:
                    path = normalized[2]
                    if path.endswith("/environments/staging"):
                        return subprocess.CompletedProcess(cmd, 0, stdout='{"name":"staging"}', stderr="")
                    if path.endswith("/variables?per_page=100"):
                        return subprocess.CompletedProcess(
                            cmd,
                            0,
                            stdout=json.dumps({"variables": [{"name": "BOARD_ENTHUSIASTS_APP_ENV", "value": "staging"}]}),
                            stderr="",
                        )
                    if path.endswith("/secrets?per_page=100"):
                        return subprocess.CompletedProcess(
                            cmd,
                            0,
                            stdout=json.dumps({"secrets": [{"name": "SUPABASE_SECRET_KEY"}]}),
                            stderr="",
                        )
                raise AssertionError(f"Unexpected command: {normalized}")

            with (
                mock.patch.object(dev, "assert_command_available"),
                mock.patch.object(dev, "resolve_github_cli_executable", return_value="gh"),
                mock.patch.object(dev, "run_command", side_effect=fake_run_command),
                mock.patch.dict(dev.os.environ, {}, clear=True),
            ):
                with self.assertRaises(dev.DevCliError) as raised:
                    dev.assert_github_environment_sync(config, target="staging")

        self.assertIn("mismatched vars", str(raised.exception))

    def test_assert_github_environment_sync_skips_inside_github_actions(self) -> None:
        config = dev.config_from_args(self.create_args(), pathlib.Path.cwd())

        with (
            mock.patch.object(dev, "assert_command_available") as assert_command_available,
            mock.patch.object(dev, "run_command") as run_command,
            mock.patch.dict(dev.os.environ, {"GITHUB_ACTIONS": "true"}, clear=False),
        ):
            dev.assert_github_environment_sync(config, target="staging")

        assert_command_available.assert_not_called()
        run_command.assert_not_called()

    def test_status_and_down_parsers_accept_include_dependencies(self) -> None:
        parser = dev.build_parser()

        api_args = parser.parse_args(["api", "down", "--include-dependencies"])
        web_args = parser.parse_args(["web", "status", "--include-dependencies"])

        self.assertTrue(api_args.include_dependencies)
        self.assertTrue(web_args.include_dependencies)

    def test_main_web_down_without_dependencies_stops_only_web_service(self) -> None:
        with (
            mock.patch.object(dev, "stop_frontend_service") as stop_frontend_service,
            mock.patch.object(dev, "stop_backend_service") as stop_backend_service,
            mock.patch.object(dev, "stop_runtime_profile") as stop_runtime_profile,
            mock.patch.object(dev, "is_managed_service_running", return_value=True),
            mock.patch.object(dev, "save_runtime_profile_state") as save_runtime_profile_state,
        ):
            exit_code = dev.main(["web", "down"])

        self.assertEqual(0, exit_code)
        stop_frontend_service.assert_called_once()
        stop_backend_service.assert_not_called()
        stop_runtime_profile.assert_not_called()
        save_runtime_profile_state.assert_called_once_with(
            mock.ANY,
            profile=dev.SUPABASE_PROFILE_API,
        )

    def test_main_web_up_passes_landing_mode_to_full_stack_runner(self) -> None:
        with mock.patch.object(dev, "run_full_local_web_stack") as run_full_local_web_stack:
            exit_code = dev.main(["web", "--landing-mode", "--no-browser"])

        self.assertEqual(0, exit_code)
        run_full_local_web_stack.assert_called_once_with(
            mock.ANY,
            bootstrap=False,
            install_dependencies=True,
            hot_reload=False,
            landing_mode=True,
            open_browser_on_ready=False,
        )

    def test_main_web_down_with_dependencies_stops_full_stack(self) -> None:
        with (
            mock.patch.object(dev, "stop_frontend_service") as stop_frontend_service,
            mock.patch.object(dev, "stop_backend_service") as stop_backend_service,
            mock.patch.object(dev, "stop_runtime_profile") as stop_runtime_profile,
        ):
            exit_code = dev.main(["web", "down", "--include-dependencies"])

        self.assertEqual(0, exit_code)
        stop_frontend_service.assert_called_once()
        stop_backend_service.assert_called_once()
        stop_runtime_profile.assert_called_once()

    def test_main_api_down_without_dependencies_stops_api_and_keeps_auth_database(self) -> None:
        with (
            mock.patch.object(dev, "stop_frontend_service") as stop_frontend_service,
            mock.patch.object(dev, "stop_backend_service") as stop_backend_service,
            mock.patch.object(dev, "restart_runtime_profile") as restart_runtime_profile,
            mock.patch.object(dev, "stop_runtime_profile") as stop_runtime_profile,
        ):
            exit_code = dev.main(["api", "down"])

        self.assertEqual(0, exit_code)
        stop_frontend_service.assert_called_once()
        stop_backend_service.assert_called_once()
        restart_runtime_profile.assert_called_once_with(
            mock.ANY,
            profile=dev.SUPABASE_PROFILE_AUTH,
        )
        stop_runtime_profile.assert_not_called()

    def test_confirm_clean_action_cancels_without_confirmation_token(self) -> None:
        with mock.patch("builtins.input", return_value=""):
            confirmed = dev.confirm_clean_action(
                command_name="web",
                summary_lines=("root workspace installs",),
            )

        self.assertFalse(confirmed)

    def test_confirm_clean_action_accepts_uppercase_y(self) -> None:
        with mock.patch("builtins.input", return_value="Y"):
            confirmed = dev.confirm_clean_action(
                command_name="api",
                summary_lines=("backend-generated artifacts",),
            )

        self.assertTrue(confirmed)

    def test_database_clean_paths_target_only_expected_automation_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            config = dev.config_from_args(self.create_args(), repo_root)

            expected_paths = [
                repo_root / ".dev-cli-logs" / "runtime-profile-state.json",
                repo_root / ".dev-cli-logs" / "api-state.json",
                repo_root / ".dev-cli-logs" / "web-state.json",
                repo_root / ".dev-cli-logs" / "workers-api.log",
                repo_root / ".dev-cli-logs" / "migration-spa.log",
                repo_root / "backend" / "supabase" / ".branches",
                repo_root / "backend" / "supabase" / ".temp",
                repo_root / "supabase" / ".temp",
            ]
            for path in expected_paths:
                if path.name in {".branches", ".temp"}:
                    path.mkdir(parents=True, exist_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("generated", encoding="utf-8")

            protected_env_path = repo_root / "config" / ".env.local"
            protected_env_path.parent.mkdir(parents=True, exist_ok=True)
            protected_env_path.write_text("SECRET=value\n", encoding="utf-8")

            planned = dev.get_database_clean_paths(config)
            removed = dev.remove_paths(planned)

            self.assertEqual({str(path) for path in expected_paths}, {str(path) for path in removed})
            self.assertTrue(protected_env_path.exists())

    def test_main_web_clean_requires_confirmation_before_running_cleanup(self) -> None:
        with (
            mock.patch("builtins.input", return_value=""),
            mock.patch.object(dev, "clean_supabase_local_state") as clean_supabase_local_state,
            mock.patch.object(dev, "remove_paths") as remove_paths,
        ):
            exit_code = dev.main(["web", "clean"])

        self.assertEqual(0, exit_code)
        clean_supabase_local_state.assert_not_called()
        remove_paths.assert_not_called()

    def test_main_api_clean_runs_confirmed_cleanup(self) -> None:
        fake_removed_path = pathlib.Path("backend/apps/workers-api/.dev.vars")

        with (
            mock.patch("builtins.input", return_value="y"),
            mock.patch.object(dev, "clean_supabase_local_state") as clean_supabase_local_state,
            mock.patch.object(dev, "remove_paths", return_value=[fake_removed_path]) as remove_paths,
            mock.patch.object(dev, "summarize_removed_paths") as summarize_removed_paths,
        ):
            exit_code = dev.main(["api", "clean"])

        self.assertEqual(0, exit_code)
        clean_supabase_local_state.assert_called_once()
        remove_paths.assert_called_once()
        summarize_removed_paths.assert_called_once_with([fake_removed_path], repo_root=mock.ANY)

    def test_main_clean_all_runs_ordered_cleanups_after_single_confirmation(self) -> None:
        with (
            mock.patch("builtins.input", return_value="y"),
            mock.patch.object(dev, "get_desktop_clean_paths", return_value=[pathlib.Path("desktop")]),
            mock.patch.object(dev, "get_web_clean_paths", return_value=[pathlib.Path("web")]),
            mock.patch.object(dev, "get_api_clean_paths", return_value=[pathlib.Path("api")]),
            mock.patch.object(dev, "get_database_clean_paths", side_effect=[[pathlib.Path("auth")], [pathlib.Path("database")]]),
            mock.patch.object(dev, "perform_clean_operation") as perform_clean_operation,
        ):
            exit_code = dev.main(["clean-all"])

        self.assertEqual(0, exit_code)
        self.assertEqual(
            [
                mock.call(mock.ANY, command_name="desktop", paths=[pathlib.Path("desktop")]),
                mock.call(mock.ANY, command_name="web", paths=[pathlib.Path("web")]),
                mock.call(mock.ANY, command_name="api", paths=[pathlib.Path("api")]),
                mock.call(mock.ANY, command_name="auth", paths=[pathlib.Path("auth")]),
                mock.call(mock.ANY, command_name="database", paths=[pathlib.Path("database")]),
            ],
            perform_clean_operation.call_args_list,
        )

    def test_main_seed_data_uses_additive_seed_workflow_by_default(self) -> None:
        with (
            mock.patch.object(dev, "run_supabase_stack_command") as run_supabase_stack_command,
            mock.patch.object(dev, "seed_migration_data") as seed_migration_data,
        ):
            exit_code = dev.main(["seed-data"])

        self.assertEqual(0, exit_code)
        run_supabase_stack_command.assert_called_once_with(mock.ANY, action="start")
        seed_migration_data.assert_called_once_with(
            mock.ANY,
            seed_password=dev.LOCAL_SEED_DEFAULT_PASSWORD,
            additive=True,
        )

    def test_main_seed_data_reset_workflow_reseeds_with_requested_password(self) -> None:
        with mock.patch.object(dev, "run_supabase_stack_command") as run_supabase_stack_command:
            exit_code = dev.main(["seed-data", "--reset", "--seed-password", "CustomSeed!234"])

        self.assertEqual(0, exit_code)
        self.assertEqual(
            [
                mock.call(mock.ANY, action="start"),
                mock.call(mock.ANY, action="db-reset", seed_password="CustomSeed!234"),
            ],
            run_supabase_stack_command.call_args_list,
        )

    def test_seed_migration_data_passes_additive_flag_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            config = dev.config_from_args(self.create_args(), repo_root)
            asset_root = repo_root / "frontend" / "public" / "seed-catalog"
            asset_root.mkdir(parents=True, exist_ok=True)

            runtime_env = {
                "SUPABASE_URL": "http://127.0.0.1:54321",
                "SUPABASE_SECRET_KEY": "service-role-key",
                "SUPABASE_AVATARS_BUCKET": "avatars",
                "SUPABASE_CARD_IMAGES_BUCKET": "card-images",
                "SUPABASE_HERO_IMAGES_BUCKET": "hero-images",
                "SUPABASE_LOGO_IMAGES_BUCKET": "logo-images",
            }

            with (
                mock.patch.object(dev, "assert_command_available"),
                mock.patch.object(dev, "ensure_migration_workspace_scaffolding"),
                mock.patch.object(dev, "install_migration_workspace_dependencies"),
                mock.patch.object(dev, "get_local_supabase_runtime", return_value=runtime_env),
                mock.patch.object(dev, "wait_for_local_supabase_http_ready"),
                mock.patch.object(dev, "run_command") as run_command,
            ):
                dev.seed_migration_data(config, seed_password="SeedPassword!123", additive=True)

            run_command.assert_called_once_with(
                [
                    "npm",
                    "run",
                    "seed:migration",
                    "--",
                    "--additive",
                    "--supabase-url",
                    "http://127.0.0.1:54321",
                    "--secret-key",
                    "service-role-key",
                    "--password",
                    "SeedPassword!123",
                    "--asset-root",
                    str(asset_root.resolve()),
                    "--avatars-bucket",
                    "avatars",
                    "--card-images-bucket",
                    "card-images",
                    "--hero-images-bucket",
                    "hero-images",
                    "--logo-images-bucket",
                    "logo-images",
                ],
                cwd=config.repo_root,
            )

    def test_run_api_contract_tests_starts_workers_and_injects_seeded_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            api_root = repo_root / "api"
            collection_path = api_root / "postman" / "collections" / "board-enthusiasts-api.contract-tests.postman_collection.json"
            environment_path = api_root / "postman" / "environments" / "board-enthusiasts_local.postman_environment.json"
            collection_path.parent.mkdir(parents=True, exist_ok=True)
            environment_path.parent.mkdir(parents=True, exist_ok=True)
            collection_path.write_text("{}", encoding="utf-8")
            environment_path.write_text("{}", encoding="utf-8")

            args = self.create_args()
            config = dev.config_from_args(args, repo_root)

            with (
                mock.patch.object(dev, "assert_command_available"),
                mock.patch.object(dev, "run_api_spec_lint"),
                mock.patch.object(dev, "run_supabase_stack_command") as run_supabase_stack_command,
                mock.patch.object(
                    dev,
                    "get_local_supabase_runtime",
                    return_value={
                        "SUPABASE_URL": "http://127.0.0.1:54321",
                        "SUPABASE_PUBLISHABLE_KEY": "publishable-key",
                    },
                ),
                mock.patch.object(
                    dev,
                    "start_migration_workers_process",
                    return_value=(mock.Mock(spec=[]), repo_root / ".dev-cli-logs" / "workers-api.log"),
                ) as start_workers_process,
                mock.patch.object(
                    dev,
                    "fetch_supabase_access_token",
                    side_effect=["developer-token", "moderator-token"],
                ) as fetch_token,
                mock.patch.object(dev, "run_command") as run_command,
                mock.patch.object(dev, "stop_background_process") as stop_background_process,
            ):
                dev.run_api_contract_tests(
                    config,
                    environment_path=environment_path,
                    base_url=config.migration_workers_base_url,
                    contract_execution_mode="live",
                    report_path=repo_root / "api" / "postman-cli-reports" / "contract-tests.xml",
                    lint_spec=False,
                    start_workers=True,
                    developer_token=None,
                    moderator_token=None,
                    developer_email=dev.LOCAL_SEED_DEVELOPER_EMAIL,
                    moderator_email=dev.LOCAL_SEED_MODERATOR_EMAIL,
                    seed_user_password=dev.LOCAL_SEED_DEFAULT_PASSWORD,
                )

            self.assertEqual(
                [
                    mock.call(config, action="start"),
                    mock.call(config, action="db-reset"),
                ],
                run_supabase_stack_command.call_args_list,
            )
            start_workers_process.assert_called_once()
            self.assertEqual(2, fetch_token.call_count)
            run_command.assert_called_once()
            invoked_command = run_command.call_args.args[0]
            self.assertIn("developerAccessToken=developer-token", invoked_command)
            self.assertIn("moderatorAccessToken=moderator-token", invoked_command)
            self.assertIn(f"baseUrl={config.migration_workers_base_url}", invoked_command)
            stop_background_process.assert_called_once()

    def test_parity_commands_no_longer_accept_start_stack(self) -> None:
        parser = dev.build_parser()

        with self.assertRaises(SystemExit):
            parser.parse_args(["parity-test", "--start-stack"])

        with self.assertRaises(SystemExit):
            parser.parse_args(["capture-parity-baseline", "--start-stack"])

    def test_run_parity_suite_ensures_local_web_stack_before_running(self) -> None:
        config = dev.config_from_args(self.create_args(), pathlib.Path.cwd())

        with (
            mock.patch.object(dev, "assert_command_available"),
            mock.patch.object(dev, "ensure_migration_workspace_scaffolding"),
            mock.patch.object(dev, "install_migration_workspace_dependencies"),
            mock.patch.object(dev, "ensure_playwright_browser_installed"),
            mock.patch.object(
                dev,
                "ensure_local_web_stack_for_parity",
                return_value=dev.ParityStackStartupResult(started_frontend=True),
            ) as ensure_local_web_stack_for_parity,
            mock.patch.object(dev, "build_subprocess_env", return_value={"PARITY_BASE_URL": config.frontend_base_url}),
            mock.patch.object(dev, "run_command") as run_command,
            mock.patch.object(dev, "cleanup_local_web_stack_after_parity") as cleanup_local_web_stack_after_parity,
        ):
            dev.run_parity_suite(config, update_snapshots=False)

        ensure_local_web_stack_for_parity.assert_called_once_with(config)
        run_command.assert_called_once()
        cleanup_local_web_stack_after_parity.assert_called_once_with(
            config,
            startup_result=dev.ParityStackStartupResult(started_frontend=True),
        )

    def test_ensure_local_web_stack_for_parity_starts_missing_services(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            config = dev.config_from_args(self.create_args(), repo_root)
            backend_process = mock.Mock(pid=321)
            frontend_process = mock.Mock(pid=654)

            with (
                mock.patch.object(
                    dev,
                    "probe_http_url",
                    side_effect=[
                        (False, "connection refused"),
                        (False, "backend missing"),
                        (False, "frontend missing"),
                        (True, None),
                    ],
                ),
                mock.patch.object(dev, "ensure_runtime_profile") as ensure_runtime_profile,
                mock.patch.object(
                    dev,
                    "get_local_supabase_runtime",
                    side_effect=[
                        dev.DevCliError("local runtime unavailable"),
                        {
                            "SUPABASE_URL": "http://127.0.0.1:54321",
                            "SUPABASE_PUBLISHABLE_KEY": "publishable",
                            "SUPABASE_SECRET_KEY": "secret",
                            "SUPABASE_AVATARS_BUCKET": "avatars",
                            "SUPABASE_CARD_IMAGES_BUCKET": "card-images",
                            "SUPABASE_HERO_IMAGES_BUCKET": "hero-images",
                            "SUPABASE_LOGO_IMAGES_BUCKET": "logo-images",
                        },
                    ],
                ),
                mock.patch.object(dev, "wait_for_local_supabase_http_ready"),
                mock.patch.object(dev, "ensure_local_demo_seed_data"),
                mock.patch.object(
                    dev,
                    "start_migration_workers_process",
                    return_value=(backend_process, repo_root / ".dev-cli-logs" / "workers-api.log"),
                ) as start_migration_workers_process,
                mock.patch.object(
                    dev,
                    "start_background_command_with_log",
                    return_value=(frontend_process, repo_root / ".dev-cli-logs" / "migration-spa.log"),
                ) as start_background_command_with_log,
                mock.patch.object(dev, "wait_for_background_process_http_ready") as wait_for_background_process_http_ready,
                mock.patch.object(dev, "save_stack_state") as save_stack_state,
            ):
                startup_result = dev.ensure_local_web_stack_for_parity(config)

        self.assertEqual(
            dev.ParityStackStartupResult(
                started_runtime=True,
                started_backend=True,
                started_frontend=True,
            ),
            startup_result,
        )
        ensure_runtime_profile.assert_called_once_with(config, profile=dev.SUPABASE_PROFILE_WEB)
        start_migration_workers_process.assert_called_once()
        start_background_command_with_log.assert_called_once()
        self.assertEqual(2, save_stack_state.call_count)
        wait_for_background_process_http_ready.assert_called_once()

    def test_cleanup_local_web_stack_after_parity_stops_only_started_services(self) -> None:
        config = dev.config_from_args(self.create_args(), pathlib.Path.cwd())

        with (
            mock.patch.object(dev, "stop_frontend_service") as stop_frontend_service,
            mock.patch.object(dev, "stop_backend_service") as stop_backend_service,
            mock.patch.object(dev, "stop_runtime_profile") as stop_runtime_profile,
        ):
            dev.cleanup_local_web_stack_after_parity(
                config,
                startup_result=dev.ParityStackStartupResult(
                    started_runtime=False,
                    started_backend=True,
                    started_frontend=True,
                ),
            )

        stop_frontend_service.assert_called_once_with(config)
        stop_backend_service.assert_called_once_with(config)
        stop_runtime_profile.assert_not_called()

    def test_cleanup_local_web_stack_after_parity_stops_runtime_when_parity_started_it(self) -> None:
        config = dev.config_from_args(self.create_args(), pathlib.Path.cwd())

        with (
            mock.patch.object(dev, "stop_frontend_service") as stop_frontend_service,
            mock.patch.object(dev, "stop_backend_service") as stop_backend_service,
            mock.patch.object(dev, "stop_runtime_profile") as stop_runtime_profile,
        ):
            dev.cleanup_local_web_stack_after_parity(
                config,
                startup_result=dev.ParityStackStartupResult(started_runtime=True),
            )

        stop_runtime_profile.assert_called_once_with(config)
        stop_frontend_service.assert_not_called()
        stop_backend_service.assert_not_called()

    def test_run_supabase_hosted_demo_seeding_runs_additive_seed_for_staging(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            config = dev.config_from_args(self.create_args(), repo_root)
            asset_root = repo_root / "frontend" / "public" / "seed-catalog"
            asset_root.mkdir(parents=True, exist_ok=True)

            env_values = {
                "SUPABASE_URL": "https://example.supabase.co",
                "SUPABASE_SECRET_KEY": "service-role-key",
                "DEPLOY_SMOKE_USER_PASSWORD": "SeedPassword!123",
                "SUPABASE_AVATARS_BUCKET": "avatars",
                "SUPABASE_CARD_IMAGES_BUCKET": "card-images",
                "SUPABASE_HERO_IMAGES_BUCKET": "hero-images",
                "SUPABASE_LOGO_IMAGES_BUCKET": "logo-images",
            }

            with mock.patch.object(dev, "run_command") as run_command:
                dev.run_supabase_hosted_demo_seeding(
                    config,
                    target="staging",
                    env_values=env_values,
                    subprocess_env={"PATH": os.environ.get("PATH", "")},
                )

            run_command.assert_called_once_with(
                [
                    "npm",
                    "run",
                    "seed:migration",
                    "--",
                    "--additive",
                    "--supabase-url",
                    "https://example.supabase.co",
                    "--secret-key",
                    "service-role-key",
                    "--password",
                    "SeedPassword!123",
                    "--asset-root",
                    str(asset_root.resolve()),
                    "--avatars-bucket",
                    "avatars",
                    "--card-images-bucket",
                    "card-images",
                    "--hero-images-bucket",
                    "hero-images",
                    "--logo-images-bucket",
                    "logo-images",
                ],
                cwd=repo_root,
                env=mock.ANY,
            )

    def test_run_supabase_hosted_demo_seeding_skips_production(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            config = dev.config_from_args(self.create_args(), repo_root)

            with mock.patch.object(dev, "run_command") as run_command:
                dev.run_supabase_hosted_demo_seeding(
                    config,
                    target="production",
                    env_values={
                        "SUPABASE_URL": "https://example.supabase.co",
                        "SUPABASE_SECRET_KEY": "service-role-key",
                        "DEPLOY_SMOKE_USER_PASSWORD": "SeedPassword!123",
                        "SUPABASE_AVATARS_BUCKET": "avatars",
                        "SUPABASE_CARD_IMAGES_BUCKET": "card-images",
                        "SUPABASE_HERO_IMAGES_BUCKET": "hero-images",
                        "SUPABASE_LOGO_IMAGES_BUCKET": "logo-images",
                    },
                    subprocess_env={},
                )

            run_command.assert_not_called()

    def test_removed_legacy_runtime_commands_are_rejected(self) -> None:
        parser = dev.build_parser()

        for command in (
            ["up"],
            ["down"],
            ["status"],
            ["frontend"],
            ["web-status"],
            ["web-stop"],
            ["spa", "run"],
            ["workers", "run"],
            ["supabase", "start"],
        ):
            with self.assertRaises(SystemExit):
                parser.parse_args(command)

    def test_api_lint_tolerates_known_redocly_windows_shutdown_assertion_after_success(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            args = self.create_args()
            config = dev.config_from_args(args, repo_root)
            spec_path = repo_root / config.api_spec
            spec_path.parent.mkdir(parents=True, exist_ok=True)
            spec_path.write_text("openapi: 3.1.0\ninfo:\n  title: Test\n  version: 1.0.0\npaths: {}\n", encoding="utf-8")

            result = subprocess.CompletedProcess(
                args=["npx", "@redocly/cli", "lint", str(spec_path)],
                returncode=1,
                stdout="Woohoo! Your API description is valid. 🎉",
                stderr="Assertion failed: !(handle->flags & UV_HANDLE_CLOSING), file src\\win\\async.c, line 76",
            )

            with (
                mock.patch.object(dev, "assert_command_available"),
                mock.patch.object(dev, "run_command", return_value=result) as run_command,
            ):
                dev.run_api_spec_lint(config)

            self.assertTrue(run_command.called)


class DevCliDesktopWorkflowTests(unittest.TestCase):
    """Covers the desktop-specific root CLI workflow helpers."""

    @staticmethod
    def create_args() -> argparse.Namespace:
        """Create a minimal argument namespace for config construction."""

        return argparse.Namespace()

    def test_config_from_args_includes_desktop_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)

            config = dev.config_from_args(self.create_args(), repo_root)

            self.assertEqual("be-home-for-desktop", config.desktop_root)
            self.assertEqual("be-home-for-desktop/Packages/manifest.json", config.desktop_package_json)
            self.assertEqual("http://127.0.0.1:1420", config.desktop_base_url)

    def test_apply_runtime_base_url_overrides_respects_local_desktop_port_env(self) -> None:
        config = dev.config_from_args(self.create_args(), pathlib.Path.cwd())

        with mock.patch.dict(
            dev.os.environ,
            {"BOARD_ENTHUSIASTS_LOCAL_DESKTOP_PORT": "51420"},
            clear=False,
        ):
            overridden = dev.apply_runtime_base_url_overrides(config)

        self.assertEqual("http://127.0.0.1:51420", overridden.desktop_base_url)

    def test_desktop_parser_defaults_to_up_and_accepts_local_only(self) -> None:
        parser = dev.build_parser()

        desktop_args = parser.parse_args(["desktop", "--local-only", "--skip-install"])

        self.assertEqual("desktop", desktop_args.command)
        self.assertEqual("up", desktop_args.action)
        self.assertTrue(desktop_args.local_only)
        self.assertTrue(desktop_args.skip_install)

    def test_desktop_parser_accepts_app_state_only_clean(self) -> None:
        parser = dev.build_parser()

        desktop_args = parser.parse_args(["desktop", "clean", "--app-state-only"])

        self.assertEqual("desktop", desktop_args.command)
        self.assertEqual("clean", desktop_args.action)
        self.assertTrue(desktop_args.app_state_only)

    def test_desktop_parser_accepts_unity_test_and_build_actions(self) -> None:
        parser = dev.build_parser()

        test_args = parser.parse_args(["desktop", "test", "--skip-install"])
        build_args = parser.parse_args(["desktop", "build"])

        self.assertEqual("test", test_args.action)
        self.assertTrue(test_args.skip_install)
        self.assertEqual("build", build_args.action)

    def test_main_desktop_up_passes_flags_to_desktop_stack_runner(self) -> None:
        with mock.patch.object(dev, "run_local_desktop_stack") as run_local_desktop_stack:
            exit_code = dev.main(["desktop", "--local-only", "--skip-install"])

        self.assertEqual(0, exit_code)
        run_local_desktop_stack.assert_called_once_with(
            mock.ANY,
            bootstrap=False,
            install_dependencies=False,
            local_only=True,
        )

    def test_main_desktop_clean_passes_app_state_only_flag_to_handler(self) -> None:
        with mock.patch.object(dev, "handle_desktop_clean") as handle_desktop_clean:
            exit_code = dev.main(["desktop", "clean", "--app-state-only"])

        self.assertEqual(0, exit_code)
        handle_desktop_clean.assert_called_once_with(mock.ANY, app_state_only=True)

    def test_main_desktop_test_passes_restore_flag_to_unity_tests(self) -> None:
        with mock.patch.object(dev, "run_desktop_tests") as run_desktop_tests:
            exit_code = dev.main(["desktop", "test", "--skip-install"])

        self.assertEqual(0, exit_code)
        run_desktop_tests.assert_called_once_with(mock.ANY, restore=False)

    def test_main_desktop_build_passes_restore_flag_to_unity_build(self) -> None:
        with mock.patch.object(dev, "run_desktop_build") as run_desktop_build:
            exit_code = dev.main(["desktop", "build", "--skip-install"])

        self.assertEqual(0, exit_code)
        run_desktop_build.assert_called_once_with(mock.ANY, restore=False)

    def test_main_desktop_down_without_dependencies_stops_only_desktop_service(self) -> None:
        with (
            mock.patch.object(dev, "stop_desktop_service") as stop_desktop_service,
            mock.patch.object(dev, "stop_backend_service") as stop_backend_service,
            mock.patch.object(dev, "stop_runtime_profile") as stop_runtime_profile,
            mock.patch.object(dev, "is_managed_service_running", return_value=True),
            mock.patch.object(dev, "save_runtime_profile_state") as save_runtime_profile_state,
        ):
            exit_code = dev.main(["desktop", "down"])

        self.assertEqual(0, exit_code)
        stop_desktop_service.assert_called_once()
        stop_backend_service.assert_not_called()
        stop_runtime_profile.assert_not_called()
        save_runtime_profile_state.assert_called_once_with(
            mock.ANY,
            profile=dev.SUPABASE_PROFILE_API,
        )

    def test_get_desktop_clean_paths_includes_unity_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = pathlib.Path(temp_dir)
            config = dev.config_from_args(self.create_args(), repo_root)

            paths = dev.get_desktop_clean_paths(config)

        expected = {
            repo_root / ".dev-cli-logs" / "be-home-for-desktop.log",
            repo_root / ".dev-cli-logs" / "unity-desktop-editmode-results.xml",
            repo_root / ".dev-cli-logs" / "unity-desktop-playmode-results.xml",
            repo_root / "be-home-for-desktop" / "Library",
            repo_root / "be-home-for-desktop" / "Temp",
            repo_root / "be-home-for-desktop" / "Build",
        }
        self.assertTrue(expected.issubset(set(paths)))

    def test_validate_unity_uss_properties_rejects_unsupported_property(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            uss_path = pathlib.Path(temp_dir) / "bad.uss"
            uss_path.write_text(".bad { gap: 8px; }\n", encoding="utf-8")

            with self.assertRaises(dev.DevCliError):
                dev.validate_unity_uss_properties([uss_path])

    def test_build_unity_editor_command_uses_resolved_editor_path(self) -> None:
        with mock.patch.object(dev, "resolve_unity_editor_path", return_value=pathlib.Path("Unity.exe")):
            command = dev.build_unity_editor_command(
                batchmode=True,
                project_path=pathlib.Path("be-home-for-desktop"),
                extra_args=["-quit"],
            )

        self.assertEqual(["Unity.exe", "-batchmode", "-projectPath", "be-home-for-desktop", "-quit"], command)

    def test_resolve_desktop_app_state_root_uses_windows_local_app_data_case_insensitively(self) -> None:
        root = dev.resolve_desktop_app_state_root(
            environment={"LocalAppData": r"C:\Users\matt\AppData\Local"},
            platform_name="windows",
        )

        self.assertEqual(
            pathlib.Path(r"C:\Users\matt\AppData\Local")
            / "Board Enthusiasts"
            / "BE Home for Desktop",
            root,
        )

    def test_handle_desktop_clean_app_state_only_skips_api_cleanup(self) -> None:
        config = dev.config_from_args(self.create_args(), pathlib.Path.cwd())
        app_state_path = pathlib.Path("desktop-app-state")

        with (
            mock.patch.object(dev, "confirm_clean_action", return_value=True) as confirm_clean_action,
            mock.patch.object(dev, "stop_desktop_service") as stop_desktop_service,
            mock.patch.object(dev, "get_desktop_app_state_clean_paths", return_value=[app_state_path]) as get_desktop_app_state_clean_paths,
            mock.patch.object(dev, "remove_paths", return_value=[app_state_path]) as remove_paths,
            mock.patch.object(dev, "summarize_removed_paths") as summarize_removed_paths,
            mock.patch.object(dev, "clean_supabase_local_state") as clean_supabase_local_state,
        ):
            dev.handle_desktop_clean(config, app_state_only=True)

        confirm_clean_action.assert_called_once()
        self.assertEqual(
            "desktop clean --app-state-only",
            confirm_clean_action.call_args.kwargs["command_name"],
        )
        stop_desktop_service.assert_called_once_with(config)
        get_desktop_app_state_clean_paths.assert_called_once_with(config)
        remove_paths.assert_called_once_with([app_state_path])
        summarize_removed_paths.assert_called_once_with([app_state_path], repo_root=config.repo_root)
        clean_supabase_local_state.assert_not_called()

    def test_run_all_tests_includes_desktop_validation(self) -> None:
        config = dev.config_from_args(self.create_args(), pathlib.Path.cwd())

        with (
            mock.patch.object(dev, "restore_backend") as restore_backend,
            mock.patch.object(dev, "run_migration_typecheck") as run_migration_typecheck,
            mock.patch.object(dev, "run_tests") as run_tests,
            mock.patch.object(dev, "run_root_python_tests") as run_root_python_tests,
            mock.patch.object(dev, "restore_frontend") as restore_frontend,
            mock.patch.object(dev, "run_frontend_tests") as run_frontend_tests,
            mock.patch.object(dev, "restore_desktop_workspace") as restore_desktop_workspace,
            mock.patch.object(dev, "run_desktop_tests") as run_desktop_tests,
            mock.patch.object(dev, "run_api_spec_lint") as run_api_spec_lint,
            mock.patch.object(dev, "run_api_contract_tests") as run_api_contract_tests,
            mock.patch.object(dev, "run_contract_smoke") as run_contract_smoke,
            mock.patch.object(dev, "run_workers_flow_smoke_command") as run_workers_flow_smoke_command,
        ):
            dev.run_all_tests(
                config,
                bootstrap=False,
                environment_path=pathlib.Path("environment.json"),
                base_url="http://127.0.0.1:8787",
                contract_execution_mode="live",
                report_path=pathlib.Path("report.xml"),
                start_workers=False,
            )

        restore_backend.assert_called_once_with(config)
        restore_frontend.assert_called_once_with(config)
        restore_desktop_workspace.assert_called_once_with(config)
        run_frontend_tests.assert_called_once_with(config, restore=False)
        run_desktop_tests.assert_called_once_with(config, restore=False)
        self.assertTrue(run_api_spec_lint.called)
        self.assertTrue(run_api_contract_tests.called)
        self.assertTrue(run_contract_smoke.called)
        self.assertTrue(run_workers_flow_smoke_command.called)


if __name__ == "__main__":
    unittest.main()
