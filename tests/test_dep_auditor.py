"""Unit tests for PEP 508 dependency auditor."""

import pytest
from pyproject_doctor.dep_auditor import (
    DependencyAuditor,
    normalize_package_name,
    parse_dependency_spec,
)
from pyproject_doctor.models import DiagnosticSeverity


def test_normalize_package_name():
    assert normalize_package_name("Foo_Bar.Baz") == "foo-bar-baz"
    assert normalize_package_name("my--package") == "my-package"
    assert normalize_package_name("REQUESTS") == "requests"


def test_parse_valid_dependencies():
    name, extras, spec, marker, err = parse_dependency_spec("requests>=2.28.0")
    assert err is None
    assert name == "requests"
    assert ">=2.28.0" in spec

    name, extras, spec, marker, err = parse_dependency_spec("fastapi[all]>=0.100.0; python_version>='3.9'")
    assert err is None
    assert name == "fastapi"
    assert extras == "all"
    assert ">=0.100.0" in spec
    assert "python_version" in marker


def test_parse_invalid_dependency_syntax():
    # Invalid single '='
    name, extras, spec, marker, err = parse_dependency_spec("requests=2.28.0")
    assert err is not None

    # Unclosed bracket
    name, extras, spec, marker, err = parse_dependency_spec("package[extra>=1.0")
    assert err is not None


def test_audit_dependencies_missing_bounds():
    diagnostics = DependencyAuditor.audit_dependencies(["requests", "urllib3"])
    missing_bounds = [d for d in diagnostics if d.code == "W301_MISSING_VERSION_BOUNDS"]
    assert len(missing_bounds) == 2
    assert any(d.field_name == "requests" for d in missing_bounds)


def test_audit_dependencies_unbounded_upper():
    diagnostics = DependencyAuditor.audit_dependencies(["requests>=2.28.0"])
    unbounded = [d for d in diagnostics if d.code == "I302_UNBOUNDED_UPPER_VERSION"]
    assert len(unbounded) == 1
    assert unbounded[0].field_name == "requests"


def test_audit_dependencies_duplicate():
    diagnostics = DependencyAuditor.audit_dependencies(["requests>=2.28.0", "requests<3.0.0"])
    dups = [d for d in diagnostics if d.code == "W303_DUPLICATE_DEPENDENCY"]
    assert len(dups) == 1
    assert dups[0].field_name == "requests"


def test_audit_invalid_item_type():
    diagnostics = DependencyAuditor.audit_dependencies([123])
    assert any(d.code == "E302_INVALID_DEPENDENCY_ITEM" for d in diagnostics)
