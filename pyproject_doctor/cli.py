"""Command line interface for pyproject-doctor."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__
from .inspector import ProjectInspector
from .models import DiagnosticSeverity
from .templates import generate_pyproject_template, list_backend_templates
from .validator import PyProjectValidator


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pyproject-doctor",
        description="Production PEP 517/518/621 validator, packaging linter, and schema inspector.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: validate (alias: lint)
    val_parser = subparsers.add_parser(
        "validate",
        aliases=["lint", "check"],
        help="Validate pyproject.toml against PEP 517, PEP 518, and PEP 621 standards.",
    )
    val_parser.add_argument(
        "files",
        nargs="*",
        default=["pyproject.toml"],
        help="Path(s) to pyproject.toml file(s) to validate (defaults to pyproject.toml)",
    )
    val_parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat style and best-practice warnings as fatal errors.",
    )
    val_parser.add_argument(
        "--json",
        action="store_true",
        help="Output validation results in JSON format.",
    )

    # Command: inspect
    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Summarize project metadata, build backend, dependencies, and entrypoints.",
    )
    inspect_parser.add_argument(
        "file",
        nargs="?",
        default="pyproject.toml",
        help="Path to pyproject.toml (defaults to pyproject.toml)",
    )
    inspect_parser.add_argument(
        "--json",
        action="store_true",
        help="Output project summary in JSON format.",
    )

    # Command: generate
    gen_parser = subparsers.add_parser(
        "generate",
        help="Generate a standard PEP 621 pyproject.toml template for modern build backends.",
    )
    gen_parser.add_argument(
        "--backend",
        "-b",
        default="setuptools",
        choices=list_backend_templates(),
        help="Build backend to use (default: setuptools)",
    )
    gen_parser.add_argument(
        "--name",
        "-n",
        default="my-package",
        help="Package / project name (default: my-package)",
    )
    gen_parser.add_argument(
        "--pkg-version",
        default="0.1.0",
        help="Initial package version (default: 0.1.0)",
    )
    gen_parser.add_argument(
        "-o",
        "--output",
        help="Destination path to write pyproject.toml (defaults to stdout)",
    )

    # Command: backends
    subparsers.add_parser("backends", help="List available build backend templates.")

    return parser


def handle_validate(args: argparse.Namespace) -> int:
    validator = PyProjectValidator(strict=args.strict)
    has_errors = False
    all_reports = {}

    for file_str in args.files:
        p = Path(file_str)
        report = validator.validate_file(p)
        all_reports[file_str] = report.to_dict()

        if not report.is_valid:
            has_errors = True

        if not args.json:
            print(f"Validating {file_str}...")
            if report.is_valid and not report.diagnostics:
                print("  ✓ Fully valid! Complies with PEP 517, PEP 518, and PEP 621.")
            elif report.is_valid:
                print("  ✓ Valid with non-fatal recommendations:")
                for d in report.diagnostics:
                    icon = "⚠" if d.severity == DiagnosticSeverity.WARNING else "ℹ"
                    print(f"    {icon} [{d.code}] {d.message}")
            else:
                print(f"  ✗ Validation failed with {len(report.errors)} error(s):")
                for d in report.errors:
                    field_info = f" (field: '{d.field_name}')" if d.field_name else ""
                    print(f"    ✗ [{d.code}] {d.message}{field_info}")
                for d in report.warnings:
                    print(f"    ⚠ [{d.code}] {d.message}")

    if args.json:
        print(json.dumps(all_reports, indent=2))

    return 1 if has_errors else 0


def handle_inspect(args: argparse.Namespace) -> int:
    p = Path(args.file)
    if not p.exists():
        if args.json:
            print(json.dumps({"error": f"File '{args.file}' not found."}))
        else:
            print(f"Error: File '{args.file}' does not exist.", file=sys.stderr)
        return 1

    info = ProjectInspector.inspect_file(p)

    if args.json:
        print(json.dumps(info.to_dict(), indent=2))
        return 0

    print(f"Project Overview for {p.name}:")
    print(f"  Name:                 {info.name or '<unset>'}")
    print(f"  Version:              {info.version or '<dynamic / unset>'}")
    print(f"  Build Backend:        {info.build_backend or '<unset>'}")
    print(f"  Requires Python:      {info.requires_python or '<any>'}")
    print(f"  License:              {info.license or '<unset>'}")
    print(f"  Dependencies:         {info.dependencies_count}")
    if info.optional_dependencies:
        extras = ", ".join(f"{k} ({v})" for k, v in info.optional_dependencies.items())
        print(f"  Optional Groups:      {extras}")
    if info.scripts:
        print(f"  Console Scripts:      {', '.join(info.scripts)}")

    return 0


def handle_generate(args: argparse.Namespace) -> int:
    content = generate_pyproject_template(
        backend=args.backend,
        name=args.name,
        version=args.pkg_version,
    )
    if args.output:
        Path(args.output).write_text(content, encoding="utf-8")
        print(f"Successfully generated pyproject.toml ({args.backend}) at '{args.output}'.")
    else:
        sys.stdout.write(content)
    return 0


def handle_backends(args: argparse.Namespace) -> int:
    backends = list_backend_templates()
    print("Supported build backend templates:")
    for b in backends:
        print(f"  - {b}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    handlers = {
        "validate": handle_validate,
        "lint": handle_validate,
        "check": handle_validate,
        "inspect": handle_inspect,
        "generate": handle_generate,
        "backends": handle_backends,
    }

    handler = handlers.get(args.command)
    if handler:
        return handler(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
