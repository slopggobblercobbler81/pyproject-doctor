# pyproject-doctor 📜🩺

[![CI](https://github.com/slopggobblercobbler81/pyproject-doctor/actions/workflows/ci.yml/badge.svg)](https://github.com/slopggobblercobbler81/pyproject-doctor/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.8%20%7C%203.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen.svg)](https://github.com/slopggobblercobbler81/pyproject-doctor)

**pyproject-doctor** is a production-grade developer CLI utility and Python library to inspect, validate, audit, and normalize `pyproject.toml` files conforming to PEP 517, PEP 518, and PEP 621 packaging specifications and modern tool standards (Ruff, Poetry, Flit, Hatch, Setuptools).

Prevent broken builds, detect conflicting dynamic fields, audit dependencies for security and validity, automatically sort and format sections, and ensure your package metadata is 100% compliant with PyPI standards.

---

## 🚀 Key Capabilities

- 🔍 **Strict PEP 517 / 518 / 621 Schema Validation**:
  - `name`: Validates PEP 508 normalization and prevents illegal naming.
  - `version`: Checks PEP 440 compliance and ensures dynamic version coordination.
  - `description`, `authors`, `license`, `readme`: Validates structure, file existence, and recommended metadata.
  - `build-system`: Enforces valid `requires` and `build-backend` declarations.
- 📦 **PEP 508 Dependency Auditing**:
  - Validates dependency syntax (comparison operators, markers, extras, URL specifiers).
  - Detects unconstrained / missing version bounds (`W301_MISSING_VERSION_BOUNDS`).
  - Identifies unbounded upper versions (`I302_UNBOUNDED_UPPER_VERSION`).
  - Catches duplicate dependencies across `dependencies` and `optional-dependencies`.
- 🛠️ **Deprecated Tool Configuration Detection**:
  - **Ruff**: Flags deprecated top-level linter options (`tool.ruff.select`, `tool.ruff.ignore`) requiring migration to `[tool.ruff.lint]`.
  - **Flake8**: Detects obsolete/non-standard `[tool.flake8]` configurations.
  - **Black**: Warns when conflicting `[tool.black]` configs are maintained alongside Ruff.
  - **Setuptools**: Identifies legacy `setup_requires` and obsolete `packages = ["find:"]` directives.
  - **Poetry**: Detects conflicts between standard PEP 621 `[project]` and legacy `[tool.poetry.dependencies]`.
- 🪄 **Auto-Fix & Normalizer (`--fix`)**:
  - Sorts dependencies in `[build-system.requires]`, `[project.dependencies]`, and `[project.optional-dependencies]` alphabetically.
  - Reorders tables into canonical packaging order (`[build-system]`, `[project]`, `[project.urls]`, `[project.scripts]`, `[tool.*]`).
  - Auto-migrates deprecated `tool.ruff.*` options to `[tool.ruff.lint]`.
  - Normalizes indentation, quotes, and clean table spacing.
- ⚡ **Multi-Backend Generator (`generate`)**:
  - Scaffolds a production-grade `pyproject.toml` pre-configured for `setuptools`, `hatch`, `flit`, `poetry`, or `pdm`.
- 📦 **Zero Runtime Dependencies**:
  - Built-in native TOML parser with automatic support for Python 3.11+ `tomllib`, optional `tomli`, and standalone fallback parser.

---

## 📦 Installation

```bash
pip install pyproject-doctor
```

Or install from source:
```bash
git clone https://github.com/slopggobblercobbler81/pyproject-doctor.git
cd pyproject-doctor
pip install -e .
```

---

## 🛠️ CLI Usage Guide

### 1. Check & Audit `pyproject.toml`
Run a health check and audit without modifying your file:
```bash
# Check pyproject.toml in current directory
pyproject-doctor --check

# Check a specific file
pyproject-doctor --check pyproject.toml

# Audit with verbose diagnostics
pyproject-doctor --check -v pyproject.toml

# Machine-readable JSON output for CI pipelines
pyproject-doctor --check --json pyproject.toml
```
*Exit code is `0` if completely valid and clean; `1` if validation errors, missing bounds, or formatting deviations are detected.*

### 2. Auto-Fix and Normalize (`--fix`)
Automatically format, sort dependencies, deduplicate entries, and migrate deprecated tool options:
```bash
# Auto-fix pyproject.toml in place
pyproject-doctor --fix

# Auto-fix specific files
pyproject-doctor --fix path/to/pyproject.toml

# Dry-run check to preview changes without writing
pyproject-doctor fix --dry-run pyproject.toml
```

Sample output:
```text
✓ Fixed pyproject.toml (3 change(s)):
    • Sorted 'build-system.requires'
    • Sorted 'project.dependencies'
    • Migrated deprecated 'tool.ruff.select' to 'tool.ruff.lint.select'
```

### 3. Validate Metadata (`validate`)
Validate strictly against PEP 517 / 518 / 621:
```bash
# Validate standard specifications
pyproject-doctor validate pyproject.toml

# Enforce strict zero-warning policy for release pipelines
pyproject-doctor validate --strict pyproject.toml

# Output structured JSON validation report
pyproject-doctor validate --json pyproject.toml
```

### 4. Inspect Package Overview (`inspect`)
Summarize packaging metadata, entrypoints, and dependency counts:
```bash
pyproject-doctor inspect pyproject.toml
```

Sample output:
```text
Project Overview for pyproject.toml:
  Name:                 pyproject-doctor
  Version:              1.0.0
  Build Backend:        setuptools.build_meta
  Requires Python:      >=3.8
  License:              MIT
  Dependencies:         0
  Optional Groups:      dev (2)
  Console Scripts:      pyproject-doctor, pypdoc
```

### 5. Generate PEP 621 Templates (`generate`)
Scaffold new packaging configurations:
```bash
# Generate with setuptools
pyproject-doctor generate --name my-tool --backend setuptools -o pyproject.toml

# Generate with Hatchling
pyproject-doctor generate --name my-api --backend hatch -o pyproject.toml

# List supported build backends
pyproject-doctor backends
```

---

## 🐍 Python Library Usage

**pyproject-doctor** can be used as a Python library:

```python
from pyproject_doctor import (
    validate_pyproject,
    validate_pyproject_file,
    fix_pyproject,
    fix_pyproject_file,
    DependencyAuditor,
    ProjectInspector,
)

# 1. Validate content
report = validate_pyproject(toml_text, strict=False)
if not report.is_valid:
    for error in report.errors:
        print(f"[{error.code}] {error.message}")

# 2. Audit dependencies
diagnostics = DependencyAuditor.audit_dependencies(["requests>=2.28.0", "click"])
for diag in diagnostics:
    print(diag.code, diag.message)

# 3. Auto-fix and format
fix_result = fix_pyproject(toml_text)
if fix_result.is_modified:
    print("Applied changes:", fix_result.changes)
    print("Normalized TOML:\n", fix_result.fixed_content)

# 4. Inspect metadata
info = ProjectInspector.inspect_text(toml_text)
print(f"Package: {info.name} v{info.version}")
```

---

## 🤖 Pre-commit Integration

Add **pyproject-doctor** to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/slopggobblercobbler81/pyproject-doctor
    rev: v1.0.0
    hooks:
      - id: pyproject-doctor
        name: Validate pyproject.toml
        entry: pyproject-doctor --check
        language: python
        files: ^pyproject\.toml$
```

---

## 🧪 Running Tests

Run the full unit test suite using `pytest`:

```bash
pytest -v
```

Or with coverage report:
```bash
pytest --cov=pyproject_doctor -v
```

---

## 📄 License

MIT © [slopggobblercobbler81](https://github.com/slopggobblercobbler81)
