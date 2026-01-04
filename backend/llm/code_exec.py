import subprocess
import tempfile
from typing import Tuple


def run_python_code(code: str, timeout: int = 10) -> Tuple[str, str]:
    """
    Run Python code in a temp file, capture stdout/stderr.
    Minimal sandbox: no network isolation here, keep code small/trusted.
    """
    with tempfile.NamedTemporaryFile("w+", suffix=".py", delete=False) as f:
        f.write(code)
        f.flush()
        try:
            proc = subprocess.run(
                ["python", f.name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
            )
            return proc.stdout.strip(), proc.stderr.strip()
        except subprocess.TimeoutExpired:
            return "", f"Timeout after {timeout}s"

