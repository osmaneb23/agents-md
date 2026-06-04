from __future__ import annotations

import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_lint_action_installs_pinned_package_version() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = pyproject["project"]["version"]
    action = (ROOT / ".github/actions/agents-md-lint/action.yml").read_text(encoding="utf-8")

    assert f'default: "{version}"' in action
    assert 'python -m pip install "agent-context-md==${{ inputs.version }}"' in action
    assert "python -m pip install agent-context-md\n" not in action


def test_publish_workflow_uses_matching_node24_artifact_actions() -> None:
    workflow = (ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8")

    assert "actions/upload-artifact@v7" in workflow
    assert "actions/download-artifact@v7" in workflow
    assert "actions/upload-artifact@v6" not in workflow
    assert "actions/download-artifact@v6" not in workflow
