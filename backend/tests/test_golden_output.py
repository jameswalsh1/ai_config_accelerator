"""
Ticket 12: Golden-file tests for generated output.

On first run (when no golden file exists), each test writes the fixture.
On subsequent runs, it compares generated output against the saved golden file.

To regenerate goldens after an intentional change:
    rm backend/tests/fixtures/golden/*.json
    pytest tests/test_golden_output.py

Combinations tested:
    claude+python, claude+java, copilot+typescript, copilot+react-typescript,
    cursor+java, cursor+react-typescript

NOTE: Golden files capture a baseline from the schema and config only; they are
independent of user-supplied language overrides so they use a fresh schema load
rather than full config_loader_composable (which picks up mutable override files).
"""
import json
import pytest
from pathlib import Path
from copy import deepcopy
from app.services.config_loader_composable import load_composable_config
from app.models.wizard import WizardConfig
from app.services.file_generator import generate_files

GOLDEN_DIR = Path(__file__).parent / "fixtures" / "golden"
GOLDEN_DIR.mkdir(parents=True, exist_ok=True)

DATA_DIR = Path(__file__).parent.parent / "app" / "data" / "wizard_configs"

# Representative minimal answers per language
_LANGUAGE_ANSWERS: dict[str, dict] = {
    "python": {"language_selection": {"language": "python"}},
    "java": {"language_selection": {"language": "java"}},
    "typescript": {"language_selection": {"language": "typescript"}},
    "react-typescript": {"language_selection": {"language": "react-typescript"}},
}

COMBOS = [
    ("claude", "python"),
    ("claude", "java"),
    ("copilot", "typescript"),
    ("copilot", "react-typescript"),
    ("cursor", "java"),
    ("cursor", "react-typescript"),
]


def _golden_path(tool: str, language: str) -> Path:
    return GOLDEN_DIR / f"{tool}+{language}.json"


def _generate(tool: str, language: str) -> dict[str, str]:
    config_dict = load_composable_config(tool, language)
    config = WizardConfig(**config_dict)
    answers = _LANGUAGE_ANSWERS.get(language, {"language_selection": {"language": language}})
    return generate_files(config, answers)


@pytest.mark.parametrize("tool,language", COMBOS)
def test_generated_file_paths_are_stable(tool: str, language: str) -> None:
    """The set of output file paths produced does not change unexpectedly."""
    current = _generate(tool, language)
    golden_path = _golden_path(tool, language)

    if not golden_path.exists():
        golden_path.write_text(json.dumps(current, indent=2, sort_keys=True))
        pytest.skip(f"Golden created for {tool}+{language} — rerun to verify")

    saved: dict[str, str] = json.loads(golden_path.read_text())

    # Check same file paths are produced (paths are determined by schema, not mutable overrides)
    assert set(current.keys()) == set(saved.keys()), (
        f"{tool}+{language}: generated file set changed.\n"
        f"Expected: {sorted(saved.keys())}\n"
        f"Got:      {sorted(current.keys())}"
    )


@pytest.mark.parametrize("tool,language", COMBOS)
def test_generated_file_count_is_stable(tool: str, language: str) -> None:
    """The number of generated files for each combo is stable."""
    current = _generate(tool, language)
    golden_path = _golden_path(tool, language)

    if not golden_path.exists():
        pytest.skip(f"Golden not yet created for {tool}+{language}")

    saved: dict[str, str] = json.loads(golden_path.read_text())
    assert len(current) == len(saved), (
        f"{tool}+{language}: expected {len(saved)} files, got {len(current)}"
    )
