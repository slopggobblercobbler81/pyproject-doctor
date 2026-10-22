# pyproject-doctor 📜🩺

[![CI](https://github.com/slopggobblercobbler81/pyproject-doctor/actions/workflows/ci.yml/badge.svg)](https://github.com/slopggobblercobbler81/pyproject-doctor/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.8%20%7C%203.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen.svg)](https://github.com/slopggobblercobbler81/pyproject-doctor)

**pyproject-doctor** is a production-grade, zero-dependency developer CLI utility and Python library to inspect, lint, validate, and scaffold `pyproject.toml` files conforming to PEP 517, PEP 518, and PEP 621 packaging specifications.

Prevent broken builds, detect conflicting dynamic fields, validate dependencies, and ensure your package metadata is 100% compliant with PyPI standards before publishing.

---

## 🚀 Key Capabilities

- 🔍 **Strict PEP 517 / 518 / 621 Schema Validation (`validate`)**:
  - `E101_MISSING_BUILD_SYSTEM`: Missing `[build-system]` table.
  - `E103_INVALID_BUILD_REQUIRES`: Non-list or missing build requires.
  - `E104_INVALID_BUILD_BACKEND`: Invalid or unknown build backend.
  - `E200_MISSING_PROJECT_TABLE`: Missing PEP 621 `[project]` metadata.
  - `E202_MISSING_PROJECT_NAME`: Missing project name.
  - `E203_INVALID_PROJECT_NAME`: Project name violating PEP 508 normalization.
  - `E205_CONFLICTING_DYNAMIC_FIELD`: Declaring fields both statically and in `project.dynamic` (forbidden by PEP 621).
  - `E206_MISSING_VERSION`: Missing version without marking it dynamic.
  - `E207_INVALID_VERSION_SPEC`: Non-PEP 440 version identifier.
  - `E301_INVALID_DEPENDENCIES_TYPE`: Non-list or malformed `project.dependencies`.
  - `E304_INVALID_ENTRYPOINT`: Invalid console script target specification (`module:func`).
  - `W201` / `W202` / `W203`: Best-practice warnings for missing README, license, and python version constraints.
- 📊 **Project Metadata Inspector (`inspect`)**:
  - Summarizes package name, version, build backend, required Python versions, direct dependencies count, optional dependency groups, and registered console scripts.
- ⚡ **Multi-Backend PEP 621 Generator (`generate`)**:
  - Scaffolds a clean, production-grade `pyproject.toml` pre-configured for `setuptools`, `hatch`, `flit`, `poetry`, or `pdm`.
- 📦 **Zero Runtime Dependencies**:
  - Native standard library TOML support (Python 3.11+ `tomllib`, optional `tomli`, and standalone fallback parser).

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

## 🛠️ Usage Guide

### 1. Validate `pyproject.toml`
Inspect your packaging configuration:
```bash
pyproject-doctor validate pyproject.toml
```

Enforce strict zero-warning policy for CI:
```bash
pyproject-doctor validate --strict pyproject.toml
```

Output machine-readable JSON for automated toolchains:
```bash
pyproject-doctor validate --json pyproject.toml
```

### 2. Inspect Package Metadata
Summarize your project configuration:
```bash
pyproject-doctor inspect pyproject.toml
```

Sample output:
```
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

### 3. Generate PEP 621 `pyproject.toml`
Scaffold a new project configuration:
```bash
# Generate with setuptools
pyproject-doctor generate --name my-tool --backend setuptools -o pyproject.toml

# Generate with Hatch
pyproject-doctor generate --name my-api --backend hatch -o pyproject.toml
```

List supported build backends:
```bash
pyproject-doctor backends
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
        entry: pyproject-doctor validate --strict
        language: python
        files: ^pyproject\.toml$
```

---

## 🧪 Running Tests

Run the test suite using `pytest`:

```bash
pytest -v
```

100% test coverage for parser, validator, inspector, templates, and CLI.

---

## 📄 License

MIT © [slopggobblercobbler81](https://github.com/slopggobblercobbler81)
