"""Normalizer and auto-fix engine for pyproject.toml."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from .dep_auditor import normalize_package_name, parse_dependency_spec
from .models import FixResult
from .toml_parser import parse_toml


# Canonical order of top-level pyproject.toml sections
CANONICAL_SECTION_ORDER = [
    "build-system",
    "project",
    "project.authors",
    "project.maintainers",
    "project.urls",
    "project.scripts",
    "project.gui-scripts",
    "project.entry-points",
    "project.optional-dependencies",
    "tool.setuptools",
    "tool.setuptools.packages.find",
    "tool.ruff",
    "tool.ruff.lint",
    "tool.pytest.ini_options",
    "tool.mypy",
    "tool.coverage.run",
    "tool.coverage.report",
]

# Canonical order of keys within [project]
PROJECT_KEY_ORDER = [
    "name",
    "version",
    "description",
    "readme",
    "requires-python",
    "license",
    "authors",
    "maintainers",
    "keywords",
    "classifiers",
    "dependencies",
    "dynamic",
]

DEPRECATED_RUFF_ROOT_KEYS = {
    "select",
    "ignore",
    "extend-select",
    "extend-ignore",
    "fixable",
    "unfixable",
    "dummy-variable-rgx",
    "per-file-ignores",
}


def sort_dependencies_list(deps: List[str]) -> Tuple[List[str], bool, List[str]]:
    """
    Sort and deduplicate a list of dependencies.
    Returns: (sorted_deps, changed, change_logs)
    """
    changes: List[str] = []
    seen: Dict[str, str] = {}
    deduped: List[str] = []
    has_dedup = False

    for d in deps:
        if not isinstance(d, str):
            deduped.append(d)
            continue
        clean = d.strip()
        name, _, _, _, _ = parse_dependency_spec(clean)
        norm_key = normalize_package_name(name) if name else clean.lower()
        if norm_key in seen:
            has_dedup = True
            changes.append(f"Deduplicated dependency '{clean}'")
        else:
            seen[norm_key] = clean
            deduped.append(clean)

    # Sort case-insensitive by package name
    def sort_key(item: str) -> str:
        if not isinstance(item, str):
            return str(item)
        name, _, _, _, _ = parse_dependency_spec(item.strip())
        return (name or item).lower()

    sorted_deps = sorted(deduped, key=sort_key)
    was_sorted = sorted_deps != deps
    if was_sorted:
        changes.append("Sorted dependencies alphabetically")

    return sorted_deps, (was_sorted or has_dedup), changes


def toml_format_value(val: Any, indent: int = 0) -> str:
    """Format Python values into clean, idiomatic TOML representations."""
    if isinstance(val, bool):
        return "true" if val else "false"
    elif isinstance(val, (int, float)):
        return str(val)
    elif isinstance(val, str):
        # Escape quotes and backslashes
        escaped = val.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return f'"{escaped}"'
    elif isinstance(val, dict):
        # Format inline table
        items = []
        for k, v in val.items():
            formatted_v = toml_format_value(v, indent=indent)
            items.append(f"{k} = {formatted_v}")
        return "{ " + ", ".join(items) + " }"
    elif isinstance(val, list):
        if not val:
            return "[]"
        # If all items are simple strings or dicts
        is_all_dict = all(isinstance(x, dict) for x in val)
        is_all_str = all(isinstance(x, str) for x in val)

        if len(val) <= 2 and is_all_str and all(len(s) < 20 for s in val):
            # Short array inline
            inner = ", ".join(toml_format_value(x) for x in val)
            return f"[{inner}]"

        # Multi-line array format
        sub_indent = " " * (indent + 4)
        base_indent = " " * indent
        lines = ["["]
        for item in val:
            formatted_item = toml_format_value(item, indent=indent + 4)
            lines.append(f"{sub_indent}{formatted_item},")
        lines.append(f"{base_indent}]")
        return "\n".join(lines)
    return str(val)


class PyProjectFixer:
    """Auto-fixer to format, sort build-system/dependencies, and clean syntax in pyproject.toml."""

    @classmethod
    def fix_text(cls, text: str, file_path: str = "pyproject.toml") -> FixResult:
        changes: List[str] = []

        try:
            data = parse_toml(text)
        except Exception as e:
            return FixResult(
                file_path=file_path,
                original_content=text,
                fixed_content=text,
                changes=[],
                is_modified=False,
                success=False,
                error_message=f"Cannot parse TOML syntax: {e}",
            )

        # 1. Sort build-system.requires
        if "build-system" in data and isinstance(data["build-system"], dict):
            reqs = data["build-system"].get("requires")
            if isinstance(reqs, list):
                sorted_reqs, changed, sub_changes = sort_dependencies_list(reqs)
                if changed:
                    data["build-system"]["requires"] = sorted_reqs
                    changes.append("Sorted 'build-system.requires'")

        # 2. Sort project.dependencies
        if "project" in data and isinstance(data["project"], dict):
            proj_deps = data["project"].get("dependencies")
            if isinstance(proj_deps, list):
                sorted_deps, changed, sub_changes = sort_dependencies_list(proj_deps)
                if changed:
                    data["project"]["dependencies"] = sorted_deps
                    changes.append("Sorted 'project.dependencies'")

            # 3. Sort project.optional-dependencies
            opt_deps = data["project"].get("optional-dependencies")
            if isinstance(opt_deps, dict):
                sorted_opt_dict = {}
                opt_changed = False
                for group in sorted(opt_deps.keys()):
                    group_deps = opt_deps[group]
                    if isinstance(group_deps, list):
                        sorted_group, g_changed, _ = sort_dependencies_list(group_deps)
                        sorted_opt_dict[group] = sorted_group
                        if g_changed:
                            opt_changed = True
                    else:
                        sorted_opt_dict[group] = group_deps

                if sorted(opt_deps.keys()) != list(opt_deps.keys()) or opt_changed:
                    data["project"]["optional-dependencies"] = sorted_opt_dict
                    changes.append("Sorted 'project.optional-dependencies'")

        # 4. Migrate deprecated Ruff root options into [tool.ruff.lint]
        if "tool" in data and isinstance(data["tool"], dict):
            ruff_conf = data["tool"].get("ruff")
            if isinstance(ruff_conf, dict):
                deprecated_found = [k for k in ruff_conf.keys() if k in DEPRECATED_RUFF_ROOT_KEYS]
                if deprecated_found:
                    if "lint" not in ruff_conf or not isinstance(ruff_conf["lint"], dict):
                        ruff_conf["lint"] = {}
                    for k in deprecated_found:
                        ruff_conf["lint"][k] = ruff_conf.pop(k)
                        changes.append(f"Migrated deprecated 'tool.ruff.{k}' to 'tool.ruff.lint.{k}'")

        # 5. Format and serialize data cleanly
        formatted_toml = cls._serialize_data(data)

        # Check if actual content changed
        is_modified = formatted_toml.strip() != text.strip()
        if is_modified and not changes:
            changes.append("Formatted and normalized TOML structure and indentation")

        return FixResult(
            file_path=file_path,
            original_content=text,
            fixed_content=formatted_toml,
            changes=changes,
            is_modified=is_modified,
            success=True,
        )

    @classmethod
    def fix_file(cls, path: Union[str, Path], write: bool = True) -> FixResult:
        p = Path(path)
        if not p.exists():
            return FixResult(
                file_path=str(p),
                original_content="",
                fixed_content="",
                changes=[],
                is_modified=False,
                success=False,
                error_message=f"File not found: {p}",
            )

        text = p.read_text(encoding="utf-8")
        result = cls.fix_text(text, file_path=str(p))

        if write and result.success and result.is_modified:
            p.write_text(result.fixed_content, encoding="utf-8")

        return result

    @classmethod
    def _serialize_data(cls, data: Dict[str, Any]) -> str:
        """Serialize data dictionary into clean, canonical TOML."""
        sections: List[Tuple[str, Dict[str, Any]]] = []

        # Extract subsections
        build_system = data.get("build-system")
        project = data.get("project")
        tool = data.get("tool")

        output_lines: List[str] = []

        # 1. [build-system]
        if build_system and isinstance(build_system, dict):
            output_lines.append("[build-system]")
            # Prefer requires first, then build-backend
            for k in ["requires", "build-backend"]:
                if k in build_system:
                    output_lines.append(f"{k} = {toml_format_value(build_system[k])}")
            for k, v in build_system.items():
                if k not in ["requires", "build-backend"]:
                    output_lines.append(f"{k} = {toml_format_value(v)}")
            output_lines.append("")

        # 2. [project]
        if project and isinstance(project, dict):
            output_lines.append("[project]")
            # Direct scalar/array fields
            for k in PROJECT_KEY_ORDER:
                if k in project and not isinstance(project[k], dict):
                    output_lines.append(f"{k} = {toml_format_value(project[k])}")

            # Any extra non-dict fields
            for k, v in project.items():
                if k not in PROJECT_KEY_ORDER and not isinstance(v, dict):
                    output_lines.append(f"{k} = {toml_format_value(v)}")
            output_lines.append("")

            # [project.optional-dependencies]
            if "optional-dependencies" in project and isinstance(project["optional-dependencies"], dict):
                output_lines.append("[project.optional-dependencies]")
                for opt_k in sorted(project["optional-dependencies"].keys()):
                    opt_v = project["optional-dependencies"][opt_k]
                    output_lines.append(f"{opt_k} = {toml_format_value(opt_v)}")
                output_lines.append("")

            # [project.scripts]
            if "scripts" in project and isinstance(project["scripts"], dict):
                output_lines.append("[project.scripts]")
                for s_k, s_v in sorted(project["scripts"].items()):
                    output_lines.append(f'{s_k} = "{s_v}"')
                output_lines.append("")

            # [project.gui-scripts]
            if "gui-scripts" in project and isinstance(project["gui-scripts"], dict):
                output_lines.append("[project.gui-scripts]")
                for s_k, s_v in sorted(project["gui-scripts"].items()):
                    output_lines.append(f'{s_k} = "{s_v}"')
                output_lines.append("")

            # [project.urls]
            if "urls" in project and isinstance(project["urls"], dict):
                output_lines.append("[project.urls]")
                for u_k, u_v in sorted(project["urls"].items()):
                    output_lines.append(f'{u_k} = "{u_v}"')
                output_lines.append("")

        # 3. [tool.*] sections
        if tool and isinstance(tool, dict):
            for tool_name in sorted(tool.keys()):
                tool_val = tool[tool_name]
                if isinstance(tool_val, dict):
                    cls._write_tool_table(f"tool.{tool_name}", tool_val, output_lines)

        # 4. Any other top-level tables
        for top_k in sorted(data.keys()):
            if top_k not in ["build-system", "project", "tool"]:
                top_v = data[top_k]
                if isinstance(top_v, dict):
                    cls._write_tool_table(top_k, top_v, output_lines)

        # Clean trailing blank lines
        result = "\n".join(output_lines).strip() + "\n"
        return result

    @classmethod
    def _write_tool_table(cls, table_name: str, table_data: Dict[str, Any], output_lines: List[str]) -> None:
        """Recursively format nested tool tables."""
        scalar_items = {k: v for k, v in table_data.items() if not isinstance(v, dict)}
        dict_items = {k: v for k, v in table_data.items() if isinstance(v, dict)}

        if scalar_items or not dict_items:
            output_lines.append(f"[{table_name}]")
            for k in sorted(scalar_items.keys()):
                output_lines.append(f"{k} = {toml_format_value(scalar_items[k])}")
            output_lines.append("")

        for sub_k in sorted(dict_items.keys()):
            cls._write_tool_table(f"{table_name}.{sub_k}", dict_items[sub_k], output_lines)


def fix_pyproject(text: str, file_path: str = "pyproject.toml") -> FixResult:
    return PyProjectFixer.fix_text(text, file_path=file_path)


def fix_pyproject_file(path: Union[str, Path], write: bool = True) -> FixResult:
    return PyProjectFixer.fix_file(path, write=write)
