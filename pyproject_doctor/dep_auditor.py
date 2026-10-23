"""PEP 508 dependency auditor and validator."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from .models import Diagnostic, DiagnosticSeverity


# PEP 508 / PEP 440 Regex patterns for standalone fallback
DEP_SPLIT_REGEX = re.compile(r"^([^;]+)(?:;(.*))?$")
PACKAGE_NAME_REGEX = re.compile(
    r"^([A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)"
    r"(?:\[([A-Za-z0-9._,\s-]+)\])?"
    r"(?:\s*(@\s*.+|\s*(?:===|==|!=|<=|>=|<|>|~=)\s*[^;,]+(?:\s*,\s*(?:===|==|!=|<=|>=|<|>|~=)\s*[^;,]+)*))?$"
)

# Standard comparison operators in PEP 440
COMPARISON_OPS = ["===", "==", "!=", "<=", ">=", "<", ">", "~="]


def normalize_package_name(name: str) -> str:
    """Normalize package name per PEP 503."""
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_dependency_spec(dep_str: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]]:
    """
    Parse a PEP 508 dependency string.
    Returns: (name, extras, version_spec, marker, error_message)
    """
    dep_str = dep_str.strip()
    if not dep_str:
        return None, None, None, None, "Empty dependency string."

    # Try packaging library first if available
    try:
        from packaging.requirements import InvalidRequirement, Requirement

        try:
            req = Requirement(dep_str)
            name = req.name
            extras = ",".join(sorted(req.extras)) if req.extras else None
            spec = str(req.specifier) if req.specifier else None
            if req.url:
                spec = f"@ {req.url}"
            marker = str(req.marker) if req.marker else None
            return name, extras, spec, marker, None
        except InvalidRequirement as e:
            return None, None, None, None, str(e)
    except ImportError:
        pass

    # Pure Python Fallback parser
    match_marker = DEP_SPLIT_REGEX.match(dep_str)
    if not match_marker:
        return None, None, None, None, f"Malformed dependency syntax: '{dep_str}'"

    main_part = match_marker.group(1).strip()
    marker_part = match_marker.group(2).strip() if match_marker.group(2) else None

    # Check for invalid single '=' which is a common typo
    if re.search(r"(?<![=!<>~])=(?![=])", main_part):
        return None, None, None, None, f"Invalid '=' in version specifier for '{dep_str}'. Use '==' or '>='."

    match_pkg = PACKAGE_NAME_REGEX.match(main_part)
    if not match_pkg:
        return None, None, None, None, f"Invalid PEP 508 dependency specification: '{dep_str}'"

    name = match_pkg.group(1)
    extras = match_pkg.group(2)
    spec = match_pkg.group(3).strip() if match_pkg.group(3) else None

    # Additional validation if spec is present
    if spec and not spec.startswith("@"):
        # Check operators
        specs = [s.strip() for s in spec.split(",")]
        for s in specs:
            has_op = any(s.startswith(op) for op in COMPARISON_OPS)
            if not has_op:
                return None, None, None, None, f"Invalid version specifier '{s}' in dependency '{dep_str}'"

    return name, extras, spec, marker_part, None


class DependencyAuditor:
    """Audits dependencies for syntax errors, missing bounds, and duplicate entries."""

    @classmethod
    def audit_dependencies(
        cls,
        dependencies: List[str],
        section_name: str = "project.dependencies",
    ) -> List[Diagnostic]:
        diagnostics: List[Diagnostic] = []
        seen_packages: Dict[str, str] = {}

        for dep in dependencies:
            if not isinstance(dep, str):
                diagnostics.append(
                    Diagnostic(
                        code="E302_INVALID_DEPENDENCY_ITEM",
                        message=f"Dependency item must be a string, got {type(dep).__name__}: {dep!r}",
                        section=section_name,
                        severity=DiagnosticSeverity.ERROR,
                    )
                )
                continue

            clean_dep = dep.strip()
            name, extras, spec, marker, error = parse_dependency_spec(clean_dep)

            if error:
                diagnostics.append(
                    Diagnostic(
                        code="E305_INVALID_DEPENDENCY_SYNTAX",
                        message=f"Invalid dependency syntax in '{dep}': {error}",
                        section=section_name,
                        severity=DiagnosticSeverity.ERROR,
                        suggested_fix="Ensure dependency adheres to PEP 508 (e.g., 'requests>=2.28.0')",
                    )
                )
                continue

            if not name:
                continue

            norm_name = normalize_package_name(name)

            # Check for duplicates
            if norm_name in seen_packages:
                diagnostics.append(
                    Diagnostic(
                        code="W303_DUPLICATE_DEPENDENCY",
                        message=f"Duplicate dependency for '{name}' in section '{section_name}' (conflicts with '{seen_packages[norm_name]}').",
                        section=section_name,
                        severity=DiagnosticSeverity.WARNING,
                        field_name=name,
                        suggested_fix=f"Consolidate '{dep}' and '{seen_packages[norm_name]}'",
                    )
                )
            else:
                seen_packages[norm_name] = dep

            # Check for missing bounds
            if not spec:
                diagnostics.append(
                    Diagnostic(
                        code="W301_MISSING_VERSION_BOUNDS",
                        message=f"Dependency '{dep}' has no version bounds specified, which can lead to unpredictable builds.",
                        section=section_name,
                        severity=DiagnosticSeverity.WARNING,
                        field_name=name,
                        suggested_fix=f"Add version constraints, e.g. '{name}>=1.0.0'",
                    )
                )
            elif not spec.startswith("@"):
                # Check for unconstrained upper bound (e.g. >=2.0.0 without < or <=)
                has_upper = ("<" in spec or "<=" in spec or "~=" in spec or "==" in spec or "===" in spec)
                has_lower = (">=" in spec or ">" in spec)
                if has_lower and not has_upper:
                    diagnostics.append(
                        Diagnostic(
                            code="I302_UNBOUNDED_UPPER_VERSION",
                            message=f"Dependency '{dep}' has lower bound but no upper bound; consider adding '<N.0' or using '~='.",
                            section=section_name,
                            severity=DiagnosticSeverity.INFO,
                            field_name=name,
                        )
                    )

        return diagnostics
