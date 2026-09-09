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

It also answers a second question the macros could not ask: which of the
sixteen filaments the job actually starts on. A file can declare sixteen and
print with one of them - the sliced file of 2026-09-09 declared two and issued
a single `T1`, its second filament. START_PRINT used to load the first one
regardless, so it loaded and purged the wrong spool, and the `T1` that followed
turned into a tool change in the middle of the start. That one ended on
`macro_box_extrude_err, tnn: T1B`.

The initial tool is read from the file being printed: the first `Tn` line, with
n between 0 and 15, in slicer order - T0 is the job's first filament, T15 its
sixteenth. It maps onto the logical names T1A..T4D in that same order, which is
what Tnn_map is keyed on.

Nothing here writes. The writer stays BOX_MODIFY_TN, the CFS's own command.
"""

import json
import os
import re

DEFAULT_PATH = "/usr/data/creality/userdata/box/tn_data.json"
BOXES = ("1", "2", "3", "4")
SLOTS = ("A", "B", "C", "D")
NAMES = tuple("T" + box + slot for box in BOXES for slot in SLOTS)

# T0..T15 in slicer order map onto T1A..T4D in that same order: T0 is the job's
# first filament and T1A its logical name, T15 the sixteenth and T4D.
TOOL_LINE = re.compile(rb"^T(\d{1,2})\s*(?:;.*)?$")
# The initial tool sits a few lines after the start block. A megabyte is three
# orders of magnitude of margin and still one short read on the machine.
SCAN_LIMIT = 1 << 20
SCAN_CHUNK = 1 << 16


def is_slot_name(value):
    return isinstance(value, str) and value in NAMES


def logical_of_index(index):
    """Logical name of the slicer's filament number `index`, zero based."""
    if not isinstance(index, int) or index < 0 or index >= len(NAMES):
        return ""
    return NAMES[index]


def scan_initial_tool(path, limit=SCAN_LIMIT):
    """Number of the first filament a sliced file selects, and where it came from.

    Returns (index, note). A file with no tool command at all is mono-filament
    printed on the slicer's first filament, which is index 0 - the same answer
    the old hard-coded T1A gave, now stated rather than assumed.
    """
    try:
        with open(path, "rb") as handle:
            read = 0
            tail = b""
            while read < limit:
                chunk = handle.read(min(SCAN_CHUNK, limit - read))
                if not chunk:
                    break
                read += len(chunk)
                lines = (tail + chunk).split(b"\n")
                tail = lines.pop()
                for line in lines:
                    found = TOOL_LINE.match(line.strip())
                    if found is None:
                        continue
                    index = int(found.group(1))
                    if index >= len(NAMES):
                        return -1, ("le fichier demande T%d, au dela des 16 "
                                    "emplacements du CFS" % index)
                    return index, "premier T du fichier"
    except OSError as exception:
        return -1, "fichier illisible: %s" % exception
    return 0, "aucun T dans le fichier, mono-filament"


class KctrlSlotMap:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.path = config.get("path", DEFAULT_PATH)
        self.map = {}
        self.error = ""
        # (mtime, size) of the file behind the cached map. get_status runs on
        # every Moonraker poll, so the file is stat'd rather than parsed.
        self.stamp = None
        # Which filament of the job is loaded first, and the sliced file that
        # answer was read from. Same caching rule: the file is stat'd on every
        # poll and parsed only when it changes, so a print costs one scan.
        self.initial_index = 0
        self.initial_note = "aucun fichier en cours"
        self.initial_file = ""
        self.initial_stamp = None
        gcode = self.printer.lookup_object("gcode")
        gcode.register_command(
            "KCTRL_MAP", self.cmd_KCTRL_MAP, desc=self.cmd_KCTRL_MAP_help)

    def stat(self, path=None):
        try:
            info = os.stat(path if path is not None else self.path)
        except OSError:
            return None
        return (info.st_mtime, info.st_size)

    def status_of(self, name):
        """get_status of another object, without waking the reactor.

        This runs on every poll, including in the middle of a print, and the
        objects read here ignore the timestamp they are handed.
        """
        obj = self.printer.lookup_object(name, None)
        if obj is None:
            return {}
        try:
            return obj.get_status(None) or {}
        except Exception:
            return {}

    def printing_file(self):
        """Absolute path of the file virtual_sdcard is running, or ''."""
        status = self.status_of("virtual_sdcard")
        if not status:
            return ""
        path = status.get("file_path") or ""
        if path:
            return path
        # Older Creality builds publish the name only. The directory is the one
        # virtual_sdcard was configured with, and it is the only one it reads.
        name = self.status_of("print_stats").get("filename") or ""
        sdcard = self.printer.lookup_object("virtual_sdcard", None)
        folder = getattr(sdcard, "sdcard_dirname", "")
        if name and folder:
            return os.path.join(folder, name)
        return ""

    def refresh_initial(self, path=None):
        """Re-read the initial tool of the job, only when the file changed."""
        target = path if path is not None else self.printing_file()
        if not target:
            self.initial_index = 0
            self.initial_file = ""
            self.initial_stamp = None
            self.initial_note = "aucun fichier en cours"
            return
        stamp = self.stat(target)
        unchanged = (stamp is not None and target == self.initial_file
                     and stamp == self.initial_stamp)
        if unchanged:
            return
        self.initial_file = target
        self.initial_stamp = stamp
        self.initial_index, self.initial_note = scan_initial_tool(target)

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
        self.refresh_initial()
        logical = logical_of_index(self.initial_index)
        return {
            "map": dict(self.map),
            "loaded": 1 if self.map else 0,
            "error": self.error,
            "path": self.path,
            # Zero based, the slicer's own numbering: 0 is T0 and logical T1A.
            "initial_index": self.initial_index,
            "initial_logical": logical,
            "initial_slot": self.map.get(logical, ""),
            "initial_note": self.initial_note,
            "initial_file": self.initial_file,
        }

    cmd_KCTRL_MAP_help = (
        "Show which physical CFS slot each filament of a job resolves to")

    def cmd_KCTRL_MAP(self, gcmd):
        self.refresh()
        self.refresh_initial(gcmd.get("FILE", None))
        start = logical_of_index(self.initial_index)
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
            # reads. An entry is shown when it points at a loaded slot, when it
            # has been remapped and so carries a decision, or when it is the one
            # the job starts on - that one is always worth a line.
            if empty and physical == logical and logical != start:
                continue
            detail = "vide" if empty else ("matiere %s, couleur %s"
                                           % (material, color))
            mark = "" if physical == logical else "   <- remappe"
            if logical == start:
                mark += "   <== charge au depart"
            lines.append("  filament %d (%s) -> %s   %s%s"
                         % (position, logical, physical, detail, mark))
        if start:
            lines.append("  depart sur le filament %d (%s), %s"
                         % (self.initial_index + 1, start, self.initial_note))
        else:
            lines.append("  depart indetermine: %s" % self.initial_note)
        if self.initial_file:
            lines.append("  fichier lu: %s" % self.initial_file)
        gcmd.respond_info("\n".join(lines))


def load_config(config):
    return KctrlSlotMap(config)
