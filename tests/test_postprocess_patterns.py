import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "postprocess_models.py"
MODEL = """from pydantic import RootModel

class Identifier(
    RootModel[str]
):
    root: str
"""


def run_postprocess(tmp_path, model=MODEL):
    schemas = tmp_path / "schemas"
    schemas.mkdir(exist_ok=True)
    (schemas / "catalog.json").write_text(
        json.dumps({"$defs": {"identifier": {"type": "string", "not": {"pattern": "\\s"}}}}),
        encoding="utf-8",
    )
    module = tmp_path / "models" / "schemas" / "catalog.py"
    if model is not None:
        module.parent.mkdir(parents=True, exist_ok=True)
        module.write_text(model, encoding="utf-8")
    result = subprocess.run(  # noqa: S603 - fixed script and test-owned temporary paths
        [sys.executable, str(SCRIPT), str(schemas), str(schemas), str(tmp_path / "models")],
        text=True,
        capture_output=True,
        check=False,
    )
    return result, module


def test_not_pattern_is_scoped_idempotent_and_handles_multiline_classes(tmp_path):
    other = tmp_path / "models" / "schemas" / "other.py"
    other.parent.mkdir(parents=True)
    other.write_text(MODEL)
    result, module = run_postprocess(tmp_path)
    assert result.returncode == 0, result.stderr
    first = module.read_text()
    assert first.count("def _enforce_not_pattern(") == 1
    assert other.read_text() == MODEL
    repeated, _ = run_postprocess(tmp_path, model=None)
    assert repeated.returncode == 0, repeated.stderr
    assert module.read_text() == first
    check = subprocess.run(  # noqa: S603 - fixed code and test-owned generated module
        [
            sys.executable,
            "-c",
            "exec(open(__import__('sys').argv[1]).read()); Identifier.model_validate('bad id')",
            str(module),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert check.returncode != 0
    assert "String must not match" in check.stderr


def test_missing_generated_model_is_a_generation_failure(tmp_path):
    result, _ = run_postprocess(tmp_path, model=None)
    assert result.returncode != 0
    assert "not.pattern" in result.stderr


def test_incompatible_generated_class_is_a_generation_failure(tmp_path):
    result, _ = run_postprocess(tmp_path, model="class Identifier:\n    pass\n")
    assert result.returncode != 0
    assert "No generated string RootModel" in result.stderr
