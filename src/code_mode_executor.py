import os
import sys
import subprocess
import tempfile
from pathlib import Path

class CodeModeExecutor:
    def __init__(self, timeout_seconds=5):
        self.timeout_seconds = timeout_seconds

    def execute(self, code_str: str) -> dict:
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as temp_file:
            temp_file.write(code_str)
            temp_path = temp_file.name

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"

        try:
            result = subprocess.run(
                [sys.executable, temp_path],
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                encoding="utf-8",
                errors="replace",
                env=env
            )
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            success = (result.returncode == 0)

            return {
                "success": success,
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Execution timed out after {self.timeout_seconds} seconds.",
                "exit_code": -1
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "exit_code": -1
            }
        finally:
            try:
                Path(temp_path).unlink(missing_ok=True)
            except Exception:
                pass
