"""The spool library: empty spools, filament records, spools and the calculator.

Document 102, lots B to E, plus the half of lot F that needs no socket: what a
slot shows, which spool Thomas expects there, and what a write to the CFS
would change. Everything here works on the library dictionary that
kctrl_spools_store keeps on disk. Nothing opens a socket, the time always
comes in as an argument, and the only files read are the firmware's material
database and the tail of a sliced file, both bounded.

The Moonraker component applies an action to a copy of the library, checks
the copy, saves it and only then swaps it in: a refused action or a failed
save leaves the library as it was. Mainsail computes the same figures with
spools-logic.js, the same formulas in the same order and the same rounding;
calculator-vectors.json pins both sides.

The CFS knows a slot's material id and colour, nothing else. Weights, tares,
places and the remaining filament live here. Presence comes from the CFS,
the identity of a spool from here: a slot that shows another material or
colour than the spool expected there is "à vérifier", and Thomas decides.
"""

from __future__ import annotations

import copy
import json
import math
import os
import re
from typing import Any, Dict, List, Optional, Tuple

SCHEMA = 1
BOXES = ("1", "2", "3", "4")
SLOTS = ("A", "B", "C", "D")
SLOT_NAMES = tuple("T" + box + slot for box in BOXES for slot in SLOTS)
# Where a spool is. "a_ranger" is out of the CFS with no place said yet.
STATES = ("cfs", "a_ranger", "stock", "terminee", "jetee")
ARCHIVED = ("terminee", "jetee")
# What the remaining weight was last set from: a new spool's nominal net, an
# estimate by eye (net grams), or a weighing (gross grams, the tare comes off
# when it is read, so a corrected tare corrects every weighing).
BASES = ("neuve", "estimation", "pesee")
TARE_SOURCES = ("spoolmandb", "pesee", "manuel")
SPOOL_MATERIALS = ("plastique", "carton", "métal", "inconnue")
DIAMETER = 1.75
PRINTS_KEPT = 20
UNASSIGNED_KEPT = 50
CANDIDATES_SHOWN = 8
NAME_LIMIT = 80
NOTES_LIMIT = 500
# The firmware writes -1 in an empty slot; T3 and T4, absent, publish None.
EMPTY_MATERIALS = ("-1", "None", "")
# vender is "none" in an empty slot, "unknown" for a spool without a chip and
# -1 when the unit is absent; anything else names the maker the chip gave.
NO_CHIP = ("none", "unknown", "-1", "None", "")
COLOUR_HEX = re.compile(r"[0-9A-F]{6}")
CREALITY_ID = re.compile(r"[0-9A-Za-z]{5}")
SLOT_MATERIAL = re.compile(r"0[0-9A-Za-z]{5}")
SLOT_COLOUR = re.compile(r"0[0-9a-f]{6}")
CONTROL = re.compile(r"[\x00-\x09\x0b-\x1f\x7f]")
IDS = {"empty_spools": "V", "filaments": "F", "spools": "B"}
COUNTERS = {"empty_spools": "empty", "filaments": "filament", "spools": "spool"}
# Orca writes the job's consumption per filament above its config block:
# "; filament used [mm] = 6847.96, 0.00" and "; filament used [g] = 20.59, 0.00".
PLANNED_KEYS = {b"; filament used [mm] =": "mm", b"; filament used [g] =": "g"}
TAIL_LIMIT = 1 << 19

LABELS = {
    "manufacturer": "fabricant", "name": "nom", "spool_material": "matière de la bobine",
    "tare_g": "tare", "nominal_net_g": "net nominal", "source": "origine de la tare",
    "catalogue": "référence SpoolmanDB", "notes": "notes", "material": "matière",
    "colour": "couleur", "diameter_mm": "diamètre", "density": "densité",
    "creality_id": "fiche matériau Creality", "filament": "fiche filament",
    "empty_spool": "bobine vide", "initial_net_g": "net initial",
    "basis_kind": "type de reste", "kind": "type de reste", "value_g": "valeur",
    "state": "état", "slot": "emplacement", "place": "lieu", "id": "numéro",
    "segment": "segment", "spool": "bobine", "cut_loss_mm": "perte de coupe",
    "low_g": "seuil de bobine basse",
}


class ModelError(ValueError):
    """An action refused; the message is shown to Thomas as it is."""


# ---------------------------------------------------------------- calculator
def round_half_away(value: float, digits: int = 0) -> float:
    """Round half away from zero, identical in Python and in spools-logic.js.

    round() rounds half to even and Math.round rounds half up, so neither is
    used: 2.5 g is 3 g on both sides and -2.5 is -3. Never returns -0.0, which
    JSON would carry as "-0.0" on one side and 0 on the other.
    """
    scale = 10 ** digits
    result = math.floor(abs(value) * scale + 0.5) / scale
    if result == 0:
        return 0.0
    return -result if value < 0 else result


def grams_per_metre(density: float, diameter: float) -> float:
    """g per metre of filament: density in g/cm3, diameter in mm.

    A metre of 1.75 mm filament is pi x 0.875 x 0.875 x 1000 mm3, that is
    2.405 cm3; at 1.24 g/cm3 that is 2.98 g.
    """
    radius = diameter / 2.0
    return density * math.pi * radius * radius


def net_of_gross(gross_g: float, tare_g: float) -> float:
    if gross_g < tare_g:
        raise ModelError("poids brut %s g inférieur à la tare %s g de la bobine vide : "
                         "vérifier la pesée ou le type de bobine vide"
                         % (_figure(gross_g), _figure(tare_g)))
    return gross_g - tare_g


def percent_of(net_g: float, initial_g: float) -> float:
    return net_g / initial_g * 100.0


def net_of_percent(percent: float, initial_g: float) -> float:
    return percent * initial_g / 100.0


def length_of(net_g: float, gpm: float) -> float:
    return net_g / gpm


def net_of_length(metres: float, gpm: float) -> float:
    return metres * gpm


def grams_of_mm(mm: float, gpm: float) -> float:
    return mm / 1000.0 * gpm


def shown(net_g: float, initial_g: float, gpm: float) -> Dict[str, Optional[float]]:
    """What the window shows for a remaining net: grams, percent, metres.

    Whole grams and percent; metres whole, with one decimal under ten metres,
    where a single metre is a third of the spool's end.
    """
    percent = round_half_away(percent_of(net_g, initial_g), 0) if initial_g > 0 else None
    metres = None  # type: Optional[float]
    if gpm > 0:
        length = length_of(net_g, gpm)
        metres = round_half_away(length, 1 if length < 10 else 0)
    return {"g": round_half_away(net_g, 0), "percent": percent, "m": metres}


def _figure(value: float) -> str:
    rounded = round_half_away(value, 1)
    return ("%d" % rounded) if rounded == int(rounded) else ("%.1f" % rounded).replace(".", ",")


# ---------------------------------------------------------------- CFS values
def colour_key(text: Any) -> str:
    """Six upper-case hex digits, or ''. Same rule as kctrl_slot_map.colour_key.

    The CFS publishes '0ff1e1e', the sliced file '#FF1E1E', the window
    'ff1e1e': all three compare as 'FF1E1E'. '-1', 'None' and '' match nothing.
    """
    value = str(text if text is not None else "").strip().lstrip("#").upper()
    if len(value) == 7 and value[0] == "0":
        value = value[1:]
    return value if COLOUR_HEX.fullmatch(value) else ""


def material_key(slot_type: Any) -> str:
    """The database id of a slot's material: 000001 is record 00001."""
    text = str(slot_type)
    if len(text) == 6 and text.startswith("0"):
        return text[1:]
    return text


def slot_material(creality_id: str) -> str:
    return "0" + creality_id


def slot_colour(colour: str) -> str:
    return "0" + colour.lower()


def chip_remaining(vender: Any, remain: Any) -> Optional[int]:
    """What a chip says is left, in percent, or None for a spool without one.

    remain_len comes from the CFS reading the chip; a chipless spool shows 100
    there, which measures nothing, so it is only kept when vender names a maker.
    """
    if str(vender) in NO_CHIP:
        return None
    try:
        value = int(float(str(remain)))
    except (TypeError, ValueError):
        return None
    return value if 0 <= value <= 100 else None


def _item(values: Any, index: int) -> str:
    try:
        return str(values[index])
    except (IndexError, KeyError, TypeError):
        return ""


def observe_box(box: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """{slot: observation} from the box object's status.

    Only the fields named here are read: the units also publish their serial
    number and uuid, which are never read, kept, logged or shown.
    """
    found = {}
    for number in BOXES:
        unit = box.get("T" + number) or {}
        if not isinstance(unit, dict):
            unit = {}
        connected = str(unit.get("state", "None")) == "connect"
        for index, letter in enumerate(SLOTS):
            material = _item(unit.get("material_type"), index)
            present = connected and material not in EMPTY_MATERIALS
            found["T" + number + letter] = {
                "connected": connected,
                "present": present,
                "material": material if present else "",
                "colour": colour_key(_item(unit.get("color_value"), index)) if present else "",
                "chip": chip_remaining(_item(unit.get("vender"), index),
                                       _item(unit.get("remain_len"), index)) if present else None,
            }
    return found


def read_materials(path: str) -> Tuple[Dict[str, Dict[str, Any]], str]:
    """({id: record}, error) from the firmware's material database.

    Same file and same layout as kctrl_slot_map.read_material_records reads:
    result.list[].base, the type under the firmware's own spelling
    meterialType. Only what a filament record needs is kept.
    """
    try:
        with open(path, encoding="utf-8") as stream:
            data = json.load(stream)
    except (OSError, ValueError) as exception:
        return {}, "base matériau de la K1 illisible : %s" % exception
    records = data.get("result", {}).get("list") if isinstance(data, dict) else None
    if not isinstance(records, list):
        return {}, "base matériau de la K1 sans liste de fiches"
    found = {}
    for record in records:
        base = record.get("base") if isinstance(record, dict) else None
        if not isinstance(base, dict):
            continue
        ident = str(base.get("id") or "")
        kind = str(base.get("meterialType") or "").strip().upper()
        if not CREALITY_ID.fullmatch(ident) or not kind:
            continue
        found[ident] = {
            "id": ident,
            "brand": str(base.get("brand") or "").strip(),
            "name": str(base.get("name") or "").strip(),
            "type": kind,
            "density": _loose_number(base.get("density")),
            "diameter": _loose_number(base.get("diameter")),
        }
    if not found:
        return {}, "base matériau de la K1 sans fiche exploitable"
    return found, ""


def _loose_number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def _fold(text: str) -> str:
    return re.sub(r"[^0-9a-z]", "", text.casefold())


def suggest_creality_id(manufacturer: str, material: str, name: str,
                        materials: Dict[str, Dict[str, Any]]) -> str:
    """The material record a new filament record should point at, or ''.

    The maker's own record of that type when it has exactly one; among
    several, the one whose name the filament's name contains ("Hyper PLA");
    otherwise the Generic record of the type. Same rule in spools-logic.js.
    Any record of the right type loads at the right temperature, since the
    tool change aligns the record to the file; what the id changes is which
    spools the firmware treats as twins for its automatic refill.
    """
    kind = material.strip().upper()
    if not kind:
        return ""
    same = sorted((record for record in materials.values() if record["type"] == kind),
                  key=lambda record: record["id"])
    brand = _fold(manufacturer)
    mine = [record for record in same if brand and _fold(record["brand"]) == brand]
    if len(mine) == 1:
        return mine[0]["id"]
    if mine:
        label = _fold(name)
        named = [record for record in mine if _fold(record["name"]) and _fold(record["name"]) in label]
        if len(named) == 1:
            return named[0]["id"]
    generic = [record for record in same if _fold(record["brand"]) == "generic"]
    return generic[0]["id"] if generic else ""


def read_planned(path: str, limit: int = TAIL_LIMIT) -> Tuple[List[Dict[str, float]], str]:
    """([{mm, g}] per filament in slicer order, note) from a sliced file's tail."""
    try:
        with open(path, "rb") as stream:
            stream.seek(0, os.SEEK_END)
            size = stream.tell()
            stream.seek(max(0, size - limit))
            tail = stream.read()
    except OSError as exception:
        return [], "fichier illisible : %s" % exception
    found = {}  # type: Dict[str, List[float]]
    for raw in tail.split(b"\n"):
        line = raw.strip()
        for prefix, name in PLANNED_KEYS.items():
            if line.startswith(prefix):
                values = []
                for item in line[len(prefix):].decode("ascii", "replace").split(","):
                    number = _loose_number(item.strip())
                    values.append(number if number is not None else 0.0)
                found[name] = values
    if "mm" not in found:
        return [], "pas de consommation prévue en fin de fichier"
    planned = []
    for index, mm in enumerate(found["mm"]):
        grams = found.get("g", [])
        planned.append({"mm": mm, "g": grams[index] if index < len(grams) else 0.0})
    return planned, "%d filament(s) prévu(s)" % len(planned)


# ---------------------------------------------------------------- library
def empty_library() -> Dict[str, Any]:
    return {
        "schema": SCHEMA,
        "counters": {"empty": 0, "filament": 0, "spool": 0, "segment": 0},
        "empty_spools": {},
        "filaments": {},
        "spools": {},
        "slots": {},
        "pending_cfs": {},
        "prints": [],
        "unassigned": [],
        "settings": {"cut_loss_mm": 0.0, "low_g": 100.0},
    }


def normalise(library: Dict[str, Any]) -> Dict[str, Any]:
    """Fill the keys a library of this schema may lack; nothing is changed."""
    blank = empty_library()
    for key, value in blank.items():
        if key not in library:
            library[key] = value
    for key in ("counters", "settings"):
        if isinstance(library[key], dict):
            for name, value in blank[key].items():
                library[key].setdefault(name, value)
    return library


def label(spool_id: str) -> str:
    return "%s-%s" % (spool_id[:1], spool_id[1:]) if spool_id else ""


def _number_of(ident: str, prefix: str) -> int:
    if len(ident) < 4 or not ident.startswith(prefix) or not ident[1:].isdigit():
        return -1
    return int(ident[1:])


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def check(library: Any) -> List[str]:
    """Every inconsistency found, empty when the library can be used."""
    if not isinstance(library, dict):
        return ["bibliothèque : objet attendu"]
    errors = []  # type: List[str]
    if library.get("schema") != SCHEMA:
        errors.append("schéma %r inattendu" % library.get("schema"))
    for key, kind in (("counters", dict), ("empty_spools", dict), ("filaments", dict),
                      ("spools", dict), ("slots", dict), ("pending_cfs", dict),
                      ("prints", list), ("unassigned", list), ("settings", dict)):
        if not isinstance(library.get(key), kind):
            errors.append("%s absent ou mal formé" % key)
    if errors:
        return errors
    counters = library["counters"]
    for name in ("empty", "filament", "spool", "segment"):
        if not isinstance(counters.get(name), int) or counters[name] < 0:
            errors.append("compteur %s mal formé" % name)
    if errors:
        return errors
    for collection, prefix in IDS.items():
        for ident, record in library[collection].items():
            number = _number_of(ident, prefix)
            if number < 1 or not isinstance(record, dict) or record.get("id") != ident:
                errors.append("%s : numéro %r mal formé" % (collection, ident))
            elif number > counters[COUNTERS[collection]]:
                errors.append("%s : %s au-delà du compteur" % (collection, ident))
    if errors:
        return errors
    for ident, empty in library["empty_spools"].items():
        if (not _is_number(empty.get("tare_g")) or empty["tare_g"] <= 0
                or not _is_number(empty.get("nominal_net_g")) or empty["nominal_net_g"] <= 0
                or empty.get("source") not in TARE_SOURCES
                or empty.get("spool_material") not in SPOOL_MATERIALS
                or not isinstance(empty.get("manufacturer"), str)):
            errors.append("bobine vide %s mal formée" % ident)
    for ident, fiche in library["filaments"].items():
        if (not isinstance(fiche.get("creality_id"), str) or not CREALITY_ID.fullmatch(fiche["creality_id"])
                or not _is_number(fiche.get("density")) or fiche["density"] <= 0
                or not _is_number(fiche.get("diameter_mm")) or fiche["diameter_mm"] <= 0
                or not COLOUR_HEX.fullmatch(str(fiche.get("colour", "")))
                or not isinstance(fiche.get("material"), str) or not fiche["material"]):
            errors.append("fiche %s mal formée" % ident)
    held = {}  # type: Dict[str, str]
    for ident, spool in library["spools"].items():
        basis = spool.get("basis")
        if (spool.get("filament") not in library["filaments"]
                or (spool.get("empty_spool") and spool["empty_spool"] not in library["empty_spools"])
                or not isinstance(spool.get("empty_spool"), str)
                or spool.get("state") not in STATES
                or not _is_number(spool.get("initial_net_g")) or spool["initial_net_g"] <= 0
                or not _is_number(spool.get("counted_g")) or spool["counted_g"] < 0
                or not isinstance(basis, dict) or basis.get("kind") not in BASES
                or not _is_number(basis.get("value_g"))
                or (basis["kind"] == "pesee" and not spool.get("empty_spool"))):
            errors.append("bobine %s mal formée" % ident)
            continue
        slot = spool.get("slot")
        if spool["state"] == "cfs":
            if slot not in SLOT_NAMES:
                errors.append("bobine %s au CFS sans emplacement" % ident)
            elif slot in held:
                errors.append("%s et %s dans le même emplacement %s" % (held[slot], ident, slot))
            else:
                held[slot] = ident
        elif slot:
            errors.append("bobine %s hors CFS avec un emplacement" % ident)
    for slot, record in library["slots"].items():
        if slot not in SLOT_NAMES or not isinstance(record, dict):
            errors.append("emplacement %r mal formé" % slot)
    for slot, pending in library["pending_cfs"].items():
        if slot not in SLOT_NAMES or not isinstance(pending, dict) \
                or pending.get("spool") not in library["spools"]:
            errors.append("écriture en attente %r mal formée" % slot)
    if len(library["prints"]) > PRINTS_KEPT or not all(
            isinstance(item, dict) and isinstance(item.get("job"), str) for item in library["prints"]):
        errors.append("impressions mal formées")
    if len(library["unassigned"]) > UNASSIGNED_KEPT or not all(
            isinstance(item, dict) and isinstance(item.get("id"), str) and _is_number(item.get("mm"))
            for item in library["unassigned"]):
        errors.append("segments à attribuer mal formés")
    settings = library["settings"]
    if not _is_number(settings.get("cut_loss_mm")) or not _is_number(settings.get("low_g")):
        errors.append("réglages mal formés")
    return errors


# ---------------------------------------------------------------- reading
def linked(library: Dict[str, Any], slot: str) -> Optional[Dict[str, Any]]:
    for spool in library["spools"].values():
        if spool["state"] == "cfs" and spool["slot"] == slot:
            return spool
    return None


def fiche_gpm(fiche: Dict[str, Any]) -> float:
    return grams_per_metre(fiche["density"], fiche["diameter_mm"])


def basis_net(library: Dict[str, Any], spool: Dict[str, Any]) -> Optional[float]:
    basis = spool["basis"]
    if basis["kind"] == "neuve":
        return spool["initial_net_g"]
    if basis["kind"] == "estimation":
        return basis["value_g"]
    empty = library["empty_spools"].get(spool["empty_spool"])
    if empty is None:
        return None
    return basis["value_g"] - empty["tare_g"]


def remaining_of(library: Dict[str, Any], spool: Dict[str, Any]) -> Dict[str, Any]:
    """What is left on a spool: the basis net minus what was counted since."""
    fiche = library["filaments"][spool["filament"]]
    gpm = fiche_gpm(fiche)
    net = basis_net(library, spool)
    if net is None:
        return {"net_g": None, "exhausted": False, "shown": None, "gross_g": None}
    left = net - spool["counted_g"]
    exhausted = left < 0
    left = max(0.0, left)
    empty = library["empty_spools"].get(spool["empty_spool"])
    return {
        "net_g": round_half_away(left, 2),
        "exhausted": exhausted,
        "shown": shown(left, spool["initial_net_g"], gpm),
        "gross_g": round_half_away(left + empty["tare_g"], 0) if empty else None,
    }


def counting_verified(library: Dict[str, Any]) -> bool:
    """True once a weighing has checked a counted consumption."""
    return any(spool.get("last_gap") and spool["last_gap"].get("counted_g", 0) > 0
               for spool in library["spools"].values())


def spool_view(library: Dict[str, Any], spool: Dict[str, Any]) -> Dict[str, Any]:
    remaining = remaining_of(library, spool)
    view = copy.deepcopy(spool)
    view["label"] = label(spool["id"])
    view["remaining"] = remaining
    view["low"] = remaining["net_g"] is not None and remaining["net_g"] < library["settings"]["low_g"]
    return view


def same_identity(fiche: Dict[str, Any], observation: Dict[str, Any]) -> bool:
    return (observation["material"] == slot_material(fiche["creality_id"])
            and observation["colour"] == fiche["colour"])


def candidates(library: Dict[str, Any], observation: Dict[str, Any],
               materials: Dict[str, Dict[str, Any]]) -> List[str]:
    """Spools out of the CFS that could be the one just put in, best first.

    Same material id and colour first, then same type and colour; among them
    the spools just taken out of the CFS before those in stock, the most
    recently touched first. Never more than eight, never linked on its own.
    """
    kind = (materials.get(material_key(observation["material"])) or {}).get("type", "")
    scored = []
    for spool in library["spools"].values():
        if spool["state"] not in ("a_ranger", "stock"):
            continue
        fiche = library["filaments"][spool["filament"]]
        if fiche["colour"] != observation["colour"]:
            continue
        if same_identity(fiche, observation):
            rank = 0
        elif kind and fiche["material"] == kind:
            rank = 1
        else:
            continue
        scored.append((rank, 0 if spool["state"] == "a_ranger" else 1, -spool["updated"], spool["id"]))
    return [item[3] for item in sorted(scored)[:CANDIDATES_SHOWN]]


def refill_impact(observations: Dict[str, Dict[str, Any]], slot: str,
                  material: str, colour: str) -> Dict[str, List[str]]:
    """Which slots the firmware would pair with `slot` for its automatic refill.

    Its groups are same material id and same colour (same_material in the box
    status); writing another identity makes some partners and loses others.
    """
    def partners(identity: Tuple[str, str]) -> List[str]:
        return sorted(name for name, seen in observations.items()
                      if name != slot and seen.get("present")
                      and (seen["material"], seen["colour"]) == identity)

    current = observations.get(slot) or {}
    before = set(partners((current.get("material", ""), current.get("colour", ""))))
    after = set(partners((material, colour)))
    return {"gained": sorted(after - before), "lost": sorted(before - after),
            "partners": sorted(after)}


def write_plan(library: Dict[str, Any], slot: str,
               observations: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """What `KCTRL_FILAMENT` must send so the slot shows its spool's identity.

    Only the parts that differ are sent. A slot the CFS shows empty is never
    written: a material id there would make the start window, and the
    firmware, believe a spool is loaded.
    """
    if slot not in SLOT_NAMES:
        raise ModelError("emplacement inconnu : %s" % slot)
    spool = linked(library, slot)
    if spool is None:
        raise ModelError("aucune bobine attendue en %s" % slot)
    observation = observations.get(slot)
    if not observation or not observation["connected"]:
        raise ModelError("unité du CFS de %s non connectée" % slot)
    if not observation["present"]:
        raise ModelError("%s est vide au CFS : mettre la bobine d'abord" % slot)
    fiche = library["filaments"][spool["filament"]]
    material = slot_material(fiche["creality_id"])
    plan = {
        "slot": slot,
        "spool": spool["id"],
        "material": material if observation["material"] != material else None,
        "colour": slot_colour(fiche["colour"]) if observation["colour"] != fiche["colour"] else None,
        "impact": refill_impact(observations, slot, material, fiche["colour"]),
    }
    return plan


def gcode_of_plan(plan: Dict[str, Any]) -> str:
    """The one command a write sends, its values checked character by character."""
    if plan.get("slot") not in SLOT_NAMES:
        raise ModelError("emplacement inconnu : %r" % plan.get("slot"))
    parts = ["KCTRL_FILAMENT SLOT=%s" % plan["slot"]]
    if plan.get("material") is not None:
        if not SLOT_MATERIAL.fullmatch(str(plan["material"])):
            raise ModelError("matériau mal formé : %r" % plan["material"])
        parts.append("MATERIAL=%s" % plan["material"])
    if plan.get("colour") is not None:
        if not SLOT_COLOUR.fullmatch(str(plan["colour"])):
            raise ModelError("couleur mal formée : %r" % plan["colour"])
        parts.append("COLOR=%s" % plan["colour"])
    if len(parts) == 1:
        raise ModelError("rien à écrire en %s : le CFS montre déjà cette bobine" % plan["slot"])
    return " ".join(parts)


def readback_ok(plan: Dict[str, Any], observation: Dict[str, Any]) -> bool:
    if not observation or not observation.get("present"):
        return False
    if plan.get("material") is not None and observation["material"] != plan["material"]:
        return False
    if plan.get("colour") is not None and observation["colour"] != colour_key(plan["colour"]):
        return False
    return True


def slot_views(library: Dict[str, Any], observations: Dict[str, Dict[str, Any]],
               materials: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One line per slot of a connected unit, or of a slot with a spool expected."""
    views = []
    for slot in SLOT_NAMES:
        observation = observations.get(slot) or {
            "connected": False, "present": False, "material": "", "colour": "", "chip": None}
        spool = linked(library, slot)
        pending = library["pending_cfs"].get(slot)
        if not observation["connected"] and spool is None and pending is None:
            continue
        record = library["slots"].get(slot) or {}
        view = {
            "slot": slot,
            "observed": dict(observation, type=(materials.get(material_key(observation["material"]))
                                                or {}).get("type", "") if observation["present"] else ""),
            "spool": spool["id"] if spool else "",
            "pending": copy.deepcopy(pending),
            "last_write": copy.deepcopy(record.get("last_write")),
            "candidates": [],
            "plan": None,
        }
        if not observation["connected"]:
            status = "hors_ligne"
        elif pending is not None:
            status = "en_attente_cfs"
        elif spool is None:
            status = "inconnue" if observation["present"] else "vide"
            if observation["present"]:
                view["candidates"] = candidates(library, observation, materials)
        elif not observation["present"]:
            status = "attendue"
        elif same_identity(library["filaments"][spool["filament"]], observation):
            status = "ok"
        else:
            status = "a_verifier"
            view["plan"] = write_plan(library, slot, observations)
        view["status"] = status
        views.append(view)
    return views


def attention(library: Dict[str, Any], views: List[Dict[str, Any]]) -> List[str]:
    """What the badge on the Bobines button counts, one line each."""
    items = []
    for view in views:
        if view["status"] == "a_verifier":
            items.append("%s à vérifier" % view["slot"])
        elif view["status"] == "inconnue":
            items.append("%s : bobine inconnue" % view["slot"])
        last = view.get("last_write") or {}
        if last.get("result") not in (None, "ok") and view["status"] != "ok":
            items.append("%s : écriture au CFS non confirmée" % view["slot"])
        spool = library["spools"].get(view["spool"]) if view["spool"] else None
        if spool is not None:
            remaining = remaining_of(library, spool)
            if remaining["net_g"] is not None and remaining["net_g"] < library["settings"]["low_g"]:
                items.append("%s : %s basse (%d g)" % (view["slot"], label(spool["id"]),
                                                      remaining["shown"]["g"]))
    if library["unassigned"]:
        count = len(library["unassigned"])
        items.append("%d consommation%s à attribuer" % (count, "s" if count > 1 else ""))
    return items


# ---------------------------------------------------------------- parameters
def _only(params: Dict[str, Any], allowed: Tuple[str, ...]) -> None:
    for key in params:
        if key not in allowed:
            raise ModelError("champ inconnu : %s" % key)


def _label(key: str) -> str:
    return LABELS.get(key, key)


def _text(params: Dict[str, Any], key: str, required: bool = False, default: str = "",
          limit: int = NAME_LIMIT, multiline: bool = False) -> str:
    if key not in params or params[key] is None:
        if required:
            raise ModelError("%s manquant" % _label(key))
        return default
    value = params[key]
    if not isinstance(value, str):
        raise ModelError("%s : texte attendu" % _label(key))
    value = CONTROL.sub(" ", value.replace("\r\n", "\n"))
    if multiline:
        value = "\n".join(" ".join(line.split()) for line in value.split("\n")).strip()
    else:
        value = " ".join(value.split())
    if required and not value:
        raise ModelError("%s manquant" % _label(key))
    if len(value) > limit:
        raise ModelError("%s : %d caractères au plus" % (_label(key), limit))
    return value


def _number(params: Dict[str, Any], key: str, low: float, high: float,
            digits: int = 2, required: bool = False, default: Optional[float] = None,
            above: bool = False) -> Optional[float]:
    if key not in params or params[key] is None or params[key] == "":
        if required:
            raise ModelError("%s manquant" % _label(key))
        return default
    value = params[key]
    if isinstance(value, str):
        try:
            value = float(value.strip().replace(",", "."))
        except ValueError:
            raise ModelError("%s : nombre attendu" % _label(key))
    if not _is_number(value):
        raise ModelError("%s : nombre attendu" % _label(key))
    if value < low or value > high or (above and value <= low):
        raise ModelError("%s : entre %s et %s" % (_label(key), _figure(low), _figure(high)))
    return round_half_away(float(value), digits)


def _choice(params: Dict[str, Any], key: str, choices: Tuple[str, ...],
            required: bool = False, default: str = "") -> str:
    if key not in params or params[key] is None:
        if required:
            raise ModelError("%s manquant" % _label(key))
        return default
    if params[key] not in choices:
        raise ModelError("%s : %r inconnu" % (_label(key), params[key]))
    return params[key]


def _record(library: Dict[str, Any], collection: str, params: Dict[str, Any],
            key: str = "id") -> Dict[str, Any]:
    ident = params.get(key)
    record = library[collection].get(ident) if isinstance(ident, str) else None
    if record is None:
        raise ModelError("%s introuvable : %r" % (_label(key), ident))
    return record


def _new_id(library: Dict[str, Any], collection: str) -> str:
    counter = COUNTERS[collection]
    library["counters"][counter] += 1
    return "%s%03d" % (IDS[collection], library["counters"][counter])


def _slot(params: Dict[str, Any]) -> str:
    slot = params.get("slot")
    if slot not in SLOT_NAMES:
        raise ModelError("emplacement : T1A à T4D attendu, reçu %r" % slot)
    return slot


def _colour(params: Dict[str, Any], required: bool) -> Optional[str]:
    if params.get("colour") in (None, ""):
        if required:
            raise ModelError("couleur manquante")
        return None
    value = colour_key(params["colour"]) if isinstance(params["colour"], str) else ""
    if not value:
        raise ModelError("couleur : six chiffres hexadécimaux attendus, reçu %r" % params["colour"])
    return value


class Context(object):
    """What an action may know besides the library."""

    def __init__(self, now: int, materials: Optional[Dict[str, Dict[str, Any]]] = None,
                 observations: Optional[Dict[str, Dict[str, Any]]] = None) -> None:
        self.now = int(now)
        self.materials = materials or {}
        self.observations = observations or {}


def _event(kind: str, **fields: Any) -> Dict[str, Any]:
    event = {"kind": kind}
    event.update(fields)
    return event


def _changes(record: Dict[str, Any], values: Dict[str, Any]) -> List[str]:
    changed = []
    for key, value in values.items():
        if value is not None and record.get(key) != value:
            record[key] = value
            changed.append(key)
    return changed


# ---------------------------------------------------------------- empty spools
def _create_empty_spool(library, params, context):
    _only(params, ("manufacturer", "name", "spool_material", "tare_g", "nominal_net_g",
                   "source", "catalogue", "notes"))
    source = _choice(params, "source", TARE_SOURCES, required=True)
    catalogue = _text(params, "catalogue", limit=160)
    if source == "spoolmandb" and not catalogue:
        raise ModelError("référence SpoolmanDB manquante")
    for empty in library["empty_spools"].values():
        if catalogue and empty["catalogue"] == catalogue:
            raise ModelError("déjà dans la bibliothèque : %s" % empty["id"])
    record = {
        "manufacturer": _text(params, "manufacturer", required=True),
        "name": _text(params, "name"),
        "spool_material": _choice(params, "spool_material", SPOOL_MATERIALS, required=True),
        "tare_g": _number(params, "tare_g", 0, 2000, required=True, above=True),
        "nominal_net_g": _number(params, "nominal_net_g", 0, 10000, required=True, above=True),
        "source": source,
        "catalogue": catalogue,
        "weighed_on": context.now if source == "pesee" else 0,
        "notes": _text(params, "notes", limit=NOTES_LIMIT, multiline=True),
        "created": context.now,
        "updated": context.now,
    }
    ident = _new_id(library, "empty_spools")
    record["id"] = ident
    library["empty_spools"][ident] = record
    return [_event("bobine_vide", empty_spool=ident, change="créée", tare_g=record["tare_g"],
                   source=source)], {"id": ident}


def _pesee_users(library, ident):
    return sorted(spool["id"] for spool in library["spools"].values()
                  if spool["empty_spool"] == ident and spool["basis"]["kind"] == "pesee")


def _edit_empty_spool(library, params, context):
    _only(params, ("id", "manufacturer", "name", "spool_material", "tare_g", "nominal_net_g", "notes"))
    record = _record(library, "empty_spools", params)
    values = {
        "manufacturer": _text(params, "manufacturer", required=True) if "manufacturer" in params else None,
        "name": _text(params, "name") if "name" in params else None,
        "spool_material": _choice(params, "spool_material", SPOOL_MATERIALS) or None,
        "nominal_net_g": _number(params, "nominal_net_g", 0, 10000, above=True),
        "notes": _text(params, "notes", limit=NOTES_LIMIT, multiline=True) if "notes" in params else None,
    }
    tare = _number(params, "tare_g", 0, 2000, above=True)
    changed = _changes(record, values)
    events = []
    if tare is not None and tare != record["tare_g"]:
        # A tare typed by hand is no longer the weighing or the catalogue value.
        record["tare_g"] = tare
        record["source"] = "manuel"
        record["weighed_on"] = 0
        changed.append("tare_g")
    if not changed:
        return [], {"id": record["id"], "changed": []}
    record["updated"] = context.now
    fields = {"empty_spool": record["id"], "change": "modifiée", "fields": changed}
    if "tare_g" in changed:
        fields.update(tare_g=record["tare_g"], recalculated=_pesee_users(library, record["id"]))
    events.append(_event("bobine_vide", **fields))
    return events, {"id": record["id"], "changed": changed}


def _weigh_empty_spool(library, params, context):
    """A weighing of an empty spool: it replaces the catalogue or typed tare."""
    _only(params, ("id", "tare_g"))
    record = _record(library, "empty_spools", params)
    record["tare_g"] = _number(params, "tare_g", 0, 2000, required=True, above=True)
    record["source"] = "pesee"
    record["weighed_on"] = context.now
    record["updated"] = context.now
    return [_event("bobine_vide", empty_spool=record["id"], change="pesée", tare_g=record["tare_g"],
                   source="pesee", recalculated=_pesee_users(library, record["id"]))], {"id": record["id"]}


def _delete_empty_spool(library, params, context):
    _only(params, ("id",))
    record = _record(library, "empty_spools", params)
    users = sorted(label(spool["id"]) for spool in library["spools"].values()
                   if spool["empty_spool"] == record["id"])
    if users:
        raise ModelError("bobine vide utilisée par %s" % ", ".join(users))
    del library["empty_spools"][record["id"]]
    return [_event("bobine_vide", empty_spool=record["id"], change="supprimée")], {"id": record["id"]}


# ---------------------------------------------------------------- filaments
def _fiche_values(library, params, context, current):
    """Checked fields of a filament record; current is None for a new one."""
    def given(key):
        return key in params and params[key] not in (None, "")

    base = dict(current or {})
    manufacturer = (_text(params, "manufacturer", required=True) if "manufacturer" in params
                    else base.get("manufacturer", ""))
    if not manufacturer:
        raise ModelError("fabricant manquant")
    material = _text(params, "material").upper() if given("material") else None
    name = _text(params, "name") if "name" in params else base.get("name", "")
    colour = _colour(params, required=current is None) or base.get("colour")
    diameter = _number(params, "diameter_mm", 1.0, 3.5, digits=2,
                       default=base.get("diameter_mm", DIAMETER))
    density = _number(params, "density", 0.5, 8.0, digits=3, default=None)
    creality_id = _text(params, "creality_id") if given("creality_id") else None
    identity_changes = current is None or creality_id is not None or material is not None
    if identity_changes:
        if not context.materials:
            raise ModelError("base matériau de la K1 illisible : impossible de vérifier la "
                             "fiche Creality, réessayer quand Klipper est prêt")
        if creality_id is None and current is not None and material in (None, base["material"]):
            creality_id = base["creality_id"]
        if creality_id is None:
            creality_id = suggest_creality_id(manufacturer, material or base.get("material", ""),
                                              name, context.materials)
            if not creality_id:
                raise ModelError("choisir la fiche matériau Creality : aucune ne correspond à "
                                 "%s %s" % (manufacturer, material or "?"))
        record = context.materials.get(creality_id)
        if record is None:
            raise ModelError("fiche matériau Creality %s inconnue de la K1" % creality_id)
        if material is None:
            material = record["type"]
        elif material != record["type"]:
            raise ModelError("la fiche Creality %s est du %s, pas du %s : choisir une fiche "
                             "%s ou corriger la matière" % (creality_id, record["type"],
                                                             material, material))
        if density is None:
            density = base.get("density") if current is not None and material == base.get("material") \
                else record["density"]
            if density is None or not 0.5 <= density <= 8.0:
                raise ModelError("densité inconnue pour %s : la saisir" % material)
            density = round_half_away(density, 3)
    else:
        creality_id = base["creality_id"]
        material = base["material"]
        if density is None:
            density = base["density"]
    return {
        "manufacturer": manufacturer,
        "name": name or material,
        "material": material,
        "colour": colour,
        "diameter_mm": diameter,
        "density": density,
        "creality_id": creality_id,
        "notes": (_text(params, "notes", limit=NOTES_LIMIT, multiline=True) if "notes" in params
                  else base.get("notes", "")),
    }


def _same_fiche(library, values, ignore=""):
    for fiche in library["filaments"].values():
        if (fiche["id"] != ignore
                and fiche["manufacturer"].casefold() == values["manufacturer"].casefold()
                and fiche["name"].casefold() == values["name"].casefold()
                and fiche["colour"] == values["colour"]
                and fiche["creality_id"] == values["creality_id"]
                and fiche["diameter_mm"] == values["diameter_mm"]):
            return fiche["id"]
    return ""


def _create_filament(library, params, context):
    _only(params, ("manufacturer", "name", "material", "colour", "diameter_mm", "density",
                   "creality_id", "notes"))
    values = _fiche_values(library, params, context, None)
    twin = _same_fiche(library, values)
    if twin:
        raise ModelError("fiche identique déjà présente : %s" % twin)
    ident = _new_id(library, "filaments")
    values.update(id=ident, created=context.now, updated=context.now)
    library["filaments"][ident] = values
    return [_event("fiche", filament=ident, change="créée", creality_id=values["creality_id"],
                   colour=values["colour"])], {"id": ident}


def _edit_filament(library, params, context):
    _only(params, ("id", "manufacturer", "name", "material", "colour", "diameter_mm", "density",
                   "creality_id", "notes"))
    record = _record(library, "filaments", params)
    values = _fiche_values(library, {key: value for key, value in params.items() if key != "id"},
                           context, record)
    twin = _same_fiche(library, values, ignore=record["id"])
    if twin:
        raise ModelError("fiche identique déjà présente : %s" % twin)
    changed = _changes(record, values)
    if not changed:
        return [], {"id": record["id"], "changed": []}
    record["updated"] = context.now
    users = sorted(spool["id"] for spool in library["spools"].values() if spool["filament"] == record["id"])
    return [_event("fiche", filament=record["id"], change="modifiée", fields=changed,
                   spools=users)], {"id": record["id"], "changed": changed}


def _delete_filament(library, params, context):
    _only(params, ("id",))
    record = _record(library, "filaments", params)
    users = sorted(label(spool["id"]) for spool in library["spools"].values()
                   if spool["filament"] == record["id"])
    if users:
        raise ModelError("fiche utilisée par %s" % ", ".join(users))
    del library["filaments"][record["id"]]
    return [_event("fiche", filament=record["id"], change="supprimée")], {"id": record["id"]}


# ---------------------------------------------------------------- spools
def _basis(library, spool, kind, value, now):
    """A checked basis {kind, value_g, on}: value is net for an estimate, gross for a weighing."""
    if kind == "neuve":
        return {"kind": "neuve", "value_g": spool["initial_net_g"], "on": now}
    if value is None:
        raise ModelError("valeur manquante")
    if kind == "pesee":
        empty = library["empty_spools"].get(spool["empty_spool"])
        if empty is None:
            raise ModelError("poids brut sans bobine vide : choisir le type de bobine vide pour "
                             "retirer sa tare, ou donner une estimation")
        net_of_gross(value, empty["tare_g"])
    elif value > spool["initial_net_g"]:
        # A weighing may find a few grams more than the nominal net; an
        # estimate above what the spool held when new is a typing error.
        raise ModelError("estimation de %s g au-delà du net initial de %s g"
                         % (_figure(value), _figure(spool["initial_net_g"])))
    return {"kind": kind, "value_g": value, "on": now}


def _link(library, spool, slot, context):
    """Put `spool` in `slot`; the spool expected there before goes to "à ranger"."""
    events = []
    previous = linked(library, slot)
    if previous is not None and previous["id"] != spool["id"]:
        previous["state"] = "a_ranger"
        previous["slot"] = ""
        previous["updated"] = context.now
        events.append(_event("etat", spool=previous["id"], state="a_ranger", slot=slot,
                             detail="remplacée par %s" % label(spool["id"])))
    pending = library["pending_cfs"].get(slot)
    if pending is not None and pending["spool"] != spool["id"]:
        del library["pending_cfs"][slot]
        events.append(_event("ecriture_cfs", slot=slot, spool=pending["spool"], result="annulée",
                             detail="autre bobine en %s" % slot))
    spool["state"] = "cfs"
    spool["slot"] = slot
    spool["place"] = ""
    spool["updated"] = context.now
    observation = context.observations.get(slot) or {}
    record = library["slots"].setdefault(slot, {"observed": None, "arrived": False, "last_write": None})
    record["arrived"] = bool(observation.get("present"))
    events.append(_event("etat", spool=spool["id"], state="cfs", slot=slot))
    return events


def _unlink(library, spool, slot, context, reason):
    events = []
    pending = library["pending_cfs"].get(slot)
    if pending is not None and pending["spool"] == spool["id"]:
        del library["pending_cfs"][slot]
        events.append(_event("ecriture_cfs", slot=slot, spool=spool["id"], result="annulée",
                             detail=reason))
    record = library["slots"].get(slot)
    if record is not None:
        record["arrived"] = False
    spool["slot"] = ""
    return events


def _create_spool(library, params, context):
    _only(params, ("filament", "empty_spool", "initial_net_g", "basis_kind", "value_g", "state",
                   "slot", "place", "notes"))
    fiche = _record(library, "filaments", params, "filament")
    empty_id = _text(params, "empty_spool")
    empty = None
    if empty_id:
        empty = _record(library, "empty_spools", params, "empty_spool")
    initial = _number(params, "initial_net_g", 0, 10000, above=True,
                      default=empty["nominal_net_g"] if empty else None)
    if initial is None:
        raise ModelError("net initial manquant : le donner ou choisir la bobine vide")
    state = _choice(params, "state", ("stock", "a_ranger", "cfs"), default="stock")
    if params.get("slot") and state != "cfs":
        raise ModelError("emplacement donné pour une bobine hors du CFS")
    kind = _choice(params, "basis_kind", BASES, default="neuve")
    value = _number(params, "value_g", 0, 15000)
    spool = {
        "filament": fiche["id"],
        "empty_spool": empty_id,
        "initial_net_g": initial,
        "counted_g": 0.0,
        "last_gap": None,
        "state": "stock" if state == "cfs" else state,
        "slot": "",
        "place": _text(params, "place") if state == "stock" else "",
        "notes": _text(params, "notes", limit=NOTES_LIMIT, multiline=True),
        "created": context.now,
        "updated": context.now,
    }
    spool["basis"] = _basis(library, spool, kind, value, context.now)
    slot = _slot(params) if state == "cfs" else ""
    ident = _new_id(library, "spools")
    spool["id"] = ident
    library["spools"][ident] = spool
    events = [_event("bobine", spool=ident, change="créée", filament=fiche["id"],
                     basis=spool["basis"]["kind"], net_g=basis_net(library, spool))]
    if slot:
        events.extend(_link(library, spool, slot, context))
    return events, {"id": ident}


def _edit_spool(library, params, context):
    _only(params, ("id", "filament", "empty_spool", "initial_net_g", "notes"))
    spool = _record(library, "spools", params)
    values = {}
    if "filament" in params:
        values["filament"] = _record(library, "filaments", params, "filament")["id"]
    if "empty_spool" in params:
        empty_id = _text(params, "empty_spool")
        if empty_id:
            _record(library, "empty_spools", params, "empty_spool")
        elif spool["basis"]["kind"] == "pesee":
            raise ModelError("cette bobine a un reste pesé : la bobine vide donne sa tare")
        values["empty_spool"] = empty_id
    values["initial_net_g"] = _number(params, "initial_net_g", 0, 10000, above=True)
    if "notes" in params:
        values["notes"] = _text(params, "notes", limit=NOTES_LIMIT, multiline=True)
    if spool["basis"]["kind"] == "pesee" and values.get("empty_spool"):
        empty = library["empty_spools"][values["empty_spool"]]
        net_of_gross(spool["basis"]["value_g"], empty["tare_g"])
    if (spool["basis"]["kind"] == "estimation" and values["initial_net_g"] is not None
            and spool["basis"]["value_g"] > values["initial_net_g"]):
        raise ModelError("net initial de %s g sous l'estimation actuelle de %s g"
                         % (_figure(values["initial_net_g"]), _figure(spool["basis"]["value_g"])))
    changed = _changes(spool, values)
    if not changed:
        return [], {"id": spool["id"], "changed": []}
    if spool["basis"]["kind"] == "neuve":
        spool["basis"]["value_g"] = spool["initial_net_g"]
    spool["updated"] = context.now
    return [_event("bobine", spool=spool["id"], change="modifiée", fields=changed)], \
        {"id": spool["id"], "changed": changed}


def _set_remaining(library, params, context):
    """A new remaining weight. A weighing also keeps the gap to the count."""
    _only(params, ("id", "kind", "value_g"))
    spool = _record(library, "spools", params)
    kind = _choice(params, "kind", BASES, required=True)
    value = _number(params, "value_g", 0, 15000)
    before = basis_net(library, spool)
    counted = spool["counted_g"]
    previous = spool["basis"]["kind"]
    spool["basis"] = _basis(library, spool, kind, value, context.now)
    net = basis_net(library, spool)
    fields = {"spool": spool["id"], "basis": kind, "net_g": net, "counted_g": counted,
              "previous": previous}
    if kind == "pesee" and before is not None:
        gap = round_half_away(net - (before - counted), 2)
        spool["last_gap"] = {"g": gap, "counted_g": counted, "previous": previous, "on": context.now}
        fields["gap_g"] = gap
    spool["counted_g"] = 0.0
    spool["updated"] = context.now
    return [_event("reste", **fields)], {"id": spool["id"], "net_g": net}


def _put_in_cfs(library, params, context):
    _only(params, ("id", "slot"))
    spool = _record(library, "spools", params)
    slot = _slot(params)
    if spool["state"] == "cfs":
        raise ModelError("%s est déjà au CFS en %s : la retirer d'abord" % (label(spool["id"]), spool["slot"]))
    if spool["state"] in ARCHIVED:
        raise ModelError("%s est archivée : la remettre en stock d'abord" % label(spool["id"]))
    return _link(library, spool, slot, context), {"id": spool["id"], "slot": slot}


def _remove_from_cfs(library, params, context):
    _only(params, ("id",))
    spool = _record(library, "spools", params)
    if spool["state"] != "cfs":
        raise ModelError("%s n'est pas au CFS" % label(spool["id"]))
    slot = spool["slot"]
    events = _unlink(library, spool, slot, context, "bobine retirée")
    spool["state"] = "a_ranger"
    spool["updated"] = context.now
    events.append(_event("etat", spool=spool["id"], state="a_ranger", slot=slot, detail="retirée"))
    return events, {"id": spool["id"]}


def _store(library, params, context):
    _only(params, ("id", "place"))
    spool = _record(library, "spools", params)
    if spool["state"] not in ("a_ranger", "stock"):
        raise ModelError("%s : retirer du CFS ou remettre en stock d'abord" % label(spool["id"]))
    place = _text(params, "place")
    moved = spool["state"] == "stock"
    spool["state"] = "stock"
    spool["place"] = place
    spool["updated"] = context.now
    return [_event("etat", spool=spool["id"], state="stock", place=place,
                   detail="déplacée" if moved else "rangée")], {"id": spool["id"]}


def _archive(state):
    def action(library, params, context):
        _only(params, ("id",))
        spool = _record(library, "spools", params)
        if spool["state"] in ARCHIVED:
            raise ModelError("%s est déjà archivée" % label(spool["id"]))
        events = []
        slot = spool["slot"]
        if spool["state"] == "cfs":
            events.extend(_unlink(library, spool, slot, context, "bobine archivée"))
        spool["state"] = state
        spool["updated"] = context.now
        events.append(_event("etat", spool=spool["id"], state=state, slot=slot))
        return events, {"id": spool["id"]}
    return action


def _restore(library, params, context):
    _only(params, ("id",))
    spool = _record(library, "spools", params)
    if spool["state"] not in ARCHIVED:
        raise ModelError("%s n'est pas archivée" % label(spool["id"]))
    spool["state"] = "stock"
    spool["updated"] = context.now
    return [_event("etat", spool=spool["id"], state="stock", detail="remise en stock")], {"id": spool["id"]}


def _adopt_cfs(library, params, context):
    """The CFS is right: the spool takes the material and colour the slot shows.

    Its record may be shared with other spools, so it is not edited: the spool
    moves to a record of the same maker with that identity, created as a copy
    of its current one when none exists yet.
    """
    _only(params, ("slot",))
    slot = _slot(params)
    spool = linked(library, slot)
    if spool is None:
        raise ModelError("aucune bobine attendue en %s" % slot)
    observation = context.observations.get(slot) or {}
    if not observation.get("present"):
        raise ModelError("%s est vide au CFS" % slot)
    current = library["filaments"][spool["filament"]]
    if same_identity(current, observation):
        return [], {"id": spool["id"], "filament": current["id"]}
    creality_id = material_key(observation["material"])
    record = context.materials.get(creality_id)
    if record is None:
        raise ModelError("matériau %s du CFS inconnu de la base de la K1" % observation["material"])
    if not observation["colour"]:
        raise ModelError("couleur du CFS illisible en %s" % slot)
    target = ""
    for fiche in library["filaments"].values():
        if (fiche["manufacturer"].casefold() == current["manufacturer"].casefold()
                and fiche["creality_id"] == creality_id and fiche["colour"] == observation["colour"]
                and fiche["diameter_mm"] == current["diameter_mm"]):
            target = fiche["id"]
            break
    events = []
    if not target:
        same_type = record["type"] == current["material"]
        density = current["density"] if same_type else record["density"]
        if density is None:
            density = current["density"]
        target = _new_id(library, "filaments")
        library["filaments"][target] = {
            "id": target,
            "manufacturer": current["manufacturer"],
            "name": current["name"] if same_type else record["type"],
            "material": record["type"],
            "colour": observation["colour"],
            "diameter_mm": current["diameter_mm"],
            "density": round_half_away(density, 3),
            "creality_id": creality_id,
            "notes": "copiée de %s depuis le CFS (%s)" % (current["id"], slot),
            "created": context.now,
            "updated": context.now,
        }
        events.append(_event("fiche", filament=target, change="créée depuis le CFS", slot=slot,
                             creality_id=creality_id, colour=observation["colour"]))
    spool["filament"] = target
    spool["updated"] = context.now
    events.append(_event("bobine", spool=spool["id"], change="identité du CFS adoptée", slot=slot,
                         fields=["filament"], filament=target))
    return events, {"id": spool["id"], "filament": target}


def _assign_segment(library, params, context):
    _only(params, ("segment", "spool"))
    ident = params.get("segment")
    segment = next((item for item in library["unassigned"] if item["id"] == ident), None)
    if segment is None:
        raise ModelError("segment introuvable : %r" % ident)
    spool = _record(library, "spools", params, "spool")
    grams = round_half_away(grams_of_mm(segment["mm"], fiche_gpm(library["filaments"][spool["filament"]])), 2)
    spool["counted_g"] = round_half_away(spool["counted_g"] + grams, 2)
    spool["updated"] = context.now
    library["unassigned"].remove(segment)
    for printed in library["prints"]:
        if printed["job"] == segment.get("job"):
            printed.setdefault("assigned", []).append(
                {"segment": segment["id"], "spool": spool["id"], "mm": segment["mm"], "g": grams})
    return [_event("consommation", spool=spool["id"], mm=segment["mm"], g=grams, job=segment.get("job", ""),
                   detail="segment %s attribué" % segment["id"])], {"id": spool["id"], "g": grams}


def _dismiss_segment(library, params, context):
    _only(params, ("segment",))
    ident = params.get("segment")
    segment = next((item for item in library["unassigned"] if item["id"] == ident), None)
    if segment is None:
        raise ModelError("segment introuvable : %r" % ident)
    library["unassigned"].remove(segment)
    return [_event("consommation", mm=segment["mm"], job=segment.get("job", ""),
                   detail="segment %s ignoré" % segment["id"])], {"segment": ident}


def _settings(library, params, context):
    _only(params, ("cut_loss_mm", "low_g"))
    values = {
        "cut_loss_mm": _number(params, "cut_loss_mm", 0, 200),
        "low_g": _number(params, "low_g", 0, 5000),
    }
    changed = _changes(library["settings"], values)
    return ([_event("reglages", fields=changed, **{key: library["settings"][key] for key in changed})]
            if changed else []), {"changed": changed}


# ---------------------------------------------------------------- internal
def _observe(library, params, context):
    """What the CFS shows now: a removal sends the spool to "à ranger".

    Only connected units count: a unit that drops off says nothing about its
    spools. A slot of a spool linked while the slot was empty waits for the
    spool ("attendue"); it is seen arriving, and only a spool that arrived can
    be taken out.
    """
    _only(params, ())
    events = []
    for slot in SLOT_NAMES:
        observation = context.observations.get(slot)
        if not observation or not observation.get("connected"):
            continue
        record = library["slots"].setdefault(slot, {"observed": None, "arrived": False, "last_write": None})
        before = record.get("observed")
        seen = {"present": observation["present"], "material": observation["material"],
                "colour": observation["colour"]}
        spool = linked(library, slot)
        if before is None or before == seen:
            # The first reading after a start is the reference, not a change.
            record["observed"] = seen
            if spool is not None and seen["present"]:
                record["arrived"] = True
            continue
        record["observed"] = seen
        was_present = bool(before and before.get("present"))
        if was_present and not seen["present"]:
            if spool is not None and record["arrived"]:
                spool["state"] = "a_ranger"
                spool["slot"] = ""
                spool["updated"] = context.now
                events.append(_event("etat", spool=spool["id"], state="a_ranger", slot=slot,
                                     detail="retirée du CFS"))
                pending = library["pending_cfs"].get(slot)
                if pending is not None:
                    del library["pending_cfs"][slot]
                    events.append(_event("ecriture_cfs", slot=slot, spool=pending["spool"],
                                         result="annulée", detail="bobine retirée"))
            else:
                events.append(_event("cfs", slot=slot, detail="emplacement vidé"))
            record["arrived"] = False
        elif seen["present"] and not was_present:
            if spool is not None:
                record["arrived"] = True
            events.append(_event("cfs", slot=slot, detail="bobine arrivée", material=seen["material"],
                                 colour=seen["colour"], spool=spool["id"] if spool else ""))
        elif seen["present"]:
            if spool is not None:
                record["arrived"] = True
            events.append(_event("cfs", slot=slot, detail="matière ou couleur changée au CFS",
                                 material=seen["material"], colour=seen["colour"],
                                 spool=spool["id"] if spool else ""))
    return events, {"events": len(events)}


def _queue_cfs(library, params, context):
    _only(params, ("slot", "spool", "material", "colour"))
    slot = _slot(params)
    spool = _record(library, "spools", params, "spool")
    if spool["state"] != "cfs" or spool["slot"] != slot:
        raise ModelError("%s n'est plus attendue en %s" % (label(spool["id"]), slot))
    library["pending_cfs"][slot] = {"spool": spool["id"], "material": params.get("material"),
                                    "colour": params.get("colour"), "on": context.now}
    return [_event("ecriture_cfs", slot=slot, spool=spool["id"], result="en attente",
                   detail="impression en cours, envoi à la fin")], {"slot": slot}


def _write_result(library, params, context):
    _only(params, ("slot", "spool", "material", "colour", "result", "detail", "read"))
    slot = _slot(params)
    result = _choice(params, "result", ("ok", "ecart", "erreur", "annulee"), required=True)
    record = library["slots"].setdefault(slot, {"observed": None, "arrived": False, "last_write": None})
    record["last_write"] = {
        "spool": params.get("spool", ""), "material": params.get("material"),
        "colour": params.get("colour"), "result": result, "detail": str(params.get("detail", ""))[:300],
        "read": params.get("read"), "on": context.now,
    }
    pending = library["pending_cfs"].get(slot)
    if pending is not None:
        del library["pending_cfs"][slot]
    return [_event("ecriture_cfs", slot=slot, spool=params.get("spool", ""), result=result,
                   material=params.get("material"), colour=params.get("colour"),
                   read=params.get("read"), detail=record["last_write"]["detail"])], {"slot": slot}


def _print_end(library, params, context):
    """The count of a finished print, applied once per job.

    `segments` come from kctrl_spools_counter: the slot each one ran on, or
    none when the slot was not proved, and the millimetres the extruder
    pushed. `spools` is which spool was expected in each slot when the print
    started. A segment without a proved slot or without a spool goes to the
    list to attribute: Thomas decides with one click, nothing is guessed.
    """
    _only(params, ("job", "file", "start", "end", "outcome", "segments", "spools", "planned",
                   "notes"))
    job = params.get("job")
    if not isinstance(job, str) or not job:
        raise ModelError("impression sans identifiant")
    if any(printed["job"] == job for printed in library["prints"]):
        return [], {"job": job, "applied": False}
    expected = params.get("spools") or {}
    totals = {}  # type: Dict[str, Dict[str, float]]
    events = []
    unassigned = []
    for segment in params.get("segments") or []:
        mm = float(segment.get("mm", 0.0))
        if mm <= 0:
            continue
        slot = segment.get("slot") or ""
        spool = library["spools"].get(expected.get(slot, "")) if slot else None
        if spool is None or segment.get("reason"):
            library["counters"]["segment"] += 1
            unassigned.append({
                "id": "S%03d" % library["counters"]["segment"], "job": job, "slot": slot,
                "mm": round_half_away(mm, 1), "on": context.now,
                "reason": segment.get("reason") or ("aucune bobine liée à %s" % slot if slot
                                                    else "emplacement non prouvé"),
            })
            continue
        gpm = fiche_gpm(library["filaments"][spool["filament"]])
        line = totals.setdefault(spool["id"], {"slot": slot, "mm": 0.0, "g": 0.0})
        line["mm"] += mm
        line["g"] += grams_of_mm(mm, gpm)
    per_spool = []
    for ident in sorted(totals):
        line = totals[ident]
        spool = library["spools"][ident]
        grams = round_half_away(line["g"], 2)
        spool["counted_g"] = round_half_away(spool["counted_g"] + grams, 2)
        spool["updated"] = context.now
        metres = round_half_away(line["mm"] / 1000.0, 2)
        per_spool.append({"spool": ident, "slot": line["slot"], "mm": round_half_away(line["mm"], 1),
                          "g": grams, "m": metres})
        events.append(_event("consommation", spool=ident, slot=line["slot"], job=job,
                             mm=round_half_away(line["mm"], 1), g=grams, m=metres))
    for segment in unassigned:
        events.append(_event("consommation", job=job, slot=segment["slot"], mm=segment["mm"],
                             detail="à attribuer : %s" % segment["reason"], segment=segment["id"]))
    library["unassigned"].extend(unassigned)
    dropped = len(library["unassigned"]) - UNASSIGNED_KEPT
    if dropped > 0:
        events.append(_event("consommation", detail="%d segment(s) à attribuer trop anciens oubliés"
                             % dropped))
        del library["unassigned"][:dropped]
    library["prints"].append({
        "job": job, "file": str(params.get("file", ""))[:200], "start": params.get("start", 0),
        "end": params.get("end", context.now), "outcome": str(params.get("outcome", "")),
        "per_spool": per_spool, "unassigned": [segment["id"] for segment in unassigned],
        "planned": params.get("planned") or [], "notes": list(params.get("notes") or [])[:10],
    })
    del library["prints"][:-PRINTS_KEPT]
    events.append(_event("impression", job=job, file=str(params.get("file", ""))[:200],
                         outcome=str(params.get("outcome", "")), spools=sorted(totals),
                         unassigned=len(unassigned)))
    return events, {"job": job, "applied": True}


ACTIONS = {
    "create_empty_spool": (_create_empty_spool, False),
    "edit_empty_spool": (_edit_empty_spool, False),
    "weigh_empty_spool": (_weigh_empty_spool, False),
    "delete_empty_spool": (_delete_empty_spool, False),
    "create_filament": (_create_filament, False),
    "edit_filament": (_edit_filament, False),
    "delete_filament": (_delete_filament, False),
    "create_spool": (_create_spool, False),
    "edit_spool": (_edit_spool, False),
    "set_remaining": (_set_remaining, False),
    "put_in_cfs": (_put_in_cfs, False),
    "remove_from_cfs": (_remove_from_cfs, False),
    "store": (_store, False),
    "finish": (_archive("terminee"), False),
    "discard": (_archive("jetee"), False),
    "restore": (_restore, False),
    "adopt_cfs": (_adopt_cfs, False),
    "assign_segment": (_assign_segment, False),
    "dismiss_segment": (_dismiss_segment, False),
    "settings": (_settings, False),
    "observe": (_observe, True),
    "queue_cfs": (_queue_cfs, True),
    "write_result": (_write_result, True),
    "print_end": (_print_end, True),
}


def apply(library: Dict[str, Any], name: str, params: Any, context: Context,
          internal: bool = False) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
    """(new library, journal events, result) of one action on a copy.

    The library passed in is never changed. A refusal raises ModelError with
    the reason. A copy that fails check() after the action is a bug here, and
    raises too rather than reaching the disk.
    """
    entry = ACTIONS.get(name)
    if entry is None or (entry[1] and not internal):
        raise ModelError("action inconnue : %s" % name)
    if not isinstance(params, dict):
        raise ModelError("paramètres attendus")
    work = copy.deepcopy(library)
    events, result = entry[0](work, params, context)
    errors = check(work)
    if errors:
        raise ModelError("refusé, la bibliothèque deviendrait incohérente : %s" % errors[0])
    for event in events:
        event["t"] = context.now
    return work, events, result


# ---------------------------------------------------------------- export
EXPORT_FORMAT = "kctrl_spools.export"


def export_document(library: Dict[str, Any], journal: List[Dict[str, Any]], now: int) -> Dict[str, Any]:
    return {"format": EXPORT_FORMAT, "schema": SCHEMA, "exported": int(now),
            "library": copy.deepcopy(library), "journal": copy.deepcopy(journal)}


def import_document(document: Any) -> Dict[str, Any]:
    """The library of an export, checked; pending CFS writes are not carried over.

    An imported file is a backup, not an order: a write to the CFS queued in it
    could reach a slot that holds another spool by now.
    """
    if not isinstance(document, dict) or document.get("format") != EXPORT_FORMAT:
        raise ModelError("fichier d'export des bobines K1 Control attendu")
    if not isinstance(document.get("schema"), int) or document["schema"] > SCHEMA:
        raise ModelError("export d'une version plus récente de K1 Control : mettre à jour d'abord")
    library = document.get("library")
    if not isinstance(library, dict):
        raise ModelError("export sans bibliothèque")
    library = normalise(copy.deepcopy(library))
    library["pending_cfs"] = {}
    errors = check(library)
    if errors:
        raise ModelError("export incohérent : %s" % errors[0])
    return library
