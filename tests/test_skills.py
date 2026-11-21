"""Project skills must exist and carry valid frontmatter so Claude Code can load them."""

from pathlib import Path

import pytest
import yaml

SKILLS = Path(__file__).resolve().parents[1] / ".claude" / "skills"
REQUIRED = [
    "tax-rule-change",
    "engine-feature",
    "agent-tool",
    "ui-component",
    "eval-run",
    "release",
]


def frontmatter(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path} must start with YAML frontmatter"
    _, block, body = text.split("---\n", 2)
    meta = yaml.safe_load(block)
    assert isinstance(meta, dict)
    assert body.strip(), f"{path} has no instructions"
    return meta


@pytest.mark.parametrize("name", REQUIRED)
def test_required_skill_exists_with_valid_frontmatter(name: str) -> None:
    meta = frontmatter(SKILLS / name / "SKILL.md")
    assert meta["name"] == name
    description = meta["description"]
    assert isinstance(description, str)
    assert 40 <= len(description) <= 1024


def test_no_unexpected_skill_folders() -> None:
    found = sorted(p.name for p in SKILLS.iterdir() if p.is_dir())
    assert found == sorted(REQUIRED)
