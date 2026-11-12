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
from html.parser import HTMLParser

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
    "html5": "html",
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


def _flat(text: str | None) -> str:
    """Collapse all whitespace runs to single spaces (for HTML text)."""
    return " ".join((text or "").split())


class _TextExtractor(HTMLParser):
    """Collects the visible text of an HTML page.

    Skips non-visible sections (head/script/style/etc.). If the page
    has a ``<body>``, only its text is returned; otherwise all text
    outside skipped sections is used. Each text node becomes one line.
    """
    SKIP = {"script", "style", "title", "head", "noscript", "template"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._in_body = False
        self._saw_body = False
        self._all: list[str] = []
        self._body: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "body":
            self._in_body = True
            self._saw_body = True
        if tag in self.SKIP:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag == "body":
            self._in_body = False
        if tag in self.SKIP and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth:
            return
        text = _flat(data)
        if not text:
            return
        self._all.append(text)
        if self._in_body:
            self._body.append(text)

    def page_text(self) -> str:
        chunks = self._body if self._saw_body else self._all
        return "\n".join(chunks)


def _html_page_text(code: str) -> str:
    """Rendered text of the HTML page (tags/comments removed)."""
    parser = _TextExtractor()
    try:
        parser.feed(code or "")
        parser.close()
    except Exception:  # noqa: BLE001 - html.parser is forgiving anyway
        pass
    return parser.page_text()


def _run_html_cases(code: str, cases, fields):
    """Evaluate an HTML submission without executing anything.

    Pass rule per case: the case's expected output must appear in the
    page's rendered text (whitespace-insensitive). If it contains tags
    it is instead matched against the normalised raw markup, so tests
    can verify either visible text or required markup.
    """
    text = _html_page_text(code)
    text_flat = _flat(text).lower()
    source_flat = _flat(code).lower()
    results = []
    for case in cases:
        input_text, expected = fields(case)
        expected_flat = _flat(expected).lower()
        if "<" in expected_flat:
            passed = bool(expected_flat) and expected_flat in source_flat
        else:
            passed = (
                bool(expected_flat)
                and (expected_flat == text_flat
                     or expected_flat in text_flat)
            )
        results.append(CaseResult(
            input_text=input_text or "",
            expected_output=expected or "",
            actual_output=text,
            passed=passed,
        ))
    return results


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

    # HTML isn't executable — grade the rendered page text/markup.
    if language == "html":
        return _run_html_cases(code, cases, fields)

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
