"""Zero-dependency TOML parser with tomllib / tomli fallback."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple, Union


def _parse_toml_fallback(text: str) -> Dict[str, Any]:
    """Lightweight pure-python fallback TOML parser for pyproject.toml structures."""
    root: Dict[str, Any] = {}
    current_section: Dict[str, Any] = root
    section_path: List[str] = []

    lines = text.splitlines()
    i = 0
    num_lines = len(lines)

    while i < num_lines:
        line = lines[i].strip()
        i += 1

        if not line or line.startswith("#"):
            continue

        # Strip trailing inline comments if not inside quotes
        if "#" in line:
            # Simple check
            parts = re.split(r"\s+#", line, maxsplit=1)
            line = parts[0].strip()

        # Section header e.g. [project] or [tool.pytest.ini_options]
        if line.startswith("[[") and line.endswith("]]"):
            header = line[2:-2].strip()
            keys = [k.strip().strip('"').strip("'") for k in header.split(".")]
            curr = root
            for k in keys[:-1]:
                if k not in curr:
                    curr[k] = {}
                curr = curr[k]
            last_k = keys[-1]
            if last_k not in curr:
                curr[last_k] = []
            new_table: Dict[str, Any] = {}
            curr[last_k].append(new_table)
            current_section = new_table
            continue

        if line.startswith("[") and line.endswith("]"):
            header = line[1:-1].strip()
            keys = [k.strip().strip('"').strip("'") for k in header.split(".")]
            curr = root
            for k in keys:
                if k not in curr:
                    curr[k] = {}
                curr = curr[k]
            current_section = curr
            continue

        # Key = Value
        if "=" in line:
            key_part, val_part = line.split("=", 1)
            key = key_part.strip().strip('"').strip("'")
            val_part = val_part.strip()

            # Multiline array detection
            if val_part.startswith("[") and not val_part.endswith("]"):
                array_lines = [val_part]
                while i < num_lines:
                    nxt = lines[i].strip()
                    i += 1
                    # strip comment
                    if "#" in nxt:
                        nxt = re.split(r"\s+#", nxt, maxsplit=1)[0].strip()
                    array_lines.append(nxt)
                    if nxt.endswith("]"):
                        break
                val_part = " ".join(array_lines)

            # Multiline inline table or string
            val = _parse_val(val_part)
            current_section[key] = val

    return root


def _parse_val(val_str: str) -> Any:
    val_str = val_str.strip()
    if not val_str:
        return ""

    # Boolean
    if val_str == "true":
        return True
    if val_str == "false":
        return False

    # Strings
    if (val_str.startswith('"') and val_str.endswith('"')) or (val_str.startswith("'") and val_str.endswith("'")):
        return val_str[1:-1]

    # Arrays
    if val_str.startswith("[") and val_str.endswith("]"):
        inner = val_str[1:-1].strip()
        if not inner:
            return []
        # Parse comma-delimited items with respect to quotes
        items: List[Any] = []
        token: List[str] = []
        in_quote = False
        quote_char = ""

        for ch in inner:
            if ch in ('"', "'"):
                if in_quote and ch == quote_char:
                    in_quote = False
                elif not in_quote:
                    in_quote = True
                    quote_char = ch
                token.append(ch)
            elif ch == "," and not in_quote:
                item_str = "".join(token).strip()
                if item_str:
                    items.append(_parse_val(item_str))
                token = []
            else:
                token.append(ch)

        if token:
            item_str = "".join(token).strip()
            if item_str:
                items.append(_parse_val(item_str))

        return items

    # Inline Tables { key = "val" }
    if val_str.startswith("{") and val_str.endswith("}"):
        inner = val_str[1:-1].strip()
        table: Dict[str, Any] = {}
        if not inner:
            return table
        pairs = inner.split(",")
        for pair in pairs:
            if "=" in pair:
                k, v = pair.split("=", 1)
                table[k.strip().strip('"').strip("'")] = _parse_val(v.strip())
        return table

    # Numbers
    try:
        if "." in val_str:
            return float(val_str)
        return int(val_str)
    except ValueError:
        pass

    return val_str


def parse_toml(content: str) -> Dict[str, Any]:
    """Parse TOML string using the best available implementation."""
    # 1. Python 3.11+ built-in tomllib
    try:
        import tomllib
        return tomllib.loads(content)
    except ImportError:
        pass

    # 2. tomli if installed
    try:
        import tomli
        return tomli.loads(content)
    except ImportError:
        pass

    # 3. Pure python fallback
    return _parse_toml_fallback(content)
