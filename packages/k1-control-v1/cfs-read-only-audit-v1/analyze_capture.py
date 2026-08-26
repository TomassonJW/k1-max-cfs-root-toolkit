from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROBUST_PROFILE = "k1_p001_t055_r001_n06x06"


def _section(text: str, name: str) -> str:
    start = f"=== {name}_BEGIN ==="
    end = f"=== {name}_END ==="
    if start not in text or end not in text:
        raise ValueError(f"section absente: {name}")
    return text.split(start, 1)[1].split(end, 1)[0].strip()


def _first_json(text: str) -> Any:
    decoder = json.JSONDecoder()
    for match in re.finditer(r"[\[{]", text):
        try:
            return decoder.raw_decode(text[match.start() :])[0]
        except json.JSONDecodeError:
            continue
    raise ValueError("aucun document JSON lisible")


def _hashes(text: str, name: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for digest, path in re.findall(
        r"(?m)^([0-9a-f]{64})\s+(.+)$", _section(text, name)
    ):
        result[path.strip()] = digest
    if not result:
        raise ValueError(f"aucune empreinte dans {name}")
    return result


def _status(text: str, name: str) -> dict[str, Any]:
    document = _first_json(_section(text, name))
    return document["result"]["status"]


def _sensor(status: dict[str, Any], name: str) -> dict[str, Any]:
    key = f"filament_switch_sensor {name}"
    value = status.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"objet absent: {key}")
    return value


def classify_filament_state(*, presence_observed: bool, route_resolved: bool) -> str:
    if presence_observed and not route_resolved:
        return "engaged_unknown"
    if presence_observed and route_resolved:
        return "engaged_known"
    if not presence_observed and route_resolved:
        return "fault"
    return "unknown"


def _assert_safe(status: dict[str, Any], label: str) -> None:
    checks = {
        "imprimante au repos": status["print_stats"]["state"] == "standby",
        "buse sans cible": float(status["extruder"]["target"]) == 0.0,
        "plateau sans cible": float(status["heater_bed"]["target"]) == 0.0,
        "axes liberes": status["toolhead"]["homed_axes"] in ("", []),
        "profil robuste actif": status["bed_mesh"]["profile_name"] == ROBUST_PROFILE,
        "CFS connecte": status["box"]["state"] == "connect",
        "mouvements bas desarmes": int(status["gcode_macro KCTRL_STATE"]["low_moves_armed"]) == 0,
        "stockage Z integre": status["k1_control_store"]["integrity"] == "ok",
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise ValueError(f"etat final non sur ({label}): {', '.join(failed)}")


def analyze(capture_path: Path) -> dict[str, Any]:
    text = capture_path.read_text(encoding="utf-8", errors="replace")
    if "CFS_READ_ONLY_AUDIT_OK" not in text:
        raise ValueError("marqueur final absent")

    baseline_hashes = _hashes(text, "BASELINE_HASHES")
    final_hashes = _hashes(text, "FINAL_HASHES")
    if baseline_hashes != final_hashes:
        raise ValueError("les empreintes K1 ont change pendant l'audit")

    initial = _status(text, "OBJECT_QUERY")
    final = _status(text, "FINAL_OBJECT_QUERY")
    _assert_safe(initial, "debut")
    _assert_safe(final, "fin")

    sensor_1 = _sensor(final, "filament_sensor")
    sensor_2 = _sensor(final, "filament_sensor_2")
    box = final["box"]
    tn_data = _first_json(_section(text, "PERSISTED_TN_DATA"))

    current_route_keys = {
        key
        for key in ("tnn_map", "last_cmd", "last_tnn")
        if key in tn_data and tn_data[key] not in (None, "", {}, [])
    }
    t_command = box.get("t_command")
    presence_observed = bool(sensor_1.get("filament_detected")) or bool(
        sensor_2.get("filament_detected")
    )
    route_resolved = bool(t_command) or bool(current_route_keys)

    classification = classify_filament_state(
        presence_observed=presence_observed,
        route_resolved=route_resolved,
    )

    if classification != "engaged_unknown":
        raise ValueError(f"classement inattendu pour cette capture: {classification}")

    units = {
        key: value.get("state")
        for key, value in box.items()
        if re.fullmatch(r"T[1-4]", key) and isinstance(value, dict)
    }
    if units.get("T1") != "connect" or units.get("T2") != "connect":
        raise ValueError("les deux CFS ne sont pas confirmes connectes")

    return {
        "schema": "k1-control-cfs-read-only-audit-v1",
        "capture": str(capture_path),
        "result": "ok",
        "printer_unchanged": True,
        "safe_final_state": True,
        "classification": classification,
        "presence": {
            "observed": presence_observed,
            "filament_sensor": sensor_1,
            "filament_sensor_2": sensor_2,
        },
        "identity": {"resolved": False},
        "route": {
            "resolved": route_resolved,
            "t_command": t_command,
            "persisted_current_route_keys": sorted(current_route_keys),
        },
        "nozzle_flow": {"proven": False, "reason": "aucune purge visible"},
        "cfs_units": units,
        "active_profile": final["bed_mesh"]["profile_name"],
        "accepted_z": final["gcode_macro KCTRL_STATE"].get("accepted_z_offset"),
        "baseline_hashes": baseline_hashes,
        "final_hashes": final_hashes,
        "physical_follow_up_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = analyze(args.capture.resolve())
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    print("AUDIT_CFS_READ_ONLY_V1_OK classification=engaged_unknown")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
