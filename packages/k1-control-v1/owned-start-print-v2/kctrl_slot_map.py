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
# The temperature the stock loader will heat to, per material record. It reads
# this file and nothing else - see docs/67 - and the firmware rewrites it on its
# own at boot: measured on 2026-09-10, the record corrected to 200 C on the 9th
# was back at 220 C after the morning reboot, and the loading window then
# capped it at 205 C, a target the loader waits for and never reaches. So
# START_PRINT reads the same record before anything heats, and refuses early
# instead of hanging late.
DEFAULT_MATERIAL_DB = "/usr/data/creality/userdata/box/material_database.json"
TEMP_KEY = "nozzle_temperature"
BOXES = ("1", "2", "3", "4")
SLOTS = ("A", "B", "C", "D")
NAMES = tuple("T" + box + slot for box in BOXES for slot in SLOTS)

# T0..T15 in slicer order map onto T1A..T4D in that same order: T0 is the job's
# first filament and T1A its logical name, T15 the sixteenth and T4D.
TOOL_LINE = re.compile(rb"^T(\d+)\s*(?:;.*)?$")
# The initial tool sits a few lines after the start block. A megabyte is three
# orders of magnitude of margin and still one short read on the machine.
SCAN_LIMIT = 1 << 20
SCAN_CHUNK = 1 << 16


def is_slot_name(value):
    return isinstance(value, str) and value in NAMES


def material_key(slot_type):
    """The database id of a slot's material type.

    The slots publish the type on six characters, the database keys its
    records on five: a slot in 000001 loads at the temperature of record 00001.
    The leading zero is dropped, nothing else is guessed.
    """
    text = str(slot_type)
    if len(text) == 6 and text.startswith("0"):
        return text[1:]
    return text


def read_material_temps(path):
    """(temps, error): the loading temperature of every record, by id.

    Only records carrying both an id and a numeric nozzle_temperature are
    kept; a damaged record is skipped rather than turned into a number.
    """
    try:
        with open(path) as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exception:
        return {}, "base matiere illisible: %s" % exception
    records = data.get("result", {}).get("list") if isinstance(data, dict) else None
    if not isinstance(records, list):
        return {}, "base matiere sans liste de fiches"
    temps = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        base = record.get("base") or {}
        params = record.get("kvParam") or {}
        ident = base.get("id") if isinstance(base, dict) else None
        raw = params.get(TEMP_KEY) if isinstance(params, dict) else None
        if not ident or raw is None:
            continue
        try:
            temps[str(ident)] = float(raw)
        except (TypeError, ValueError):
            continue
    if not temps:
        return {}, "base matiere sans temperature exploitable"
    return temps, ""


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


def scan_all_tools(path):
    """Every filament number a sliced file selects, in order of first use.

    The initial tool is read from the first kilobytes; this one reads the whole
    file, because a colour change can sit at the last layer. It is meant for the
    preflight, not for get_status: a few megabytes is a few seconds on the K1.
    """
    seen = []
    try:
        with open(path, "rb") as handle:
            tail = b""
            while True:
                chunk = handle.read(SCAN_CHUNK)
                if not chunk:
                    break
                lines = (tail + chunk).split(b"\n")
                tail = lines.pop()
                for line in lines:
                    found = TOOL_LINE.match(line.strip())
                    if found is None:
                        continue
                    index = int(found.group(1))
                    if index not in seen:
                        seen.append(index)
            found = TOOL_LINE.match(tail.strip())
            if found is not None and int(found.group(1)) not in seen:
                seen.append(int(found.group(1)))
    except OSError as exception:
        return None, "fichier illisible: %s" % exception
    if not seen:
        return [0], "aucun T dans le fichier, mono-filament"
    return seen, "%d filament(s) utilise(s)" % len(seen)


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
        # Loading temperature per material record, same stat-then-parse rule.
        self.material_db = config.get("material_db", DEFAULT_MATERIAL_DB)
        self.temps = {}
        self.temps_error = ""
        self.temps_stamp = None
        gcode = self.printer.lookup_object("gcode")
        gcode.register_command(
            "KCTRL_MAP", self.cmd_KCTRL_MAP, desc=self.cmd_KCTRL_MAP_help)
        gcode.register_command(
            "KCTRL_CHECK", self.cmd_KCTRL_CHECK, desc=self.cmd_KCTRL_CHECK_help)

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

    def refresh_temps(self):
        stamp = self.stat(self.material_db)
        if stamp is None:
            self.temps = {}
            self.temps_stamp = None
            self.temps_error = "base matiere absente: %s" % self.material_db
            return
        if stamp == self.temps_stamp:
            return
        self.temps_stamp = stamp
        self.temps, self.temps_error = read_material_temps(self.material_db)

    def get_status(self, eventtime=None):
        self.refresh()
        self.refresh_initial()
        self.refresh_temps()
        logical = logical_of_index(self.initial_index)
        return {
            # Loading temperature by material record id, as the stock loader
            # will read it. Keyed on the five character id of the database;
            # material_key() turns a slot's six character type into it.
            "material_temp": dict(self.temps),
            "material_temp_error": self.temps_error,
            "material_db": self.material_db,
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

    cmd_KCTRL_CHECK_help = (
        "Check every filament a job uses against the spools actually loaded")

    def cmd_KCTRL_CHECK(self, gcmd):
        """Preflight: can this file print to the end with what is in the CFS?

        START_PRINT only ever loads the filament the job starts on. Everything
        after that is the stock cmd_T, which resolves against the same table and
        fails in the middle of a print - four hours in - when a filament points
        at a slot that is empty or at a unit that is not there. Asked here, the
        answer costs one full read of the file and no filament at all.
        """
        target = gcmd.get("FILE", None) or self.printing_file()
        if not target:
            raise gcmd.error("K1 Control: aucun fichier en cours; "
                             "KCTRL_CHECK FILE=/chemin/du/fichier.gcode")
        self.refresh()
        self.refresh_initial(target)
        used, note = scan_all_tools(target)
        if used is None:
            raise gcmd.error("K1 Control: %s" % note)
        box = self.printer.lookup_object("box", None)
        state = box.get_status(self.printer.get_reactor().monotonic()) if box else {}
        lines = ["K1 Control: controle avant impression, %s" % note]
        problems = []
        for index in sorted(used):
            logical = logical_of_index(index)
            if not logical:
                trouble = ("le filament %d depasse les 16 emplacements du CFS"
                           % (index + 1))
                lines.append("  filament %d   %s" % (index + 1, trouble))
                problems.append(trouble)
                continue
            physical = self.map.get(logical)
            if physical is None:
                trouble = ("le filament %d (%s) ne pointe sur aucun emplacement"
                           % (index + 1, logical))
                lines.append("  filament %d (%s) -> ?   %s"
                             % (index + 1, logical, "non associe"))
                problems.append(trouble)
                continue
            unit = state.get("T" + physical[1], {})
            slot_index = SLOTS.index(physical[2])
            connected = str(unit.get("state", "None")) == "connect"
            material = str(unit.get("material_type", ["-1"] * 4)[slot_index])
            empty = material in ("-1", "None", "")
            if not connected:
                verdict = "unite %s non connectee" % physical[1]
                problems.append("le filament %d (%s) veut %s, %s"
                                % (index + 1, logical, physical, verdict))
            elif empty:
                verdict = "emplacement vide"
                problems.append("le filament %d (%s) veut %s, %s"
                                % (index + 1, logical, physical, verdict))
            else:
                verdict = "matiere %s, pret" % material
            mark = "   <== charge au depart" if index == self.initial_index else ""
            lines.append("  filament %d (%s) -> %s   %s%s"
                         % (index + 1, logical, physical, verdict, mark))
        if problems:
            lines.append("  %d probleme(s); l'impression s'arreterait en cours"
                         % len(problems))
            lines.append("  KCTRL_SLOTS pour voir les bobines, "
                         "KCTRL_SLOT SLOT=... TOOL=... pour associer")
        else:
            lines.append("  tout est en place, le travail peut aller au bout")
        lines.append("  fichier lu: %s" % target)
        gcmd.respond_info("\n".join(lines))

def load_config(config):
    return KctrlSlotMap(config)
