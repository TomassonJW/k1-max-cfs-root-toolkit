"""Build the empty-spool catalogue shipped with the spool manager.

Document 102, lot B. Reads a SpoolmanDB checkout (Donkie/SpoolmanDB on
GitHub, MIT licence) and writes `tares.json`: one entry per manufacturer,
nominal net weight, empty spool weight and spool material, with the product
lines that share them and each line's density. Entries without an empty
spool weight are dropped, and so are lines not sold in 1.75 mm; colours,
temperatures and everything else stay upstream. Run by hand on the
workstation when the catalogue is refreshed, never on the K1:

    python -I build_tares.py <checkout> <commit sha> <output>

The licence travels with the file as LICENSE-SpoolmanDB.txt.
"""

from __future__ import annotations

import glob
import json
import os
import re
import sys
from typing import Any, Dict, List, Tuple

SPOOL_MATERIALS = {"plastic": "plastique", "cardboard": "carton", "metal": "métal"}
DIAMETER = 1.75


def line_name(name: str, material: str) -> str:
    text = re.sub(r"\s+", " ", name.replace("{color_name}", " ")).strip(" -")
    if not text:
        return material
    if material and material.lower() not in text.lower():
        return "%s %s" % (text, material)
    return text


def _number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return float(value)


def build(checkout: str, commit: str) -> Dict[str, Any]:
    groups = {}  # type: Dict[Tuple[str, float, float, str], Dict[str, Any]]
    for path in sorted(glob.glob(os.path.join(checkout, "filaments", "*.json"))):
        with open(path, encoding="utf-8") as stream:
            document = json.load(stream)
        manufacturer = str(document.get("manufacturer", "")).strip()
        if not manufacturer:
            continue
        for filament in document.get("filaments", []):
            diameters = filament.get("diameters") or [DIAMETER]
            if not any(abs(_number(value) - DIAMETER) < 0.01 for value in diameters):
                continue
            material = str(filament.get("material", "")).strip()
            name = line_name(str(filament.get("name", "")), material)
            density = _number(filament.get("density"))
            for weight in filament.get("weights", []):
                net = _number(weight.get("weight"))
                tare = _number(weight.get("spool_weight"))
                if net <= 0 or tare <= 0:
                    continue
                kind = SPOOL_MATERIALS.get(str(weight.get("spool_type")), "inconnue")
                key = (manufacturer, net, tare, kind)
                group = groups.setdefault(key, {"lines": {}})
                group["lines"][(name, material, density)] = None
    entries = []  # type: List[Dict[str, Any]]
    for (manufacturer, net, tare, kind), group in sorted(
            groups.items(), key=lambda item: (item[0][0].lower(), item[0][1], item[0][2], item[0][3])):
        lines = [{"name": name, "material": material, "density": density}
                 for name, material, density in sorted(group["lines"], key=lambda line: (
                     line[0].lower(), line[1], line[2]))]
        entries.append({
            "key": "%s|%g|%g|%s" % (manufacturer, net, tare, kind),
            "manufacturer": manufacturer,
            "net_g": net,
            "tare_g": tare,
            "spool_material": kind,
            "lines": lines,
        })
    return {
        "format": "kctrl_spools.tares",
        "source": "SpoolmanDB",
        "commit": commit,
        "license": "MIT",
        "copyright": "Copyright (c) 2024 Donkie",
        "entries": entries,
    }


def main(argv: List[str]) -> int:
    if len(argv) != 3:
        sys.stderr.write(__doc__)
        return 2
    checkout, commit, output = argv
    if not re.match(r"^[0-9a-f]{40}$", commit):
        sys.stderr.write("commit attendu : 40 caractères hexadécimaux\n")
        return 2
    catalogue = build(checkout, commit)
    with open(output, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(catalogue, stream, ensure_ascii=False, sort_keys=True, indent=1)
        stream.write("\n")
    print("%d entrées, %d gammes" % (len(catalogue["entries"]),
                                    sum(len(entry["lines"]) for entry in catalogue["entries"])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
