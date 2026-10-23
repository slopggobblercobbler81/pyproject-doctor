"""Command line interface for pyproject-doctor."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import __version__
from .fixer import PyProjectFixer
from .inspector import ProjectInspector
from .models import DiagnosticSeverity
from .templates import generate_pyproject_template, list_backend_templates
from .validator import PyProjectValidator


def _safe_reconfigure() -> None:
    """Safely configure stdout/stderr for UTF-8 on Windows environments."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_safe_reconfigure()


def _get_symbol(kind: str) -> str:
    """Return an encoding-safe symbol for terminal display."""
    can_unicode = False
    try:
        encoding = getattr(sys.stdout, "encoding", "") or "ascii"
        "\u2713\u2717\u26a0\u2139\u2022".encode(encoding)
        can_unicode = True
    except Exception:
        can_unicode = False

    if can_unicode:
        symbols = {
            "ok": "\u2713",
            "err": "\u2717",
            "warn": "\u26a0",
            "info": "\u2139",
            "bullet": "\u2022",
        }
    else:
        symbols = {
            "ok": "[OK]",
            "err": "[FAIL]",
            "warn": "[WARN]",
            "info": "[INFO]",
            "bullet": "-",
        }
    return symbols.get(kind, "*")


KNOWN_COMMANDS = {
    "validate",
    "lint",
    "check",
    "fix",
    "inspect",
    "generate",
    "backends",
}


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pyproject-doctor",
        description="Production PEP 517/518/621 validator, packaging linter, and schema inspector.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: validate (alias: lint)
    val_parser = subparsers.add_parser(
        "validate",
        aliases=["lint"],
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
    val_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Display verbose diagnostic outputs.",
    )

    # Command: check
    check_parser = subparsers.add_parser(
        "check",
        help="Audit pyproject.toml and check formatting/sorting without modifying (exit code 1 if issues found).",
    )
    check_parser.add_argument(
        "files",
        nargs="*",
        default=["pyproject.toml"],
        help="Path(s) to pyproject.toml file(s) to check (defaults to pyproject.toml)",
    )
    check_parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat style and best-practice warnings as fatal errors.",
    )
    check_parser.add_argument(
        "--json",
        action="store_true",
        help="Output check results in JSON format.",
    )
    check_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Display verbose output.",
    )

    # Command: fix
    fix_parser = subparsers.add_parser(
        "fix",
        help="Auto-format, sort build-system/dependencies, and clean deprecated syntax.",
    )
    fix_parser.add_argument(
        "files",
        nargs="*",
        default=["pyproject.toml"],
        help="Path(s) to pyproject.toml file(s) to fix (defaults to pyproject.toml)",
    )
    fix_parser.add_argument(
        "--check",
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Check if files need fixing without modifying them.",
    )
    fix_parser.add_argument(
        "--json",
        action="store_true",
        help="Output fix summary in JSON format.",
    )
    fix_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Display verbose modification details.",
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
    files = getattr(args, "files", []) or ["pyproject.toml"]
    strict = getattr(args, "strict", False)
    use_json = getattr(args, "json", False)
    verbose = getattr(args, "verbose", False)

    validator = PyProjectValidator(strict=strict)
    has_errors = False
    all_reports = {}

    ok_sym = _get_symbol("ok")
    err_sym = _get_symbol("err")
    warn_sym = _get_symbol("warn")
    info_sym = _get_symbol("info")

    for file_str in files:
        p = Path(file_str)
        report = validator.validate_file(p)
        all_reports[file_str] = report.to_dict()

        if not report.is_valid:
            has_errors = True

        if not use_json:
            print(f"Validating {file_str}...")
            if report.is_valid and not report.diagnostics:
                print(f"  {ok_sym} Fully valid! Complies with PEP 517, PEP 518, and PEP 621.")
            elif report.is_valid:
                print(f"  {ok_sym} Valid with recommendations:")
                for d in report.diagnostics:
                    icon = warn_sym if d.severity == DiagnosticSeverity.WARNING else info_sym
                    print(f"    {icon} [{d.code}] {d.message}")
            else:
                print(f"  {err_sym} Validation failed with {len(report.errors)} error(s):")
                for d in report.errors:
                    field_info = f" (field: '{d.field_name}')" if d.field_name else ""
                    print(f"    {err_sym} [{d.code}] {d.message}{field_info}")
                for d in report.warnings:
                    print(f"    {warn_sym} [{d.code}] {d.message}")
                if verbose:
                    for d in report.info:
                        print(f"    {info_sym} [{d.code}] {d.message}")

    if use_json:
        print(json.dumps(all_reports, indent=2))

    return 1 if has_errors else 0


def handle_check(args: argparse.Namespace) -> int:
    files = getattr(args, "files", []) or ["pyproject.toml"]
    strict = getattr(args, "strict", False)
    use_json = getattr(args, "json", False)
    verbose = getattr(args, "verbose", False)

    validator = PyProjectValidator(strict=strict)
    has_issues = False
    all_reports: Dict[str, Any] = {}

    ok_sym = _get_symbol("ok")
    err_sym = _get_symbol("err")
    warn_sym = _get_symbol("warn")
    info_sym = _get_symbol("info")
    bullet_sym = _get_symbol("bullet")

    for file_str in files:
        p = Path(file_str)
        report = validator.validate_file(p)
        fix_res = PyProjectFixer.fix_file(p, write=False)

        needs_formatting = fix_res.is_modified
        if not report.is_valid or needs_formatting:
            has_issues = True

        file_data = {
            "validation": report.to_dict(),
            "needs_formatting": needs_formatting,
            "format_changes": fix_res.changes,
        }
        all_reports[file_str] = file_data

        if not use_json:
            print(f"Checking {file_str}...")
            if report.is_valid and not needs_formatting and not report.warnings:
                print(f"  {ok_sym} Completely healthy! Valid metadata and cleanly formatted.")
            else:
                if not report.is_valid:
                    print(f"  {err_sym} Validation errors ({len(report.errors)}):")
                    for d in report.errors:
                        print(f"    {err_sym} [{d.code}] {d.message}")
                if report.warnings:
                    print(f"  {warn_sym} Validation warnings ({len(report.warnings)}):")
                    for d in report.warnings:
                        print(f"    {warn_sym} [{d.code}] {d.message}")
                if needs_formatting:
                    print(f"  {warn_sym} Formatting / sorting needed ({len(fix_res.changes)}):")
                    for ch in fix_res.changes:
                        print(f"    {bullet_sym} {ch}")
                if verbose and report.info:
                    print("  Info:")
                    for d in report.info:
                        print(f"    {info_sym} [{d.code}] {d.message}")

    if use_json:
        print(json.dumps(all_reports, indent=2))

    return 1 if has_issues else 0


def handle_fix(args: argparse.Namespace) -> int:
    files = getattr(args, "files", []) or ["pyproject.toml"]
    use_json = getattr(args, "json", False)
    verbose = getattr(args, "verbose", False)
    dry_run = getattr(args, "dry_run", False)

    all_results = {}
    any_modified = False
    has_errors = False

    ok_sym = _get_symbol("ok")
    err_sym = _get_symbol("err")
    bullet_sym = _get_symbol("bullet")

    for file_str in files:
        p = Path(file_str)
        if not p.exists():
            res_dict = {
                "file_path": file_str,
                "success": False,
                "error_message": f"File '{file_str}' does not exist.",
                "is_modified": False,
                "changes": [],
            }
            all_results[file_str] = res_dict
            has_errors = True
            if not use_json:
                print(f"Error: File '{file_str}' not found.", file=sys.stderr)
            continue

        result = PyProjectFixer.fix_file(p, write=not dry_run)
        all_results[file_str] = result.to_dict()

        if not result.success:
            has_errors = True

        if result.is_modified:
            any_modified = True

        if not use_json:
            if not result.success:
                print(f"{err_sym} Failed to fix {file_str}: {result.error_message}")
            elif result.is_modified:
                action = "Would modify" if dry_run else "Fixed"
                print(f"{ok_sym} {action} {file_str} ({len(result.changes)} change(s)):")
                for ch in result.changes:
                    print(f"    {bullet_sym} {ch}")
            else:
                print(f"{ok_sym} {file_str} is already cleanly formatted and normalized.")

    if use_json:
        print(json.dumps(all_results, indent=2))

    if has_errors:
        return 1
    if dry_run and any_modified:
        return 1
    return 0


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
    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        parser = create_parser()
        parser.print_help()
        return 0

    first_arg = argv[0]

    # Pre-process flags if root execution without explicit subcommand
    if first_arg not in KNOWN_COMMANDS and first_arg not in {"--help", "-h", "--version"}:
        args_copy = list(argv)
        if "--fix" in args_copy:
            args_copy.remove("--fix")
            effective_argv = ["fix"] + args_copy
        elif "--check" in args_copy:
            args_copy.remove("--check")
            effective_argv = ["check"] + args_copy
        else:
            effective_argv = ["validate"] + args_copy
    else:
        effective_argv = argv

    parser = create_parser()
    args = parser.parse_args(effective_argv)

    handlers = {
        "validate": handle_validate,
        "lint": handle_validate,
        "check": handle_check,
        "fix": handle_fix,
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
