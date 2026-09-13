"""Shared verification runner for command, pytest, and ast_symbol checks."""

from __future__ import annotations

import ast
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Union


VerificationInput = Union[str, dict[str, Any], None]


def normalize_verification_spec(data: VerificationInput) -> dict[str, Any]:
    """Normalize a verification spec from string or dict."""
    if isinstance(data, str):
        command = data.strip()
        if not command:
            raise ValueError("Verification command cannot be empty")
        return {"check_type": "command", "command": command}

    if not isinstance(data, dict):
        raise ValueError("Verification spec must be a string or dictionary")

    spec = dict(data)
    check_type = spec.get("check_type") or spec.get("type")
    command = spec.get("command") or spec.get("cmd")

    if not check_type:
        if command and str(command).strip():
            check_type = "command"
        else:
            raise ValueError("Verification spec requires check_type/type or command/cmd")

    spec["check_type"] = str(check_type).strip()
    if command is not None and str(command).strip():
        spec["command"] = str(command).strip()

    return spec


def verification_spec_from_node_data(data: dict[str, Any]) -> dict[str, Any]:
    """Extract and normalize verification configuration from node data."""
    verif = data.get("verification")
    raw: VerificationInput = None

    if isinstance(verif, dict):
        raw = verif
    elif isinstance(verif, str) and verif.strip():
        raw = verif.strip()
    else:
        command = data.get("check_command") or data.get("test_command")
        if command and str(command).strip():
            raw = str(command).strip()

    if raw is None:
        raise ValueError("Node has no verification command configured in data")

    return normalize_verification_spec(raw)


def _resolve_timeout(spec: dict[str, Any], timeout: float) -> float:
    spec_timeout = spec.get("timeout_seconds")
    if spec_timeout is not None:
        return float(spec_timeout)
    return float(timeout)


def _resolve_expected_exit_code(spec: dict[str, Any]) -> int:
    expected = spec.get("expected_exit_code")
    if expected is None:
        return 0
    return int(expected)


def _build_command(spec: dict[str, Any]) -> str:
    check_type = spec["check_type"]

    if check_type == "command":
        command = spec.get("command")
        if not command or not str(command).strip():
            raise ValueError("command check requires non-empty 'command'")
        return str(command).strip()

    if check_type == "pytest":
        command = spec.get("command")
        if command and str(command).strip():
            return str(command).strip()
        target = spec.get("target")
        if not target or not str(target).strip():
            raise ValueError("pytest check requires non-empty 'target' or 'command'")
        return f"python3 -m pytest {str(target).strip()}"

    if check_type == "ast_symbol":
        file_path = spec.get("file")
        symbols = spec.get("symbols") or []
        if not file_path or not str(file_path).strip():
            raise ValueError("ast_symbol check requires non-empty 'file'")
        if not isinstance(symbols, list) or not symbols:
            raise ValueError("ast_symbol check requires non-empty 'symbols' list")
        symbol_list = ", ".join(str(s).strip() for s in symbols if str(s).strip())
        return f"ast_symbol:{file_path} [{symbol_list}]"

    raise ValueError(f"Unsupported verification check_type '{check_type}'")


def _run_ast_symbol(spec: dict[str, Any], cwd: Path) -> tuple[int, str, str]:
    file_path = spec.get("file")
    symbols = spec.get("symbols") or []
    if not file_path or not str(file_path).strip():
        raise ValueError("ast_symbol check requires non-empty 'file'")
    if not isinstance(symbols, list) or not symbols:
        raise ValueError("ast_symbol check requires non-empty 'symbols' list")

    path = Path(str(file_path).strip())
    if not path.is_absolute():
        path = cwd / path

    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        return 1, "", f"Failed to read file '{path}': {exc}"

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return 1, "", f"Failed to parse '{path}': {exc}"

    defined: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined.add(node.name)

    missing = [str(symbol).strip() for symbol in symbols if str(symbol).strip() not in defined]
    if missing:
        return 1, "", f"Missing symbols: {', '.join(missing)}"

    found = [str(symbol).strip() for symbol in symbols if str(symbol).strip()]
    return 0, f"All symbols defined: {', '.join(found)}", ""


def _determine_status(
    exit_code: int,
    expected_exit_code: int,
    stdout: str,
    stdout_contains: Any,
) -> str:
    if exit_code != expected_exit_code:
        return "failed"
    if stdout_contains is not None and str(stdout_contains) not in stdout:
        return "failed"
    return "passed"


def run_verification(
    spec: dict[str, Any],
    cwd: Path,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """Execute a normalized verification spec and return execution results."""
    normalized = normalize_verification_spec(spec)
    check_type = normalized["check_type"]
    command = _build_command(normalized)
    effective_timeout = _resolve_timeout(normalized, timeout)
    expected_exit_code = _resolve_expected_exit_code(normalized)
    stdout_contains = normalized.get("stdout_contains")

    start_time = time.time()

    if check_type == "ast_symbol":
        exit_code, stdout, stderr = _run_ast_symbol(normalized, cwd)
        duration_seconds = round(time.time() - start_time, 3)
        status = _determine_status(exit_code, expected_exit_code, stdout, stdout_contains)
        return {
            "status": status,
            "command": command,
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "duration_seconds": duration_seconds,
        }

    try:
        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=str(cwd),
            timeout=effective_timeout,
        )
        duration_seconds = round(time.time() - start_time, 3)
        exit_code = proc.returncode
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
    except subprocess.TimeoutExpired as exc:
        duration_seconds = round(time.time() - start_time, 3)
        exit_code = -1
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = f"Command timed out after {effective_timeout} seconds: {exc}"
    except Exception as exc:
        duration_seconds = round(time.time() - start_time, 3)
        exit_code = -1
        stdout = ""
        stderr = f"Execution error: {exc}"

    status = _determine_status(exit_code, expected_exit_code, stdout, stdout_contains)

    return {
        "status": status,
        "command": command,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "duration_seconds": duration_seconds,
    }
