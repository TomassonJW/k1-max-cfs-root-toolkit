"""Expose the CFS tool-remap table to Klipper macros.

The stock screen already asks the question Thomas wants asked. When a print is
started from the touchscreen, from the Creality app or from the Creality web
page, the firmware parses the sliced file, reads its filament colours and types,
proposes a slot for each one, lets the operator correct it, and applies the
result with BOX_MODIFY_TN. Traces of that machinery are in master-server.log,
for every file on the machine:

    Parse file path:3DBenchy_C2.gcode
    types  : PLA;PLA;PLA;PLA
    colors : #000000;#ffffff;#ff0000;#0080ff
    the multicolor match info is (T1A=T1A T1B=T1D T1C=T2A T1D=T2B)

BOX_MODIFY_TN writes the table into tn_data.json under the key `tnn_map`. The
stock cmd_T reads it for every mid-print colour change. What it never reaches is
the Klipper `box` object: querying `printer.box` returns the slot contents and
the auto-refill groups, and no map at all. A macro therefore cannot see the
answer the operator just gave on the screen.

This object closes that gap, read-only. It reads the same file the firmware
writes, re-reading only when the file changes, and publishes the table under
`printer["kctrl_slot_map"].map`. START_PRINT resolves the job's first filament
through it, so the choice made on the screen is the slot that gets loaded, with
nothing to type.

Nothing here writes. The writer stays BOX_MODIFY_TN, the CFS's own command.
"""

import json
import os

DEFAULT_PATH = "/usr/data/creality/userdata/box/tn_data.json"
BOXES = ("1", "2", "3", "4")
SLOTS = ("A", "B", "C", "D")
NAMES = tuple("T" + box + slot for box in BOXES for slot in SLOTS)


def is_slot_name(value):
    return isinstance(value, str) and value in NAMES


class KctrlSlotMap:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.path = config.get("path", DEFAULT_PATH)
        self.map = {}
        self.error = ""
        # (mtime, size) of the file behind the cached map. get_status runs on
        # every Moonraker poll, so the file is stat'd rather than parsed.
        self.stamp = None
        gcode = self.printer.lookup_object("gcode")
        gcode.register_command(
            "KCTRL_MAP", self.cmd_KCTRL_MAP, desc=self.cmd_KCTRL_MAP_help)

    def stat(self):
        try:
            info = os.stat(self.path)
        except OSError:
            return None
        return (info.st_mtime, info.st_size)

    def refresh(self):
        stamp = self.stat()
        if stamp is None:
            self.map = {}
            self.stamp = None
            self.error = "fichier absent: %s" % self.path
            return
        if stamp == self.stamp:
            return
        self.stamp = stamp
        try:
            with open(self.path) as handle:
                raw = json.load(handle).get("tnn_map", {})
        except (OSError, ValueError) as exception:
            self.map = {}
            self.error = "lecture impossible: %s" % exception
            return
        if not isinstance(raw, dict):
            self.map = {}
            self.error = "tnn_map n'est pas une table"
            return
        # A malformed entry is dropped rather than propagated: a macro that
        # loads a slot named by a truncated string would fail deep inside the
        # CFS routines instead of here.
        table = {key: value for key, value in raw.items()
                 if is_slot_name(key) and is_slot_name(value)}
        self.map = table
        self.error = "" if table else "tnn_map vide"

    def get_status(self, eventtime=None):
        self.refresh()
        return {
            "map": dict(self.map),
            "loaded": 1 if self.map else 0,
            "error": self.error,
            "path": self.path,
        }

    cmd_KCTRL_MAP_help = (
        "Show which physical CFS slot each filament of a job resolves to")

    def cmd_KCTRL_MAP(self, gcmd):
        self.refresh()
        if not self.map:
            raise gcmd.error("K1 Control: table de correspondance illisible, %s"
                             % (self.error or "raison inconnue"))
        box = self.printer.lookup_object("box", None)
        state = box.get_status(self.printer.get_reactor().monotonic()) if box else {}
        lines = ["K1 Control: correspondance filament du travail -> emplacement CFS"]
        for position, logical in enumerate(NAMES, start=1):
            physical = self.map.get(logical)
            if physical is None:
                continue
            unit = state.get("T" + physical[1], {})
            index = SLOTS.index(physical[2])
            material = str(unit.get("material_type", ["-1"] * 4)[index])
            color = str(unit.get("color_value", ["-1"] * 4)[index])
            empty = material in ("-1", "None", "")
            # Sixteen lines of which twelve say nothing is a table nobody
            # reads. An entry is shown when it points at a loaded slot, or
            # when it has been remapped and so carries a decision.
            if empty and physical == logical:
                continue
            detail = "vide" if empty else ("matiere %s, couleur %s"
                                           % (material, color))
            mark = "" if physical == logical else "   <- remappe"
            lines.append("  filament %d (%s) -> %s   %s%s"
                         % (position, logical, physical, detail, mark))
        gcmd.respond_info("\n".join(lines))


def load_config(config):
    return KctrlSlotMap(config)
