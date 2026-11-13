import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "generate_models.sh"
WINDOWS_BASH = Path("C:/Program Files/Git/bin/bash.exe")
BASH = str(WINDOWS_BASH) if WINDOWS_BASH.is_file() else shutil.which("bash")


@pytest.mark.skipif(BASH is None, reason="Bash is required for the generation CLI")
@pytest.mark.parametrize("arguments,reference", [(["2026-04-08"], "a" * 40), (["one", "two"], "")])
def test_ambiguous_generation_arguments_fail_before_fetching(arguments, reference):
    environment = dict(os.environ)
    environment["BCP_REF"] = reference
    environment["BCP_REPO"] = "must-not-be-fetched"
    result = subprocess.run(  # noqa: S603 - fixed script and literal invalid arguments
        [BASH, SCRIPT.as_posix(), *arguments],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    assert "not both" in result.stderr
    assert "Fetching spec" not in result.stdout
