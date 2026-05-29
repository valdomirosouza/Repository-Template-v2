"""Unit tests for SandboxExecutor.

Spec: specs/ai/sandbox-execution.md
ADR:  ADR-0016 (Agent Sandbox Execution Policy)
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.sandbox_executor import (
    SandboxExecutor,
    SandboxPolicyError,
    SandboxResult,
    _get_sandbox_mode_variant,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_executor(**kwargs) -> SandboxExecutor:
    return SandboxExecutor(
        docker_image="python:3.13-slim",
        timeout_seconds=5.0,
        **kwargs,
    )


def _make_proc(stdout: bytes = b"", stderr: bytes = b"", returncode: int = 0):
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.kill = MagicMock()
    return proc


# ── SandboxResult ────────────────────────────────────────────────────────────


class TestSandboxResult:
    def test_succeeded_true_on_zero_exit(self):
        r = SandboxResult(
            exit_code=0, stdout="ok", stderr="", timed_out=False, duration_seconds=0.1
        )
        assert r.succeeded is True

    def test_succeeded_false_on_nonzero_exit(self):
        r = SandboxResult(
            exit_code=1, stdout="", stderr="err", timed_out=False, duration_seconds=0.1
        )
        assert r.succeeded is False

    def test_succeeded_false_when_timed_out(self):
        r = SandboxResult(exit_code=0, stdout="", stderr="", timed_out=True, duration_seconds=5.0)
        assert r.succeeded is False


# ── Command validation ────────────────────────────────────────────────────────


class TestCommandValidation:
    def test_rejects_semicolon(self):
        ex = _make_executor()
        with pytest.raises(SandboxPolicyError, match="metacharacter"):
            ex._validate_command(["sh", "-c", "echo hello; rm -rf /"])

    def test_rejects_ampersand_chain(self):
        ex = _make_executor()
        with pytest.raises(SandboxPolicyError, match="metacharacter"):
            ex._validate_command(["bash", "-c", "cmd && malicious"])

    def test_rejects_subshell(self):
        ex = _make_executor()
        with pytest.raises(SandboxPolicyError, match="metacharacter"):
            ex._validate_command(["echo", "$HOME"])

    def test_accepts_safe_command(self):
        ex = _make_executor()
        ex._validate_command(
            ["python", "-c", "print('hello')"]
        )  # parens are NOT shell metacharacters in argv-mode

    def test_accepts_python_script(self):
        ex = _make_executor()
        ex._validate_command(["python", "script.py", "--flag", "value"])


# ── Policy enforcement ────────────────────────────────────────────────────────


class TestPolicyEnforcement:
    def test_disabled_allowed_in_development(self):
        ex = _make_executor()
        with patch(
            "src.agents.sandbox_executor._get_sandbox_mode_variant", return_value="disabled"
        ):
            with patch("src.agents.sandbox_executor.settings") as mock_settings:
                mock_settings.app_env = "development"
                ex._enforce_policy(risk_score=0.1)  # must not raise

    def test_disabled_raises_in_production(self):
        ex = _make_executor()
        with patch(
            "src.agents.sandbox_executor._get_sandbox_mode_variant", return_value="disabled"
        ):
            with patch("src.agents.sandbox_executor.settings") as mock_settings:
                mock_settings.app_env = "production"
                with pytest.raises(SandboxPolicyError, match="not 'development'"):
                    ex._enforce_policy(risk_score=0.1)

    def test_enabled_does_not_raise(self):
        ex = _make_executor()
        with patch("src.agents.sandbox_executor._get_sandbox_mode_variant", return_value="enabled"):
            ex._enforce_policy(risk_score=0.9)  # no exception

    def test_hitl_required_logs_warning_below_threshold(self, caplog):
        ex = _make_executor()
        with patch(
            "src.agents.sandbox_executor._get_sandbox_mode_variant", return_value="hitl-required"
        ):
            with patch("src.agents.sandbox_executor.settings") as mock_settings:
                mock_settings.hitl_risk_threshold = 0.4
                ex._enforce_policy(risk_score=0.1)  # below threshold → warning, no raise


# ── Docker command builder ────────────────────────────────────────────────────


class TestBuildDockerCommand:
    def test_network_none_present(self):
        ex = _make_executor()
        cmd = ex._build_docker_command(["python", "-c", "print(1)"])
        assert "--network" in cmd
        assert "none" in cmd

    def test_rm_flag_present(self):
        ex = _make_executor()
        cmd = ex._build_docker_command(["python", "-c", "print(1)"])
        assert "--rm" in cmd

    def test_image_in_command(self):
        ex = _make_executor()
        cmd = ex._build_docker_command(["python", "-c", "print(1)"])
        assert "python:3.13-slim" in cmd

    def test_user_command_appended(self):
        ex = _make_executor()
        user_cmd = ["python", "-c", "print(42)"]
        cmd = ex._build_docker_command(user_cmd)
        assert cmd[-3:] == user_cmd

    def test_cpu_and_memory_flags(self):
        ex = SandboxExecutor(cpu_limit="0.5", memory_limit="256m")
        cmd = ex._build_docker_command(["python", "--version"])
        assert "--cpus" in cmd and "0.5" in cmd
        assert "--memory" in cmd and "256m" in cmd


# ── Truncation ────────────────────────────────────────────────────────────────


class TestTruncation:
    def test_stdout_truncated_at_limit(self):
        ex = _make_executor()
        big_stdout = "x" * 100_000
        result = SandboxResult(
            exit_code=0, stdout=big_stdout, stderr="", timed_out=False, duration_seconds=0.1
        )
        with patch("src.agents.sandbox_executor.settings") as s:
            s.sandbox_stdout_max_bytes = 64
            s.sandbox_stderr_max_bytes = 16
            truncated = ex._truncate(result)
        assert len(truncated.stdout.encode()) <= 64 + len("\n[OUTPUT TRUNCATED]")
        assert "[OUTPUT TRUNCATED]" in truncated.stdout

    def test_stderr_truncated_at_limit(self):
        ex = _make_executor()
        big_stderr = "e" * 50_000
        result = SandboxResult(
            exit_code=1, stdout="", stderr=big_stderr, timed_out=False, duration_seconds=0.1
        )
        with patch("src.agents.sandbox_executor.settings") as s:
            s.sandbox_stdout_max_bytes = 65536
            s.sandbox_stderr_max_bytes = 16
            truncated = ex._truncate(result)
        assert "[OUTPUT TRUNCATED]" in truncated.stderr

    def test_no_truncation_within_limit(self):
        ex = _make_executor()
        result = SandboxResult(
            exit_code=0, stdout="hello", stderr="world", timed_out=False, duration_seconds=0.1
        )
        with patch("src.agents.sandbox_executor.settings") as s:
            s.sandbox_stdout_max_bytes = 65536
            s.sandbox_stderr_max_bytes = 16384
            truncated = ex._truncate(result)
        assert truncated.stdout == "hello"
        assert truncated.stderr == "world"


# ── Full run (mocked Docker) ──────────────────────────────────────────────────


class TestRunMocked:
    @pytest.mark.asyncio
    async def test_successful_run_returns_result(self):
        ex = _make_executor()
        proc = _make_proc(stdout=b"hello\n", returncode=0)
        with patch("src.agents.sandbox_executor._get_sandbox_mode_variant", return_value="enabled"):
            with patch("asyncio.create_subprocess_exec", return_value=proc):
                result = await ex.run(["python", "-c", "print(1)"])
        assert result.exit_code == 0
        assert result.stdout == "hello\n"
        assert result.succeeded is True
        assert result.duration_seconds >= 0

    @pytest.mark.asyncio
    async def test_nonzero_exit_captured(self):
        ex = _make_executor()
        proc = _make_proc(stderr=b"syntax error\n", returncode=1)
        with patch("src.agents.sandbox_executor._get_sandbox_mode_variant", return_value="enabled"):
            with patch("asyncio.create_subprocess_exec", return_value=proc):
                result = await ex.run(["python", "bad_script.py"])
        assert result.exit_code == 1
        assert result.succeeded is False

    @pytest.mark.asyncio
    async def test_timeout_sets_timed_out_flag(self):
        ex = SandboxExecutor(timeout_seconds=0.001)
        proc = MagicMock()
        proc.returncode = None
        proc.kill = MagicMock()

        async def slow_communicate():
            await asyncio.sleep(10)
            return b"", b""

        proc.communicate = slow_communicate
        with patch("src.agents.sandbox_executor._get_sandbox_mode_variant", return_value="enabled"):
            with patch("asyncio.create_subprocess_exec", return_value=proc):
                result = await ex.run(["sleep", "10"])
        assert result.timed_out is True
        assert result.exit_code == -1

    @pytest.mark.asyncio
    async def test_docker_not_found_raises_policy_error(self):
        ex = _make_executor()
        with patch("src.agents.sandbox_executor._get_sandbox_mode_variant", return_value="enabled"):
            with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
                with pytest.raises(SandboxPolicyError, match="Docker binary not found"):
                    await ex.run(["python", "--version"])

    @pytest.mark.asyncio
    async def test_metacharacter_rejected_before_docker(self):
        ex = _make_executor()
        with patch("src.agents.sandbox_executor._get_sandbox_mode_variant", return_value="enabled"):
            with pytest.raises(SandboxPolicyError, match="metacharacter"):
                await ex.run(["sh", "-c", "echo; rm -rf /"])

    @pytest.mark.asyncio
    async def test_policy_disabled_in_production_blocks_execution(self):
        ex = _make_executor()
        with patch(
            "src.agents.sandbox_executor._get_sandbox_mode_variant", return_value="disabled"
        ):
            with patch("src.agents.sandbox_executor.settings") as mock_settings:
                mock_settings.app_env = "production"
                with pytest.raises(SandboxPolicyError, match="not 'development'"):
                    await ex.run(["python", "--version"])


# ── Feature flag fallback ─────────────────────────────────────────────────────


class TestGetSandboxModeVariant:
    def test_returns_enabled_when_sdk_raises(self):
        # get_client() raising causes the except-branch → fallback "enabled"
        with patch("openfeature.api.get_client", side_effect=RuntimeError("no provider")):
            variant = _get_sandbox_mode_variant()
        assert variant == "enabled"

    def test_returns_sdk_value_when_available(self):
        mock_client = MagicMock()
        mock_client.get_string_value.return_value = "hitl-required"
        with patch("openfeature.api.get_client", return_value=mock_client):
            variant = _get_sandbox_mode_variant()
        assert variant == "hitl-required"
