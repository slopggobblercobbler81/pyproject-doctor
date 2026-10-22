"""pyproject-doctor: Production PEP 517/518/621 validator, packaging linter, and schema inspector."""

__version__ = "1.0.0"

from .inspector import ProjectInspector, inspect_pyproject
from .models import Diagnostic, DiagnosticSeverity, ProjectInfo, ValidationReport
from .templates import generate_pyproject_template, list_backend_templates
from .validator import PyProjectValidator, validate_pyproject, validate_pyproject_file

__all__ = [
    "__version__",
    "Diagnostic",
    "DiagnosticSeverity",
    "ProjectInfo",
    "ValidationReport",
    "PyProjectValidator",
    "validate_pyproject",
    "validate_pyproject_file",
    "ProjectInspector",
    "inspect_pyproject",
    "generate_pyproject_template",
    "list_backend_templates",
]
