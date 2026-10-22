"""Unit tests for PyProjectValidator."""

from pyproject_doctor.validator import validate_pyproject, validate_pyproject_file


VALID_PEP621 = """
[build-system]
requires = ["setuptools>=61.0.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "sample-tool"
version = "1.2.3"
description = "A sample CLI utility"
readme = "README.md"
requires-python = ">=3.9"
license = { text = "MIT" }
dependencies = [
    "requests>=2.28.0"
]

[project.scripts]
sample-tool = "sample_tool.cli:main"
"""


def test_validate_valid_pyproject():
    report = validate_pyproject(VALID_PEP621)
    assert report.is_valid
    assert len(report.errors) == 0


def test_missing_build_system():
    bad = """
    [project]
    name = "sample"
    version = "0.1.0"
    """
    report = validate_pyproject(bad)
    assert not report.is_valid
    assert any(d.code == "E101_MISSING_BUILD_SYSTEM" for d in report.errors)


def test_invalid_build_requires():
    bad = """
    [build-system]
    requires = "setuptools"
    build-backend = "setuptools.build_meta"

    [project]
    name = "sample"
    version = "0.1.0"
    """
    report = validate_pyproject(bad)
    assert not report.is_valid
    assert any(d.code == "E103_INVALID_BUILD_REQUIRES" for d in report.errors)


def test_missing_project_table():
    bad = """
    [build-system]
    requires = ["setuptools"]
    build-backend = "setuptools.build_meta"
    """
    report = validate_pyproject(bad)
    assert not report.is_valid
    assert any(d.code == "E200_MISSING_PROJECT_TABLE" for d in report.errors)


def test_missing_and_invalid_project_name():
    missing_name = """
    [build-system]
    requires = ["setuptools"]
    build-backend = "setuptools.build_meta"

    [project]
    version = "0.1.0"
    """
    rep1 = validate_pyproject(missing_name)
    assert any(d.code == "E202_MISSING_PROJECT_NAME" for d in rep1.errors)

    invalid_name = """
    [build-system]
    requires = ["setuptools"]
    build-backend = "setuptools.build_meta"

    [project]
    name = "invalid name with spaces"
    version = "0.1.0"
    """
    rep2 = validate_pyproject(invalid_name)
    assert any(d.code == "E203_INVALID_PROJECT_NAME" for d in rep2.errors)


def test_conflicting_dynamic_field():
    conflicting = """
    [build-system]
    requires = ["setuptools"]
    build-backend = "setuptools.build_meta"

    [project]
    name = "sample"
    version = "1.0.0"
    dynamic = ["version"]
    """
    report = validate_pyproject(conflicting)
    assert not report.is_valid
    assert any(d.code == "E205_CONFLICTING_DYNAMIC_FIELD" for d in report.errors)


def test_invalid_version():
    invalid_ver = """
    [build-system]
    requires = ["setuptools"]
    build-backend = "setuptools.build_meta"

    [project]
    name = "sample"
    version = "not_a_version_at_all"
    """
    report = validate_pyproject(invalid_ver)
    assert not report.is_valid
    assert any(d.code == "E207_INVALID_VERSION_SPEC" for d in report.errors)


def test_invalid_entrypoint():
    bad_ep = """
    [build-system]
    requires = ["setuptools"]
    build-backend = "setuptools.build_meta"

    [project]
    name = "sample"
    version = "0.1.0"

    [project.scripts]
    my-cmd = "invalid entrypoint target format"
    """
    report = validate_pyproject(bad_ep)
    assert not report.is_valid
    assert any(d.code == "E304_INVALID_ENTRYPOINT" for d in report.errors)


def test_validate_file(tmp_path):
    p = tmp_path / "pyproject.toml"
    p.write_text(VALID_PEP621, encoding="utf-8")
    report = validate_pyproject_file(p)
    assert report.is_valid
    assert report.file_path == str(p)


def test_validate_nonexistent_file():
    report = validate_pyproject_file("does_not_exist_pyproject.toml")
    assert not report.is_valid
    assert any(d.code == "E001_FILE_NOT_FOUND" for d in report.errors)


def test_validate_warnings_and_strict():
    loose_toml = """
    [build-system]
    requires = ["setuptools"]
    build-backend = "setuptools.build_meta"

    [project]
    name = "loose-pkg"
    version = "1.0.0"
    dependencies = ["requests"]
    """
    report = validate_pyproject(loose_toml, strict=False)
    assert report.is_valid
    assert len(report.warnings) > 0
    assert any(d.code == "W201_MISSING_README" for d in report.warnings)

    strict_report = validate_pyproject(loose_toml, strict=True)
    assert not strict_report.is_valid


def test_validate_own_pyproject():
    from pathlib import Path
    root_pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    report = validate_pyproject_file(root_pyproject)
    assert report.is_valid
    assert len(report.errors) == 0

