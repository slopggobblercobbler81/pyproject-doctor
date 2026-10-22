"""Unit tests for ProjectInspector."""

from pyproject_doctor.inspector import ProjectInspector, inspect_pyproject


def test_inspect_pep621():
    toml_str = """
    [build-system]
    requires = ["hatchling"]
    build-backend = "hatchling.build"

    [project]
    name = "acme-api"
    version = "2.1.0"
    description = "Acme REST API"
    requires-python = ">=3.10"
    license = { text = "Apache-2.0" }
    dependencies = [
        "fastapi>=0.100.0",
        "uvicorn>=0.23.0"
    ]

    [project.optional-dependencies]
    test = ["pytest", "httpx"]
    lint = ["ruff"]

    [project.scripts]
    acme-server = "acme.server:run"

    [project.urls]
    Homepage = "https://acme.org"
    """
    info = ProjectInspector.inspect_text(toml_str)
    assert info.name == "acme-api"
    assert info.version == "2.1.0"
    assert info.build_backend == "hatchling.build"
    assert info.requires_python == ">=3.10"
    assert info.license == "Apache-2.0"
    assert info.dependencies_count == 2
    assert info.optional_dependencies == {"test": 2, "lint": 1}
    assert info.scripts == ["acme-server"]
    assert info.urls["Homepage"] == "https://acme.org"


def test_inspect_legacy_poetry():
    toml_str = """
    [tool.poetry]
    name = "poetry-legacy"
    version = "0.5.0"
    description = "Poetry project"
    license = "MIT"

    [tool.poetry.dependencies]
    python = "^3.9"
    requests = "^2.26.0"

    [tool.poetry.scripts]
    run-tool = "pkg.cli:main"
    """
    info = ProjectInspector.inspect_text(toml_str)
    assert info.name == "poetry-legacy"
    assert info.version == "0.5.0"
    assert info.license == "MIT"
    assert info.scripts == ["run-tool"]


def test_inspect_file(tmp_path):
    p = tmp_path / "pyproject.toml"
    p.write_text(
        """
        [project]
        name = "on-disk"
        version = "1.0.0"
        """,
        encoding="utf-8",
    )
    info = inspect_pyproject(p)
    assert info.name == "on-disk"
    assert info.version == "1.0.0"
