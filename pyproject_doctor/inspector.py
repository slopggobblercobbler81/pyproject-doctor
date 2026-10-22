"""Inspection and summary tools for pyproject.toml."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .models import ProjectInfo
from .toml_parser import parse_toml


class ProjectInspector:
    """Inspects and extracts high-level project summary and dependencies."""

    @classmethod
    def inspect_text(cls, text: str) -> ProjectInfo:
        data = parse_toml(text)

        build_sys = data.get("build-system", {})
        build_backend = build_sys.get("build-backend") if isinstance(build_sys, dict) else None

        project = data.get("project")
        if not project or not isinstance(project, dict):
            # Check legacy poetry
            poetry = data.get("tool", {}).get("poetry", {})
            if isinstance(poetry, dict):
                return ProjectInfo(
                    name=poetry.get("name"),
                    version=poetry.get("version"),
                    description=poetry.get("description"),
                    build_backend=build_backend or "poetry.core.masonry.api",
                    requires_python=poetry.get("dependencies", {}).get("python"),
                    license=poetry.get("license"),
                    dependencies_count=len(poetry.get("dependencies", {})),
                    optional_dependencies={},
                    scripts=list(poetry.get("scripts", {}).keys()),
                    urls=poetry.get("urls", {}),
                )
            return ProjectInfo(
                name=None,
                version=None,
                description=None,
                build_backend=build_backend,
                requires_python=None,
                license=None,
                dependencies_count=0,
            )

        name = project.get("name")
        version = project.get("version")
        description = project.get("description")
        requires_python = project.get("requires-python")

        # License extraction
        raw_lic = project.get("license")
        license_str = None
        if isinstance(raw_lic, str):
            license_str = raw_lic
        elif isinstance(raw_lic, dict):
            license_str = raw_lic.get("text") or raw_lic.get("file")

        # Dependencies
        deps = project.get("dependencies", [])
        dep_count = len(deps) if isinstance(deps, list) else 0

        # Optional dependencies
        opt_deps_raw = project.get("optional-dependencies", {})
        opt_deps: Dict[str, int] = {}
        if isinstance(opt_deps_raw, dict):
            for group, g_deps in opt_deps_raw.items():
                if isinstance(g_deps, list):
                    opt_deps[group] = len(g_deps)

        # Scripts
        scripts_raw = project.get("scripts", {})
        scripts = list(scripts_raw.keys()) if isinstance(scripts_raw, dict) else []

        # URLs
        urls = project.get("urls", {}) if isinstance(project.get("urls"), dict) else {}

        return ProjectInfo(
            name=name,
            version=version,
            description=description,
            build_backend=build_backend,
            requires_python=requires_python,
            license=license_str,
            dependencies_count=dep_count,
            optional_dependencies=opt_deps,
            scripts=scripts,
            urls=urls,
        )

    @classmethod
    def inspect_file(cls, path: Union[str, Path]) -> ProjectInfo:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {p}")
        text = p.read_text(encoding="utf-8", errors="replace")
        return cls.inspect_text(text)


def inspect_pyproject(path: Union[str, Path]) -> ProjectInfo:
    return ProjectInspector.inspect_file(path)
