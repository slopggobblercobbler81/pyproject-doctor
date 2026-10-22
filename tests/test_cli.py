"""Integration tests for pyproject-doctor CLI."""

import json
from pathlib import Path
import pytest
from pyproject_doctor.cli import main


def test_cli_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "pyproject-doctor 1.0.0" in captured.out


def test_cli_help(capsys):
    ret = main([])
    assert ret == 0
    captured = capsys.readouterr()
    assert "usage: pyproject-doctor" in captured.out


def test_cli_validate_valid(tmp_path, capsys):
    f = tmp_path / "pyproject.toml"
    f.write_text(
        """
        [build-system]
        requires = ["setuptools"]
        build-backend = "setuptools.build_meta"

        [project]
        name = "cli-test"
        version = "0.1.0"
        """,
        encoding="utf-8",
    )
    ret = main(["validate", str(f)])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Valid" in captured.out


def test_cli_validate_invalid_and_json(tmp_path, capsys):
    f = tmp_path / "pyproject.toml"
    f.write_text(
        """
        [build-system]
        requires = ["setuptools"]

        [project]
        name = "bad project"
        """,
        encoding="utf-8",
    )
    ret = main(["validate", "--json", str(f)])
    assert ret == 1
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert str(f) in data
    assert data[str(f)]["is_valid"] is False


def test_cli_inspect_text_and_json(tmp_path, capsys):
    f = tmp_path / "pyproject.toml"
    f.write_text(
        """
        [build-system]
        requires = ["hatchling"]
        build-backend = "hatchling.build"

        [project]
        name = "inspect-me"
        version = "3.0.0"
        description = "A wonderful package"
        """,
        encoding="utf-8",
    )
    # Human output
    ret = main(["inspect", str(f)])
    assert ret == 0
    out = capsys.readouterr().out
    assert "inspect-me" in out
    assert "3.0.0" in out

    # JSON output
    ret_json = main(["inspect", "--json", str(f)])
    assert ret_json == 0
    out_json = capsys.readouterr().out
    data = json.loads(out_json)
    assert data["name"] == "inspect-me"
    assert data["version"] == "3.0.0"


def test_cli_generate_and_backends(tmp_path, capsys):
    # Backends command
    ret_b = main(["backends"])
    assert ret_b == 0
    out_b = capsys.readouterr().out
    assert "hatch" in out_b

    # Generate command
    out_file = tmp_path / "pyproject.toml"
    ret_g = main(["generate", "--backend", "hatch", "--name", "demo-tool", "-o", str(out_file)])
    assert ret_g == 0
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert 'name = "demo-tool"' in content
    assert "hatchling.build" in content
