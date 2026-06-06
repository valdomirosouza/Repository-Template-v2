"""Sandbox executor — run agent-generated code in an isolated Docker container.

Every agent-generated command or script MUST pass through this module before
execution. No exceptions without explicit HITL approval.

Spec: specs/ai/sandbox-execution.md
ADR:  ADR-0016 (Agent Sandbox Execution Policy)
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from src.agents.code_pre_flight import CodePreFlight, CodePreFlightError
from src.observability.logger import get_logger
from src.shared.config import settings

logger = get_logger("sandbox_executor")

# Characters with shell expansion meaning when passed to a shell interpreter.
# Parentheses and > are omitted: they are legitimate in Python code and have
# no shell meaning when Docker executes an argv list (not a shell string).
_SHELL_METACHARACTERS = frozenset(";|&$`")

# Sentinel placed at the end of truncated output so callers know it was cut.
_TRUNCATION_MARKER = "\n[OUTPUT TRUNCATED]"


@dataclass
class SandboxResult:
    """Execution result from an isolated sandbox run.

    Spec: specs/ai/sandbox-execution.md §4.3
    Passed unmodified to EvaluatorAgent for scoring.
    """

    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    duration_seconds: float

    @property
    def succeeded(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


class SandboxPolicyError(Exception):
    """Raised when the sandbox policy blocks execution before Docker is invoked."""


class SandboxExecutor:
    """Execute agent-generated commands inside an ephemeral Docker container.

    The container runs with:
      - --network none        (no external network access)
      - --cpus / --memory     (resource caps from settings)
      - no environment vars   (zero secrets passed in)
      - --rm                  (auto-removed after exit)

    Usage::

        executor = SandboxExecutor()
        result = await executor.run(["python", "-c", "print('hello')"])
        assert result.succeeded
    """

    def __init__(
        self,
        *,
        docker_image: str | None = None,
        timeout_seconds: float | None = None,
        cpu_limit: str | None = None,
        memory_limit: str | None = None,
    ) -> None:
        self._image = docker_image or settings.sandbox_docker_image
        self._timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.sandbox_exec_timeout_seconds
        )
        self._cpu = cpu_limit or settings.sandbox_cpu_limit
        self._memory = memory_limit or settings.sandbox_memory_limit

    # ── Public API ──────────────────────────────────────────────────────────────

    async def run(
        self,
        command: list[str],
        *,
        workdir_content: dict[str, str] | None = None,
        risk_score: float = 0.0,
    ) -> SandboxResult:
        """Execute *command* inside an isolated Docker container.

        Args:
            command: argv list — e.g. ["python", "-c", "print(1)"].
                     Must NOT contain shell metacharacters unless the
                     orchestrator explicitly templated them.
            workdir_content: optional {filename: content} dict of files to
                             write into the container's working directory
                             before execution.
            risk_score: forwarded from the agent action; used to enforce
                        sandbox-mode=hitl-required policy.

        Returns:
            SandboxResult — always returns, never raises on non-zero exit.

        Raises:
            SandboxPolicyError: if the sandbox-mode flag is 'disabled' in a
                                non-development environment, or if the command
                                contains unsafe metacharacters.
        """
        self._validate_command(command)
        self._enforce_policy(risk_score)

        # SD3: pre-flight static check on any inline Python code snippet (ADR-0047).
        # The "-c" argv form is the primary path for agent-generated Python.
        if len(command) >= 3 and command[0] == "python" and command[1] == "-c":
            try:
                CodePreFlight.check_or_raise(command[2])
            except CodePreFlightError as exc:
                logger.warning(
                    "sandbox.pre_flight_failed",
                    reason=str(exc),
                )
                raise SandboxPolicyError(f"Code pre-flight check failed: {exc}") from exc

        docker_cmd = self._build_docker_command(command)
        logger.info(
            "sandbox execution starting",
            image=self._image,
            command=command,
            risk_score=risk_score,
        )

        result = await self._run_docker(docker_cmd)
        result = self._truncate(result)

        logger.info(
            "sandbox execution finished",
            exit_code=result.exit_code,
            timed_out=result.timed_out,
            duration_seconds=result.duration_seconds,
        )
        return result

    # ── Private helpers ─────────────────────────────────────────────────────────

    def _validate_command(self, command: list[str]) -> None:
        """Reject commands that contain unescaped shell metacharacters."""
        flat = " ".join(command)
        found = _SHELL_METACHARACTERS & set(flat)
        if found:
            raise SandboxPolicyError(
                f"Command contains shell metacharacters {found!r}. "
                "Use argv list form — never pass shell strings to the sandbox."
            )

    def _enforce_policy(self, risk_score: float) -> None:
        """Enforce sandbox-mode feature flag policy.

        Raises SandboxPolicyError if the current flag variant prohibits execution.
        """
        variant = _get_sandbox_mode_variant()

        if variant == "disabled":
            if settings.app_env != "development":
                raise SandboxPolicyError(
                    "sandbox-mode is 'disabled' but app_env is not 'development'. "
                    "Production and staging require sandbox-mode 'enabled' or 'hitl-required'."
                )
            logger.warning("sandbox disabled — development environment only")
            return

        if variant == "hitl-required":
            # Callers must gate on HITL before invoking run(); this guard is a
            # defence-in-depth check, not a replacement for the gateway.
            if risk_score < settings.hitl_risk_threshold:
                logger.warning(
                    "sandbox-mode is hitl-required; caller should have obtained HITL approval",
                    risk_score=risk_score,
                )

    def _build_docker_command(self, command: list[str]) -> list[str]:
        return [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--cpus",
            self._cpu,
            "--memory",
            self._memory,
            "--workdir",
            "/sandbox",
            self._image,
            *command,
        ]

    async def _run_docker(self, docker_cmd: list[str]) -> SandboxResult:
        start = time.monotonic()
        timed_out = False
        exit_code = -1
        stdout_bytes = b""
        stderr_bytes = b""

        try:
            proc = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={},  # zero environment — no host secrets leak in
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=self._timeout,
                )
                exit_code = proc.returncode if proc.returncode is not None else -1
            except TimeoutError:
                timed_out = True
                try:
                    proc.kill()
                    await proc.communicate()
                except Exception as exc:
                    logger.warning("sandbox cleanup after timeout failed", error=str(exc))
                exit_code = -1
                logger.warning("sandbox execution timed out", timeout=self._timeout)

        except FileNotFoundError as exc:
            # Docker not installed — surface clearly rather than silently failing.
            raise SandboxPolicyError(
                "Docker binary not found. Install Docker to use SandboxExecutor."
            ) from exc

        duration = time.monotonic() - start
        return SandboxResult(
            exit_code=exit_code,
            stdout=stdout_bytes.decode("utf-8", errors="replace"),
            stderr=stderr_bytes.decode("utf-8", errors="replace"),
            timed_out=timed_out,
            duration_seconds=round(duration, 3),
        )

    def _truncate(self, result: SandboxResult) -> SandboxResult:
        """Enforce stdout/stderr size caps from spec §4.1."""
        stdout = result.stdout
        stderr = result.stderr

        if len(stdout.encode()) > settings.sandbox_stdout_max_bytes:
            stdout = stdout.encode()[: settings.sandbox_stdout_max_bytes].decode(
                "utf-8", errors="ignore"
            )
            stdout += _TRUNCATION_MARKER

        if len(stderr.encode()) > settings.sandbox_stderr_max_bytes:
            stderr = stderr.encode()[: settings.sandbox_stderr_max_bytes].decode(
                "utf-8", errors="ignore"
            )
            stderr += _TRUNCATION_MARKER

        return SandboxResult(
            exit_code=result.exit_code,
            stdout=stdout,
            stderr=stderr,
            timed_out=result.timed_out,
            duration_seconds=result.duration_seconds,
        )


def _get_sandbox_mode_variant() -> str:
    """Return the active sandbox-mode flag variant.

    Evaluation order:
    1. OpenFeature SDK (flagd in production, InMemoryProvider in tests).
    2. Fallback: 'enabled' — safe default that enforces the sandbox.
    """
    try:
        from openfeature import api

        client = api.get_client()
        return client.get_string_value("sandbox-mode", "enabled")
    except Exception:
        return "enabled"
