import json
import textwrap
from pathlib import Path

import pytest

from factgraph.cli import main


class ProjectDir:
    """A throwaway content project on disk, built file by file in a test."""

    def __init__(self, root: Path):
        self.root = root

    def write(self, rel: str, content) -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if not isinstance(content, str):
            content = json.dumps(content, indent=2)
        path.write_text(textwrap.dedent(content), encoding="utf-8")
        return path

    @property
    def config(self) -> str:
        return str(self.root / "factgraph.toml")


@pytest.fixture
def project(tmp_path) -> ProjectDir:
    return ProjectDir(tmp_path)


@pytest.fixture
def run(capsys):
    """Run the CLI; return (exit code, stdout lines)."""

    def _run(*args: str):
        code = main(list(args))
        out = capsys.readouterr().out
        return code, [line for line in out.splitlines() if line.strip()]

    return _run
