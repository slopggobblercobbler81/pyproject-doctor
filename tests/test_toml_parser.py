"""Unit tests for fallback and standard TOML parsing."""

from pyproject_doctor.toml_parser import _parse_toml_fallback, parse_toml


def test_parse_basic_toml():
    toml_str = """
    title = "Test Project"
    version = "1.0.0"
    debug = true
    count = 42

    [build-system]
    requires = ["setuptools>=61.0.0", "wheel"]
    build-backend = "setuptools.build_meta"
    """
    data = parse_toml(toml_str)
    assert data["title"] == "Test Project"
    assert data["version"] == "1.0.0"
    assert data["debug"] is True
    assert data["count"] == 42
    assert "build-system" in data
    assert data["build-system"]["requires"] == ["setuptools>=61.0.0", "wheel"]
    assert data["build-system"]["build-backend"] == "setuptools.build_meta"


def test_parse_nested_sections():
    toml_str = """
    [project]
    name = "demo"

    [project.scripts]
    run = "demo.cli:main"

    [tool.pytest.ini_options]
    addopts = "-v"
    """
    data = parse_toml(toml_str)
    assert data["project"]["name"] == "demo"
    assert data["project"]["scripts"]["run"] == "demo.cli:main"
    assert data["tool"]["pytest"]["ini_options"]["addopts"] == "-v"


def test_parse_fallback_inline_table():
    toml_str = """
    [project]
    license = { text = "MIT" }
    """
    data = _parse_toml_fallback(toml_str)
    assert data["project"]["license"]["text"] == "MIT"
