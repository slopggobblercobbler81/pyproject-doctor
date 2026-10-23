"""PEP 517 / 518 / 621 validator for pyproject.toml."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from .dep_auditor import DependencyAuditor
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

# Ruff options deprecated at the root [tool.ruff] level in modern Ruff
DEPRECATED_RUFF_ROOT_OPTIONS = {
    "select",
    "ignore",
    "extend-select",
    "extend-ignore",
    "fixable",
    "unfixable",
    "dummy-variable-rgx",
    "per-file-ignores",
}


class PyProjectValidator:
    """Validates pyproject.toml against PEP 517, PEP 518, and PEP 621 specifications."""

    def __init__(self, strict: bool = False):
        self.strict = strict

    def validate_text(
        self,
        text: str,
        file_path: str = "pyproject.toml",
        base_dir: Optional[Path] = None,
    ) -> ValidationReport:
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
        self._validate_project(data, diagnostics, base_dir=base_dir)

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
        return self.validate_text(text, file_path=str(p), base_dir=p.parent)

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
        else:
            # Audit build-system requires for valid PEP 508 strings
            req_diagnostics = DependencyAuditor.audit_dependencies(
                requires, section_name="build-system.requires"
            )
            diagnostics.extend(req_diagnostics)

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

    def _validate_project(
        self,
        data: Dict[str, Any],
        diagnostics: List[Diagnostic],
        base_dir: Optional[Path] = None,
    ) -> None:
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

        # 3. Description
        desc = project.get("description")
        if desc is None and "description" not in dynamic_fields:
            diagnostics.append(
                Diagnostic(
                    code="W205_MISSING_DESCRIPTION",
                    message="Recommended field 'project.description' is missing.",
                    section="project",
                    severity=DiagnosticSeverity.WARNING,
                    field_name="description",
                    suggested_fix='Add description = "A short summary of your project"',
                )
            )
        elif desc is not None and not isinstance(desc, str):
            diagnostics.append(
                Diagnostic(
                    code="E209_INVALID_DESCRIPTION",
                    message="'project.description' must be a string.",
                    section="project",
                    severity=DiagnosticSeverity.ERROR,
                    field_name="description",
                )
            )

        # 4. Authors
        authors = project.get("authors")
        if authors is None and "authors" not in dynamic_fields:
            diagnostics.append(
                Diagnostic(
                    code="W206_MISSING_AUTHORS",
                    message="Recommended field 'project.authors' is not specified.",
                    section="project",
                    severity=DiagnosticSeverity.WARNING,
                    field_name="authors",
                    suggested_fix='Add authors = [{ name = "Author Name", email = "author@example.com" }]',
                )
            )
        elif authors is not None:
            if not isinstance(authors, list):
                diagnostics.append(
                    Diagnostic(
                        code="E208_INVALID_AUTHORS",
                        message="'project.authors' must be a list of tables/dictionaries.",
                        section="project",
                        severity=DiagnosticSeverity.ERROR,
                        field_name="authors",
                    )
                )
            else:
                for idx, author in enumerate(authors):
                    if not isinstance(author, dict):
                        diagnostics.append(
                            Diagnostic(
                                code="E208_INVALID_AUTHORS",
                                message=f"Author at index {idx} must be a table with 'name' and/or 'email'.",
                                section="project.authors",
                                severity=DiagnosticSeverity.ERROR,
                                field_name="authors",
                            )
                        )
                    elif not any(k in author for k in ("name", "email")):
                        diagnostics.append(
                            Diagnostic(
                                code="E208_INVALID_AUTHORS",
                                message=f"Author table at index {idx} must specify at least 'name' or 'email'.",
                                section="project.authors",
                                severity=DiagnosticSeverity.ERROR,
                                field_name="authors",
                            )
                        )

        # 5. Readme
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
        elif readme is not None:
            if isinstance(readme, str):
                if base_dir and not (base_dir / readme).exists():
                    diagnostics.append(
                        Diagnostic(
                            code="W207_README_FILE_NOT_FOUND",
                            message=f"Readme file '{readme}' referenced in 'project.readme' does not exist.",
                            section="project",
                            severity=DiagnosticSeverity.WARNING,
                            field_name="readme",
                        )
                    )
            elif isinstance(readme, dict):
                if "file" not in readme and "text" not in readme:
                    diagnostics.append(
                        Diagnostic(
                            code="E211_INVALID_README_TABLE",
                            message="'project.readme' table must contain either 'file' or 'text'.",
                            section="project",
                            severity=DiagnosticSeverity.ERROR,
                            field_name="readme",
                        )
                    )
            else:
                diagnostics.append(
                    Diagnostic(
                        code="E211_INVALID_README_TYPE",
                        message="'project.readme' must be a string path or table.",
                        section="project",
                        severity=DiagnosticSeverity.ERROR,
                        field_name="readme",
                    )
                )

        # 6. License
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
        elif license_field is not None:
            if isinstance(license_field, dict):
                if "text" not in license_field and "file" not in license_field:
                    diagnostics.append(
                        Diagnostic(
                            code="E210_INVALID_LICENSE",
                            message="'project.license' table must contain either 'text' or 'file'.",
                            section="project",
                            severity=DiagnosticSeverity.ERROR,
                            field_name="license",
                        )
                    )
            elif not isinstance(license_field, str):
                diagnostics.append(
                    Diagnostic(
                        code="E210_INVALID_LICENSE",
                        message="'project.license' must be a string or table with 'text' or 'file'.",
                        section="project",
                        severity=DiagnosticSeverity.ERROR,
                        field_name="license",
                    )
                )

        # 7. Requires-python
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

        # 8. Dependencies
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
                dep_diagnostics = DependencyAuditor.audit_dependencies(
                    dependencies, section_name="project.dependencies"
                )
                diagnostics.extend(dep_diagnostics)

        # 9. Optional dependencies
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
            else:
                for group, group_deps in opt_deps.items():
                    if not isinstance(group_deps, list):
                        diagnostics.append(
                            Diagnostic(
                                code="E303_INVALID_OPTIONAL_DEPS",
                                message=f"Optional dependency group '{group}' must be a list of strings.",
                                section=f"project.optional-dependencies.{group}",
                                severity=DiagnosticSeverity.ERROR,
                                field_name=group,
                            )
                        )
                    else:
                        g_diagnostics = DependencyAuditor.audit_dependencies(
                            group_deps, section_name=f"project.optional-dependencies.{group}"
                        )
                        diagnostics.extend(g_diagnostics)

        # 10. Scripts & entry points
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

        # 1. Pytest configuration
        if "pytest" in tools and isinstance(tools["pytest"], dict):
            if "ini_options" not in tools["pytest"]:
                diagnostics.append(
                    Diagnostic(
                        code="W401_PYTEST_OPTIONS_LOCATION",
                        message="pytest configuration in pyproject.toml should be located under '[tool.pytest.ini_options]'.",
                        section="tool.pytest",
                        severity=DiagnosticSeverity.WARNING,
                        suggested_fix="Move settings under [tool.pytest.ini_options]",
                    )
                )

        # 2. Flake8 configuration (deprecated/non-standard in pyproject.toml)
        if "flake8" in tools:
            diagnostics.append(
                Diagnostic(
                    code="W402_DEPRECATED_FLAKE8_CONFIG",
                    message="Found '[tool.flake8]'. Flake8 does not natively support pyproject.toml; consider migrating to Ruff.",
                    section="tool.flake8",
                    severity=DiagnosticSeverity.WARNING,
                    suggested_fix="Replace [tool.flake8] with modern linter configuration like [tool.ruff]",
                )
            )

        # 3. Ruff configuration
        if "ruff" in tools and isinstance(tools["ruff"], dict):
            ruff_conf = tools["ruff"]
            # Check for deprecated root options
            found_deprecated = [k for k in ruff_conf.keys() if k in DEPRECATED_RUFF_ROOT_OPTIONS]
            for opt in found_deprecated:
                diagnostics.append(
                    Diagnostic(
                        code="W404_DEPRECATED_RUFF_CONFIG",
                        message=f"Ruff option 'tool.ruff.{opt}' is deprecated at the root level; move to '[tool.ruff.lint.{opt}]'.",
                        section="tool.ruff",
                        severity=DiagnosticSeverity.WARNING,
                        field_name=opt,
                        suggested_fix=f"Move '{opt}' under [tool.ruff.lint]",
                    )
                )

            # Check if Black is also defined while Ruff is used
            if "black" in tools:
                diagnostics.append(
                    Diagnostic(
                        code="W403_OBSOLETE_BLACK_CONFIG",
                        message="Found '[tool.black]' configuration alongside '[tool.ruff]'. Ruff formatter replaces Black.",
                        section="tool.black",
                        severity=DiagnosticSeverity.WARNING,
                        suggested_fix="Remove [tool.black] and use Ruff formatting instead",
                    )
                )

        # 4. Poetry configuration
        if "poetry" in tools and isinstance(tools["poetry"], dict):
            if "project" in data and "dependencies" in tools["poetry"]:
                diagnostics.append(
                    Diagnostic(
                        code="W405_POETRY_PEP621_CONFLICT",
                        message="Both standard PEP 621 '[project]' and legacy '[tool.poetry.dependencies]' are present.",
                        section="tool.poetry",
                        severity=DiagnosticSeverity.WARNING,
                        suggested_fix="Consolidate dependencies into PEP 621 [project.dependencies]",
                    )
                )

        # 5. Setuptools configuration
        if "setuptools" in tools and isinstance(tools["setuptools"], dict):
            st = tools["setuptools"]
            if "setup_requires" in st:
                diagnostics.append(
                    Diagnostic(
                        code="W407_LEGACY_SETUPTOOLS_DIRECTIVE",
                        message="'tool.setuptools.setup_requires' is deprecated. Place build dependencies in '[build-system] requires'.",
                        section="tool.setuptools",
                        severity=DiagnosticSeverity.WARNING,
                        field_name="setup_requires",
                        suggested_fix="Move setup_requires items to [build-system] requires = [...]",
                    )
                )
            if "packages" in st and isinstance(st["packages"], list) and "find:" in st["packages"]:
                diagnostics.append(
                    Diagnostic(
                        code="W408_LEGACY_SETUPTOOLS_FIND",
                        message="Legacy 'packages = [\"find:\"]' detected. Use '[tool.setuptools.packages.find]' table instead.",
                        section="tool.setuptools",
                        severity=DiagnosticSeverity.WARNING,
                        field_name="packages",
                    )
                )


def validate_pyproject(text: str, strict: bool = False, base_dir: Optional[Path] = None) -> ValidationReport:
    return PyProjectValidator(strict=strict).validate_text(text, base_dir=base_dir)


def validate_pyproject_file(path: Union[str, Path], strict: bool = False) -> ValidationReport:
    return PyProjectValidator(strict=strict).validate_file(path)
