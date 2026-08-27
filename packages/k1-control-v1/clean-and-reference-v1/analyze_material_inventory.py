"""Extract only CFS slot material labels from a private read-only capture."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Dict, Iterable, Mapping


SLOTS = ("A", "B", "C", "D")
UNITS = ("T1", "T2")


class InventoryError(ValueError):
    pass


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise InventoryError("object_required:%s" % path)
    return value


def _marked_block(lines: Iterable[str], name: str) -> str:
    values = list(lines)
    begin = "=== %s_BEGIN ===" % name
    end = "=== %s_END ===" % name
    if values.count(begin) != 1 or values.count(end) != 1:
        raise InventoryError("capture_block_invalid:%s" % name)
    start = values.index(begin) + 1
    stop = values.index(end)
    if stop <= start:
        raise InventoryError("capture_block_empty:%s" % name)
    return "\n".join(values[start:stop])


def _slot_materials(value: Any, path: str) -> Dict[str, str]:
    if not isinstance(value, list) or len(value) != len(SLOTS):
        raise InventoryError("material_type_shape_invalid:%s" % path)
    result: Dict[str, str] = {}
    for slot, material in zip(SLOTS, value):
        if material is None:
            result[slot] = "EMPTY_OR_UNKNOWN"
        elif isinstance(material, str) and material.strip():
            result[slot] = material.strip().upper()
        else:
            raise InventoryError("material_type_value_invalid:%s.%s" % (path, slot))
    return result


def safe_projection(payload: Mapping[str, Any]) -> Dict[str, Any]:
    result = _mapping(payload.get("result"), "result")
    status = _mapping(result.get("status"), "result.status")
    box = _mapping(status.get("box"), "result.status.box")
    projection: Dict[str, Any] = {
        "box_state": box.get("state"),
        "active_command": box.get("t_command"),
        "units": {},
    }
    for unit_name in UNITS:
        unit = _mapping(box.get(unit_name), "box.%s" % unit_name)
        projection["units"][unit_name] = {
            "state": unit.get("state"),
            "engaged_slot": unit.get("filament"),
            "materials": _slot_materials(
                unit.get("material_type"), "box.%s.material_type" % unit_name
            ),
        }
    return projection


def analyze_capture(path: Path) -> Dict[str, Any]:
    lines = path.read_text(encoding="utf-8-sig", errors="strict").splitlines()
    projections = [
        safe_projection(json.loads(_marked_block(lines, name)))
        for name in ("STATE_1", "STATE_2")
    ]
    if projections[0] != projections[1]:
        raise InventoryError("material_inventory_not_stable")
    return {
        "schema": 1,
        "status": "MATERIAL_INVENTORY_READ_ONLY_OK",
        "stable_reads": 2,
        "inventory": projections[0],
        "identity_fields_exported": False,
        "printer_effect": False,
        "previous_nozzle_material_proven": False,
    }


def main(argv=None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 1:
        print("usage: analyze_material_inventory.py <private-capture>", file=sys.stderr)
        return 2
    try:
        result = analyze_capture(Path(arguments[0]))
    except Exception as exc:
        print(json.dumps({"status": "MATERIAL_INVENTORY_KO", "error": "%s:%s" % (type(exc).__name__, exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    print(result["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
