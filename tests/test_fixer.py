"""Unit tests for pyproject-doctor fixer / normalizer."""

from pyproject_doctor.fixer import PyProjectFixer, fix_pyproject, fix_pyproject_file


def test_fixer_sorts_dependencies():
    unformatted = """
    [build-system]
    requires = ["wheel", "setuptools>=61.0.0"]
    build-backend = "setuptools.build_meta"

    [project]
    name = "fix-me"
    version = "1.0.0"
    dependencies = [
        "uvicorn>=0.20.0",
        "fastapi>=0.95.0",
        "click>=8.0.0"
    ]
    """
    res = fix_pyproject(unformatted)
    assert res.success
    assert res.is_modified
    assert any("Sorted 'build-system.requires'" in c for c in res.changes)
    assert any("Sorted 'project.dependencies'" in c for c in res.changes)

    # In output, dependencies should be in alphabetical order
    content = res.fixed_content
    click_pos = content.find("click")
    fastapi_pos = content.find("fastapi")
    uvicorn_pos = content.find("uvicorn")
    assert click_pos < fastapi_pos < uvicorn_pos


def test_fixer_sorts_optional_dependencies():
    unformatted = """
    [build-system]
    requires = ["setuptools"]
    build-backend = "setuptools.build_meta"

    [project]
    name = "fix-extras"
    version = "1.0.0"

    [project.optional-dependencies]
    test = ["pytest-cov", "pytest"]
    docs = ["sphinx-rtd-theme", "mkdocs"]
    """
    res = fix_pyproject(unformatted)
    assert res.success
    assert res.is_modified
    assert any("Sorted 'project.optional-dependencies'" in c for c in res.changes)
    content = res.fixed_content
    assert content.find("docs") < content.find("test")
    assert content.find("pytest") < content.find("pytest-cov")


def test_fixer_deduplicates_dependencies():
    unformatted = """
    [build-system]
    requires = ["setuptools"]
    build-backend = "setuptools.build_meta"

    [project]
    name = "dedup-test"
    version = "1.0.0"
    dependencies = [
        "requests>=2.20.0",
        "requests>=2.25.0"
    ]
    """
    res = fix_pyproject(unformatted)
    assert res.success
    assert res.is_modified
    assert res.fixed_content.count("requests") == 1


def test_fixer_migrates_deprecated_ruff_configs():
    unformatted = """
    [build-system]
    requires = ["setuptools"]
    build-backend = "setuptools.build_meta"

    [project]
    name = "ruff-migrate"
    version = "1.0.0"

    [tool.ruff]
    select = ["E", "F"]
    ignore = ["E501"]
    line-length = 88
    """
    res = fix_pyproject(unformatted)
    assert res.success
    assert res.is_modified
    assert any("tool.ruff.select" in c for c in res.changes)
    assert any("tool.ruff.ignore" in c for c in res.changes)
    content = res.fixed_content
    assert "[tool.ruff.lint]" in content
    assert "select =" in content


def test_fixer_file_read_and_write(tmp_path):
    p = tmp_path / "pyproject.toml"
    p.write_text(
        """
        [build-system]
        requires = ["wheel", "setuptools"]
        build-backend = "setuptools.build_meta"

        [project]
        name = "test-file-fix"
        version = "1.0.0"
        dependencies = ["z-pkg", "a-pkg"]
        """,
        encoding="utf-8",
    )

    # Dry run
    res_dry = fix_pyproject_file(p, write=False)
    assert res_dry.is_modified
    # Check file was NOT modified on disk
    original = p.read_text(encoding="utf-8")
    assert original.find("z-pkg") < original.find("a-pkg")

    # Real write
    res_write = fix_pyproject_file(p, write=True)
    assert res_write.is_modified
    new_content = p.read_text(encoding="utf-8")
    assert new_content.find("a-pkg") < new_content.find("z-pkg")
