"""Resolve selected CFS material codes from private K1 JSON databases."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Dict, Iterable, List, Mapping, Sequence


TARGET_CODES = ("000001", "000003")
SECTIONS = (
    "MATERIAL_DATABASE_JSON",
    "MATERIAL_OPTION_JSON",
    "MATERIAL_BOX_INFO_JSON",
    "MATERIAL_MODIFY_INFO_JSON",
)
SAFE_KEY = re.compile(r"(material|type|name|code|nozzle|temp|minimum|maximum|min|max|speed)", re.I)
FORBIDDEN_KEY = re.compile(r"(uuid|serial|\bsn\b|color|mac|token|password)", re.I)


class DatabaseError(ValueError):
    pass


def _section(lines: Sequence[str], name: str) -> List[str]:
    begin = "=== %s_BEGIN ===" % name
    end = "=== %s_END ===" % name
    if lines.count(begin) != 1 or lines.count(end) != 1:
        raise DatabaseError("section_invalid:%s" % name)
    start = lines.index(begin) + 1
    stop = lines.index(end)
    return list(lines[start:stop])


def _load_document(lines: Sequence[str], name: str) -> Dict[str, Any]:
    block = _section(lines, name)
    if block == ["ABSENT"]:
        return {"present": False, "sha256": None, "document": None}
    if not block:
        raise DatabaseError("section_empty:%s" % name)
    parts = block[0].split(None, 1)
    if len(parts) != 2 or len(parts[0]) != 64:
        raise DatabaseError("hash_missing:%s" % name)
    document_text = "\n".join(block[1:]).strip()
    if not document_text:
        raise DatabaseError("document_empty:%s" % name)
    return {
        "present": True,
        "sha256": parts[0].lower(),
        "document": json.loads(document_text),
    }


def _contains_code(value: Any, code: str) -> bool:
    if isinstance(value, Mapping):
        return any(_contains_code(item, code) for item in value.values())
    if isinstance(value, list):
        return any(_contains_code(item, code) for item in value)
    return str(value) == code


def _safe_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list) and all(item is None or isinstance(item, (bool, int, float, str)) for item in value):
        return value
    return None


def _safe_fields(mapping: Mapping[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in mapping.items():
        text = str(key)
        if FORBIDDEN_KEY.search(text) or not SAFE_KEY.search(text):
            continue
        safe = _safe_scalar(value)
        if safe is not None:
            result[text] = safe
    return result


def _matches(value: Any, code: str, path: str = "$") -> Iterable[Dict[str, Any]]:
    if isinstance(value, Mapping):
        if _contains_code(value, code):
            safe = _safe_fields(value)
            if safe and any(str(item) == code or (isinstance(item, list) and code in [str(part) for part in item]) for item in safe.values()):
                yield {"path": path, "fields": safe}
        for key, item in value.items():
            if FORBIDDEN_KEY.search(str(key)):
                continue
            yield from _matches(item, code, "%s.%s" % (path, key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _matches(item, code, "%s[%d]" % (path, index))


def analyze(path: Path) -> Dict[str, Any]:
    lines = path.read_text(encoding="utf-8-sig", errors="strict").splitlines()
    if "MATERIAL_DATABASE_READ_ONLY_OK" not in lines:
        raise DatabaseError("terminal_marker_missing")
    documents = {name: _load_document(lines, name) for name in SECTIONS}
    matches: Dict[str, List[Dict[str, Any]]] = {code: [] for code in TARGET_CODES}
    for name, source in documents.items():
        if not source["present"]:
            continue
        for code in TARGET_CODES:
            for match in _matches(source["document"], code):
                matches[code].append({"source": name, **match})
    return {
        "schema": 1,
        "status": "MATERIAL_DATABASE_ANALYSIS_OK",
        "source_hashes": {name: source["sha256"] for name, source in documents.items()},
        "matches": matches,
        "identity_fields_exported": False,
        "printer_effect": False,
        "capture_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def main(argv=None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 1:
        print("usage: analyze_material_database.py <private-capture>", file=sys.stderr)
        return 2
    try:
        result = analyze(Path(arguments[0]))
    except Exception as exc:
        print(json.dumps({"status": "MATERIAL_DATABASE_ANALYSIS_KO", "error": "%s:%s" % (type(exc).__name__, exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    print(result["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
