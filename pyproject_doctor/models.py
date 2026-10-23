"""Data models for pyproject-doctor."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class DiagnosticSeverity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class Diagnostic:
    code: str
    message: str
    section: str
    severity: DiagnosticSeverity = DiagnosticSeverity.WARNING
    field_name: Optional[str] = None
    suggested_fix: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "section": self.section,
            "severity": self.severity.value,
            "field": self.field_name,
            "suggested_fix": self.suggested_fix,
        }


@dataclass
class ValidationReport:
    file_path: str
    is_valid: bool
    diagnostics: List[Diagnostic] = field(default_factory=list)

    @property
    def errors(self) -> List[Diagnostic]:
        return [d for d in self.diagnostics if d.severity == DiagnosticSeverity.ERROR]

    @property
    def warnings(self) -> List[Diagnostic]:
        return [d for d in self.diagnostics if d.severity == DiagnosticSeverity.WARNING]

    @property
    def info(self) -> List[Diagnostic]:
        return [d for d in self.diagnostics if d.severity == DiagnosticSeverity.INFO]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "is_valid": self.is_valid,
            "total_diagnostics": len(self.diagnostics),
            "errors": [d.to_dict() for d in self.errors],
            "warnings": [d.to_dict() for d in self.warnings],
            "info": [d.to_dict() for d in self.info],
        }


@dataclass
class ProjectInfo:
    name: Optional[str]
    version: Optional[str]
    description: Optional[str]
    build_backend: Optional[str]
    requires_python: Optional[str]
    license: Optional[str]
    dependencies_count: int
    optional_dependencies: Dict[str, int] = field(default_factory=dict)
    scripts: List[str] = field(default_factory=list)
    urls: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "build_backend": self.build_backend,
            "requires_python": self.requires_python,
            "license": self.license,
            "dependencies_count": self.dependencies_count,
            "optional_dependencies": self.optional_dependencies,
            "scripts": self.scripts,
            "urls": self.urls,
        }


@dataclass
class FixResult:
    file_path: str
    original_content: str
    fixed_content: str
    changes: List[str] = field(default_factory=list)
    is_modified: bool = False
    success: bool = True
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "is_modified": self.is_modified,
            "changes_count": len(self.changes),
            "changes": self.changes,
            "success": self.success,
            "error_message": self.error_message,
        }
