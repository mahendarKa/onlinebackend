"""Local code execution for the 'Run code' button and auto-grading.

Runs student programs via subprocess inside a throwaway temp directory
with a hard timeout — no Docker required. Relies on toolchains already
installed on the host (python, javac/java, node). Designed for trusted
LAN deployments; it does NOT sandbox the OS (no user isolation / memory
caps on Windows), so only run code from trusted exam candidates.
"""

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass

DEFAULT_TIMEOUT = 5      # per-test-case run seconds
COMPILE_TIMEOUT = 25     # javac etc.

# Aliases so a config may say "python3", "js", "nodejs", etc.
LANG_ALIASES = {
    "py": "python",
    "python2": "python",
    "python3": "python",
    "js": "javascript",
    "node": "javascript",
    "nodejs": "javascript",
}


@dataclass
class CaseResult:
    input_text: str
    expected_output: str
    actual_output: str
    passed: bool
    timed_out: bool = False
    error: str | None = None


def _java_class_name(code: str) -> str:
    """javac requires file name == public class name."""
    m = re.search(r"public\s+(?:final\s+)?class\s+(\w+)", code)
    return m.group(1) if m else "Main"


def _normalise(text: str | None) -> str:
    """Line-wise rstrip + drop trailing blank lines for fair compare."""
    lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    lines = [line.rstrip() for line in lines]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def _run_cmd(argv, workdir, stdin_text, timeout):
    """Returns (returncode, stdout, stderr, timed_out)."""
    try:
        proc = subprocess.run(
            argv,
            cwd=workdir,
            input=stdin_text or "",
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout or "", proc.stderr or "", False
    except subprocess.TimeoutExpired:
        return -1, "", f"Time limit exceeded ({timeout}s)", True
    except FileNotFoundError:
        return -1, "", f"Toolchain not installed: {argv[0]}", False
    except OSError as exc:  # noqa: BLE001 - surface as a run failure
        return -1, "", str(exc), False


def _prepare(language: str, code: str, workdir: str):
    """Write source file and compile if needed.

    Returns (run_argv_builder, error). run_argv_builder(workdir) -> argv.
    """
    if language == "python":
        src = "main.py"
        with open(f"{workdir}/{src}", "w", encoding="utf-8") as fh:
            fh.write(code)
        return lambda wd: ["python", src], None

    if language == "javascript":
        src = "main.js"
        with open(f"{workdir}/{src}", "w", encoding="utf-8") as fh:
            fh.write(code)
        return lambda wd: ["node", src], None

    if language == "java":
        name = _java_class_name(code)
        src = f"{name}.java"
        with open(f"{workdir}/{src}", "w", encoding="utf-8") as fh:
            fh.write(code)
        rc, _out, err, timed_out = _run_cmd(
            ["javac", src], workdir, "", COMPILE_TIMEOUT
        )
        if timed_out:
            return None, "Compilation timed out"
        if rc != 0:
            return None, f"Compilation failed:\n{err.strip() or 'javac error'}"
        return lambda wd: ["java", "-cp", wd, name], None

    return None, f"Unsupported language: {language or '(none)'}"


def run_test_cases(
    language: str,
    code: str,
    cases,
    time_limit: int = DEFAULT_TIMEOUT,
):
    """Execute ``code`` once per test case.

    ``cases`` items may be ORM objects or dicts exposing ``input_text``
    and ``expected_output``. Returns a list[CaseResult]. Compilation
    happens once and its failure is reported on every case.
    """
    language = LANG_ALIASES.get((language or "").lower().strip(), (language or "").lower().strip())

    def fields(case):
        if isinstance(case, dict):
            return case.get("input_text"), case.get("expected_output")
        return case.input_text, case.expected_output

    workdir = tempfile.mkdtemp(prefix="examcode_")
    try:
        build_run, prep_err = _prepare(language, code, workdir)
        results = []
        for case in cases:
            input_text, expected = fields(case)
            if prep_err:
                results.append(CaseResult(
                    input_text=input_text or "",
                    expected_output=expected or "",
                    actual_output="",
                    passed=False,
                    error=prep_err,
                ))
                continue
            argv = build_run(workdir)
            _rc, out, err, timed_out = _run_cmd(
                argv, workdir, input_text, max(int(time_limit or 0), DEFAULT_TIMEOUT)
            )
            error = None
            if timed_out:
                error = f"Time limit exceeded ({time_limit}s)"
            elif err.strip() and not out.strip():
                error = err.strip()[:2000]
            results.append(CaseResult(
                input_text=input_text or "",
                expected_output=expected or "",
                actual_output=out,
                passed=(_normalise(out) == _normalise(expected)),
                timed_out=timed_out,
                error=error,
            ))
        return results
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
