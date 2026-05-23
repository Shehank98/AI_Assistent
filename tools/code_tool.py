"""
tools/code_tool.py — Safe Python code execution for Shehan's one-off scripts.
Runs in a subprocess with a strict timeout. Not for arbitrary untrusted code.
"""

import os
import subprocess
import sys
import tempfile

# Block imports that could cause harm or escape the sandbox
_BLOCKED = [
    "import subprocess", "import socket", "import urllib", "import http",
    "import ftplib", "import smtplib", "__import__('os')", "os.system",
    "os.popen", "shutil.rmtree", "shutil.move",
]


def run_python(code: str, timeout: int = 15) -> str:
    """
    Execute Python code in a subprocess sandbox. Returns stdout/stderr.
    Blocked: network access, os.system, subprocess spawning.
    """
    for blocked in _BLOCKED:
        if blocked in code:
            return f"Blocked: '{blocked}' is not permitted in sandbox execution."

    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(code)
        tmp = f.name

    try:
        result = subprocess.run(
            [sys.executable, tmp],
            capture_output=True,
            text=True,
            timeout=timeout,
            env={"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", "")},
        )
        out = result.stdout.strip()
        err = result.stderr.strip()

        if result.returncode == 0:
            return out or "(no output)"
        else:
            return f"Exit {result.returncode}\n{err or out}"

    except subprocess.TimeoutExpired:
        return f"Timed out after {timeout}s."
    except Exception as e:
        return f"Execution error: {e}"
    finally:
        try:
            os.unlink(tmp)
        except Exception:
            pass
