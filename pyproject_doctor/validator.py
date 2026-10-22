"""PEP 517 / 518 / 621 validator for pyproject.toml."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from .models import Diagnostic, DiagnosticSeverity, ValidationReport
from .toml_parser import parse_toml


PEP508_NAME_REGEX = re.compile(r"^([A-Z0-9]|[A-Z0-9][A-Z0-9._-]*[A-Z0-9])$", re.IGNORECASE)

# Standard PEP 440 version pattern
PEP440_VERSION_REGEX = re.compile(
    r"^v?[0-9]+(\.[0-9]+)*([a-zA-Z]+[0-9]*)?(\+[a-zA-Z0-9._-]+)?$"
)

# Entrypoint pattern: module:func
ENTRYPOINT_REGEX = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*(:[A-Za-z_][A-Za-z0-9_]*)?$")

KNOWN_BUILD_BACKENDS = {
    "setuptools.build_meta",
    "setuptools.build_meta:__legacy__",
    "hatchling.build",
    "flit_core.buildapi",
    "poetry.core.masonry.api",
    "poetry.masonry.api",
    "pdm.backend",
    "pdm.pep517.api",
    "maturin",
    "mesonpy",
    "scikit_build_core.build",
    "whey",
}


class PyProjectValidator:
    """Validates pyproject.toml against PEP 517, PEP 518, and PEP 621 specifications."""

    def __init__(self, strict: bool = False):
        self.strict = strict

    def validate_text(self, text: str, file_path: str = "pyproject.toml") -> ValidationReport:
        diagnostics: List[Diagnostic] = []

        try:
            data = parse_toml(text)
        except Exception as e:
            diagnostics.append(
                Diagnostic(
                    code="E000_TOML_SYNTAX_ERROR",
                    message=f"Failed to parse TOML syntax: {e}",
                    section="global",
                    severity=DiagnosticSeverity.ERROR,
                )
            )
            return ValidationReport(file_path=file_path, is_valid=False, diagnostics=diagnostics)

        # 1. Validate [build-system] (PEP 517 / 518)
        self._validate_build_system(data, diagnostics)

        # 2. Validate [project] (PEP 621)
        self._validate_project(data, diagnostics)

        # 3. Check tool configurations
        self._validate_tools(data, diagnostics)

        is_valid = not any(d.severity == DiagnosticSeverity.ERROR for d in diagnostics)
        if self.strict and any(d.severity == DiagnosticSeverity.WARNING for d in diagnostics):
            is_valid = False

        return ValidationReport(
            file_path=file_path,
            is_valid=is_valid,
            diagnostics=diagnostics,
        )

    def validate_file(self, path: Union[str, Path]) -> ValidationReport:
        p = Path(path)
        if not p.exists():
            return ValidationReport(
                file_path=str(p),
                is_valid=False,
                diagnostics=[
                    Diagnostic(
                        code="E001_FILE_NOT_FOUND",
                        message=f"File not found: {p}",
                        section="global",
                        severity=DiagnosticSeverity.ERROR,
                    )
                ],
            )
        text = p.read_text(encoding="utf-8", errors="replace")
        return self.validate_text(text, file_path=str(p))

    def _validate_build_system(self, data: Dict[str, Any], diagnostics: List[Diagnostic]) -> None:
        build_sys = data.get("build-system")
        if build_sys is None:
            diagnostics.append(
                Diagnostic(
                    code="E101_MISSING_BUILD_SYSTEM",
                    message="Missing '[build-system]' table defined in PEP 517/518.",
                    section="build-system",
                    severity=DiagnosticSeverity.ERROR,
                    suggested_fix='Add [build-system] with requires = [...] and build-backend = "..."',
                )
            )
            return

        if not isinstance(build_sys, dict):
            diagnostics.append(
                Diagnostic(
                    code="E102_INVALID_BUILD_SYSTEM",
                    message="'[build-system]' must be a table/dictionary.",
                    section="build-system",
                    severity=DiagnosticSeverity.ERROR,
                )
            )
            return

        requires = build_sys.get("requires")
        if requires is None or not isinstance(requires, list):
            diagnostics.append(
                Diagnostic(
                    code="E103_INVALID_BUILD_REQUIRES",
                    message="'build-system.requires' is required and must be a list of strings.",
                    section="build-system",
                    severity=DiagnosticSeverity.ERROR,
                    field_name="requires",
                )
            )

        backend = build_sys.get("build-backend")
        if backend is not None:
            if not isinstance(backend, str):
                diagnostics.append(
                    Diagnostic(
                        code="E104_INVALID_BUILD_BACKEND",
                        message="'build-system.build-backend' must be a string.",
                        section="build-system",
                        severity=DiagnosticSeverity.ERROR,
                        field_name="build-backend",
                    )
                )
            elif backend not in KNOWN_BUILD_BACKENDS:
                diagnostics.append(
                    Diagnostic(
                        code="W101_UNKNOWN_BUILD_BACKEND",
                        message=f"Unrecognized build backend '{backend}'. Ensure the package providing this backend is in 'requires'.",
                        section="build-system",
                        severity=DiagnosticSeverity.WARNING,
                        field_name="build-backend",
                    )
                )

    def _validate_project(self, data: Dict[str, Any], diagnostics: List[Diagnostic]) -> None:
        project = data.get("project")
        if project is None:
            # Maybe legacy or tool-only pyproject.toml (e.g. poetry or flit legacy)
            if "tool" in data and "poetry" in data["tool"]:
                diagnostics.append(
                    Diagnostic(
                        code="W200_LEGACY_POETRY_SECTION",
                        message="File uses legacy '[tool.poetry]' metadata instead of standard PEP 621 '[project]'.",
                        section="project",
                        severity=DiagnosticSeverity.INFO,
                    )
                )
                return

            diagnostics.append(
                Diagnostic(
                    code="E200_MISSING_PROJECT_TABLE",
                    message="Missing PEP 621 '[project]' metadata table.",
                    section="project",
                    severity=DiagnosticSeverity.ERROR,
                )
            )
            return

        if not isinstance(project, dict):
            diagnostics.append(
                Diagnostic(
                    code="E201_INVALID_PROJECT_TABLE",
                    message="'[project]' must be a table/dictionary.",
                    section="project",
                    severity=DiagnosticSeverity.ERROR,
                )
            )
            return

        # 1. Project name
        name = project.get("name")
        if not name:
            diagnostics.append(
                Diagnostic(
                    code="E202_MISSING_PROJECT_NAME",
                    message="Required field 'project.name' is missing.",
                    section="project",
                    severity=DiagnosticSeverity.ERROR,
                    field_name="name",
                )
            )
        elif not isinstance(name, str) or not PEP508_NAME_REGEX.match(name):
            diagnostics.append(
                Diagnostic(
                    code="E203_INVALID_PROJECT_NAME",
                    message=f"Invalid project name '{name}'. Must conform to PEP 508 naming conventions.",
                    section="project",
                    severity=DiagnosticSeverity.ERROR,
                    field_name="name",
                )
            )

        dynamic_fields = project.get("dynamic", [])
        if not isinstance(dynamic_fields, list):
            diagnostics.append(
                Diagnostic(
                    code="E204_INVALID_DYNAMIC_FIELD",
                    message="'project.dynamic' must be a list of string field names.",
                    section="project",
                    severity=DiagnosticSeverity.ERROR,
                    field_name="dynamic",
                )
            )
            dynamic_fields = []

        # 2. Project version
        version = project.get("version")
        if "version" in dynamic_fields:
            if version is not None:
                diagnostics.append(
                    Diagnostic(
                        code="E205_CONFLICTING_DYNAMIC_FIELD",
                        message="'version' cannot be specified in both 'project.version' and 'project.dynamic'.",
                        section="project",
                        severity=DiagnosticSeverity.ERROR,
                        field_name="version",
                    )
                )
        else:
            if version is None:
                diagnostics.append(
                    Diagnostic(
                        code="E206_MISSING_VERSION",
                        message="'project.version' is required unless marked as dynamic.",
                        section="project",
                        severity=DiagnosticSeverity.ERROR,
                        field_name="version",
                        suggested_fix="Define version = \"0.1.0\" or add 'version' to dynamic = [...]",
                    )
                )
            elif not isinstance(version, str) or not PEP440_VERSION_REGEX.match(version):
                diagnostics.append(
                    Diagnostic(
                        code="E207_INVALID_VERSION_SPEC",
                        message=f"Version '{version}' is not a valid PEP 440 version specifier.",
                        section="project",
                        severity=DiagnosticSeverity.ERROR,
                        field_name="version",
                    )
                )

        # 3. Readme
        readme = project.get("readme")
        if readme is None and "readme" not in dynamic_fields:
            diagnostics.append(
                Diagnostic(
                    code="W201_MISSING_README",
                    message="Recommended field 'project.readme' is not specified.",
                    section="project",
                    severity=DiagnosticSeverity.WARNING,
                    field_name="readme",
                )
            )

        # 4. License
        license_field = project.get("license")
        if license_field is None and "license" not in dynamic_fields:
            diagnostics.append(
                Diagnostic(
                    code="W202_MISSING_LICENSE",
                    message="Recommended field 'project.license' is missing.",
                    section="project",
                    severity=DiagnosticSeverity.WARNING,
                    field_name="license",
                )
            )

        # 5. Requires-python
        req_py = project.get("requires-python")
        if req_py is None and "requires-python" not in dynamic_fields:
            diagnostics.append(
                Diagnostic(
                    code="W203_MISSING_PYTHON_REQUIRES",
                    message="Recommended field 'project.requires-python' is not set (e.g. '>=3.8').",
                    section="project",
                    severity=DiagnosticSeverity.WARNING,
                    field_name="requires-python",
                )
            )

        # 6. Dependencies
        dependencies = project.get("dependencies", [])
        if dependencies:
            if not isinstance(dependencies, list):
                diagnostics.append(
                    Diagnostic(
                        code="E301_INVALID_DEPENDENCIES_TYPE",
                        message="'project.dependencies' must be a list of PEP 508 strings.",
                        section="project",
                        severity=DiagnosticSeverity.ERROR,
                        field_name="dependencies",
                    )
                )
            else:
                for dep in dependencies:
                    if not isinstance(dep, str):
                        diagnostics.append(
                            Diagnostic(
                                code="E302_INVALID_DEPENDENCY_ITEM",
                                message=f"Dependency '{dep}' must be a string.",
                                section="project",
                                severity=DiagnosticSeverity.ERROR,
                                field_name="dependencies",
                            )
                        )
                    else:
                        # Warning if dependency is completely unconstrained
                        dep_clean = dep.split(";")[0].strip()
                        if not any(op in dep_clean for op in [">=", "==", "<=", "~=", ">", "<", "!="]):
                            diagnostics.append(
                                Diagnostic(
                                    code="W204_UNCONSTRAINED_DEPENDENCY",
                                    message=f"Dependency '{dep}' has no version constraint pinned or bounded.",
                                    section="project",
                                    severity=DiagnosticSeverity.INFO,
                                    field_name="dependencies",
                                )
                            )

        # 7. Optional dependencies
        opt_deps = project.get("optional-dependencies", {})
        if opt_deps:
            if not isinstance(opt_deps, dict):
                diagnostics.append(
                    Diagnostic(
                        code="E303_INVALID_OPTIONAL_DEPS",
                        message="'project.optional-dependencies' must be a table of extra names to list of strings.",
                        section="project",
                        severity=DiagnosticSeverity.ERROR,
                        field_name="optional-dependencies",
                    )
                )

        # 8. Scripts & entry points
        scripts = project.get("scripts", {})
        if scripts and isinstance(scripts, dict):
            for cmd, target in scripts.items():
                if not isinstance(target, str) or not ENTRYPOINT_REGEX.match(target):
                    diagnostics.append(
                        Diagnostic(
                            code="E304_INVALID_ENTRYPOINT",
                            message=f"Script '{cmd}' target '{target}' does not match standard entrypoint format 'module:function'.",
                            section="project.scripts",
                            severity=DiagnosticSeverity.ERROR,
                            field_name="scripts",
                        )
                    )

    def _validate_tools(self, data: Dict[str, Any], diagnostics: List[Diagnostic]) -> None:
        tools = data.get("tool", {})
        if not isinstance(tools, dict):
            return

        # Check for pytest configuration
        if "pytest" in tools and "ini_options" not in tools["pytest"]:
            diagnostics.append(
                Diagnostic(
                    code="W401_PYTEST_OPTIONS_LOCATION",
                    message="pytest configuration in pyproject.toml should be located under '[tool.pytest.ini_options]'.",
                    section="tool.pytest",
                    severity=DiagnosticSeverity.WARNING,
                )
            )


def validate_pyproject(text: str, strict: bool = False) -> ValidationReport:
    return PyProjectValidator(strict=strict).validate_text(text)


def validate_pyproject_file(path: Union[str, Path], strict: bool = False) -> ValidationReport:
    return PyProjectValidator(strict=strict).validate_file(path)
