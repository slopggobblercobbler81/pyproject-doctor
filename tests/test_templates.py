"""Unit tests for PEP 621 template generator."""

import pytest
from pyproject_doctor.templates import (
    generate_pyproject_template,
    list_backend_templates,
)
from pyproject_doctor.validator import validate_pyproject


def test_list_templates():
    backends = list_backend_templates()
    assert "setuptools" in backends
    assert "hatch" in backends
    assert "flit" in backends
    assert "poetry" in backends
    assert "pdm" in backends


def test_generated_templates_are_valid():
    for backend in list_backend_templates():
        content = generate_pyproject_template(
            backend=backend,
            name="generated-test-pkg",
            version="1.0.0",
        )
        report = validate_pyproject(content)
        assert report.is_valid, f"Template for {backend} failed validation: {report.errors}"
        assert len(report.errors) == 0


def test_invalid_backend_raises():
    with pytest.raises(ValueError):
        generate_pyproject_template(backend="nonexistent_build_tool")
