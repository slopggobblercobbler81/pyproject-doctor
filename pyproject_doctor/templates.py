"""Templates for standard modern PEP 621 pyproject.toml files."""

from __future__ import annotations

from typing import Dict, List, Optional


BACKEND_CONFIGS: Dict[str, Dict[str, str]] = {
    "setuptools": {
        "requires": '["setuptools>=61.0.0", "wheel"]',
        "backend": '"setuptools.build_meta"',
        "tool_section": """[tool.setuptools.packages.find]
where = ["."]
include = ["{pkg_name}*"]
""",
    },
    "hatch": {
        "requires": '["hatchling"]',
        "backend": '"hatchling.build"',
        "tool_section": """[tool.hatch.build.targets.wheel]
packages = ["{pkg_name}"]
""",
    },
    "flit": {
        "requires": '["flit_core >=3.4,<4"]',
        "backend": '"flit_core.buildapi"',
        "tool_section": "",
    },
    "poetry": {
        "requires": '["poetry-core>=1.0.0"]',
        "backend": '"poetry.core.masonry.api"',
        "tool_section": "",
    },
    "pdm": {
        "requires": '["pdm-backend"]',
        "backend": '"pdm.backend"',
        "tool_section": """[tool.pdm.build]
includes = ["{pkg_name}"]
""",
    },
}


def list_backend_templates() -> List[str]:
    return sorted(BACKEND_CONFIGS.keys())


def generate_pyproject_template(
    backend: str = "setuptools",
    name: str = "my-awesome-package",
    version: str = "0.1.0",
    description: str = "A modern Python package built with PEP 621 standards.",
) -> str:
    norm_backend = backend.lower().strip()
    if norm_backend not in BACKEND_CONFIGS:
        available = ", ".join(list_backend_templates())
        raise ValueError(f"Unknown build backend '{backend}'. Available: {available}")

    cfg = BACKEND_CONFIGS[norm_backend]
    pkg_name = name.replace("-", "_").lower()

    tool_section = cfg["tool_section"].format(pkg_name=pkg_name) if cfg["tool_section"] else ""

    content = f"""[build-system]
requires = {cfg["requires"]}
build-backend = {cfg["backend"]}

[project]
name = "{name}"
version = "{version}"
description = "{description}"
readme = "README.md"
requires-python = ">=3.8"
license = {{ text = "MIT" }}
authors = [
    {{ name = "Author Name", email = "author@example.com" }}
]
keywords = [
    "python",
    "package",
    "cli",
    "utilities"
]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12"
]
dependencies = []

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0"
]

[project.scripts]
{name} = "{pkg_name}.cli:main"

[project.urls]
Homepage = "https://github.com/username/{name}"
Repository = "https://github.com/username/{name}"
Issues = "https://github.com/username/{name}/issues"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "-v --strict-markers"

{tool_section}"""

    return content.strip() + "\n"
