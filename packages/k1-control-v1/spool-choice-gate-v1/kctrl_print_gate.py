# K1 Control: no print starts before the operator has connected every
# filament the file uses to a CFS spool of their choosing.
#
# Deployed to /usr/share/klipper/klippy/extras/kctrl_print_gate.py, enabled by
# a [kctrl_print_gate] section placed after [kctrl_slot_map]. Like the other
# Python extras it needs a klipper service restart, not a FIRMWARE_RESTART.
#
# Every way of starting a print on this machine ends in one command: Moonraker
# turns a Mainsail, Fluidd, screen or Creality Print start into
# SDCARD_PRINT_FILE FILENAME=... (the logs of this machine show that command
# and never M23). At connect time that command is taken over: the stock
# handler is kept under _KCTRL_GATE_STOCK_PRINT_FILE and only ever runs from
# KCTRL_GATE_CONFIRM, once every filament the file uses points at a loaded
# spool the operator picked on the Bobines page. Until then the file waits,
# nothing heats, nothing moves, and Mainsail shows a prompt saying so.
#
# What the page needs is published as status: the filaments the file declares
# and which of them it uses, the spools loaded in each slot with their type and
# colour, and the exact candidates for each filament. The page writes back one
# command, KCTRL_GATE_CONFIRM MAP=T1A:T2D,T1B:T1B, and the table is written
# with the same two commands KCTRL_SLOT and KCTRL_MATCH use, then the stock
# start runs. START_PRINT sees confirmed_file equal to the file it is starting
# and leaves the table alone instead of matching by colour (ADR-063).
#
# Two starts pass straight through: a power-loss resume (ISCONTINUEPRINT),
# which continues a job whose choice was already made, and a start while the
# SD card is busy or the file does not exist, which the stock handler refuses
# with its own message.

import logging
import os
import re
import sys
import time

STOCK = "_KCTRL_GATE_STOCK_PRINT_FILE"
HEAD = re.compile(r"^\s*(?:N\d+\s*)?SDCARD_PRINT_FILE\b(.*)$", re.IGNORECASE | re.DOTALL)
# A tool change is a line of its own: T followed by a number, spaces around
# allowed as Klipper allows them, optionally a comment. Scanned on whole
# chunks, not line by line: a 50 MB job is a few seconds of Python per line
# and well under a second for the regex engine.
TOOL_IN_CHUNK = re.compile(rb"(?m)^[ \t]*T(\d+)[ \t]*(?:;[^\r\n]*)?\r?$")
CHUNK = 1 << 20
PAIR = re.compile(r"^(T[1-4][A-D]):(T[1-4][A-D])$")
BOXES = ("1", "2", "3", "4")
SLOTS = ("A", "B", "C", "D")
NAMES = tuple("T" + box + slot for box in BOXES for slot in SLOTS)


def _slot_map_module():
    """The kctrl_slot_map module, which owns the file and spool readers."""
    module = sys.modules.get("extras.kctrl_slot_map")
    if module is None:
        import importlib
        module = importlib.import_module("extras.kctrl_slot_map")
    return module


def parse_map(text):
    """'T1A:T2D,T1B:T1B' -> {'T1A': 'T2D', 'T1B': 'T1B'}; ValueError says why."""
    mapping = {}
    for item in str(text or "").split(","):
        item = item.strip().upper()
        if not item:
            continue
        found = PAIR.match(item)
        if found is None:
            raise ValueError("entree '%s' illisible, attendu T1A:T2D" % item)
        logical, slot = found.group(1), found.group(2)
        if logical in mapping:
            raise ValueError("filament %s donne deux fois" % logical)
        mapping[logical] = slot
    if not mapping:
        raise ValueError("MAP vide, attendu MAP=T1A:T2D,T1B:T1B")
    return mapping


def scan_used_tools(path, breathe=None):
    """Every filament number the file selects, in order of first use.

    (indices, note). Read in 1 MB chunks; `breathe` is called between chunks
    so a long file never holds the reactor. A file without a tool command is
    mono-filament on the slicer's first filament, index 0.
    """
    seen = []
    try:
        with open(path, "rb") as handle:
            tail = b""
            while True:
                chunk = handle.read(CHUNK)
                if not chunk:
                    break
                buffer = tail + chunk
                cut = buffer.rfind(b"\n") + 1
                body, tail = buffer[:cut], buffer[cut:]
                for found in TOOL_IN_CHUNK.finditer(body):
                    index = int(found.group(1))
                    if index not in seen:
                        seen.append(index)
                if breathe is not None:
                    breathe()
            for found in TOOL_IN_CHUNK.finditer(tail + b"\n"):
                index = int(found.group(1))
                if index not in seen:
                    seen.append(index)
    except OSError as exception:
        return None, "fichier illisible: %s" % exception
    if not seen:
        return [0], "aucun T dans le fichier, mono-filament"
    return seen, "%d filament(s) utilise(s)" % len(seen)


class KctrlPrintGate:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object("gcode")
        self.reactor = self.printer.get_reactor()
        # Where the page is, as shown in the console and the Mainsail prompt.
        self.page = config.get("page", "/bobines/")
        self.pending = None
        self.confirmed = None
        self.wrapped = False
        self.last = "rien encore"
        # [virtual_sdcard] registers SDCARD_PRINT_FILE after this section is
        # read (printer.cfg includes this file before it), so the takeover
        # waits for every section to be loaded.
        self.printer.register_event_handler("klippy:connect", self._wrap)
        self.gcode.register_command(
            "KCTRL_GATE_CONFIRM", self.cmd_KCTRL_GATE_CONFIRM,
            desc=self.cmd_KCTRL_GATE_CONFIRM_help)
        self.gcode.register_command(
            "KCTRL_GATE_CANCEL", self.cmd_KCTRL_GATE_CANCEL,
            desc=self.cmd_KCTRL_GATE_CANCEL_help)
        self.gcode.register_command(
            "KCTRL_GATE", self.cmd_KCTRL_GATE, desc=self.cmd_KCTRL_GATE_help)

    def _wrap(self):
        stock = self.gcode.register_command("SDCARD_PRINT_FILE", None)
        if stock is None:
            self.wrapped = False
            logging.error("kctrl_print_gate: SDCARD_PRINT_FILE is not registered, "
                          "no gate on this machine")
            return
        self.gcode.register_command(STOCK, stock)
        self.gcode.register_command(
            "SDCARD_PRINT_FILE", self.cmd_SDCARD_PRINT_FILE,
            desc="K1 Control: hold the file until its filaments are connected "
                 "to CFS spools on the Bobines page, then start it")
        self.wrapped = True
        logging.info("kctrl_print_gate: wrapped SDCARD_PRINT_FILE; stock kept as %s",
                     STOCK)

    # ------------------------------------------------------------ helpers
    def status_of(self, name):
        obj = self.printer.lookup_object(name, None)
        if obj is None:
            return {}
        try:
            return obj.get_status(self.reactor.monotonic()) or {}
        except Exception:
            return {}

    def print_state(self):
        return str(self.status_of("print_stats").get("state", ""))

    def sd_busy(self):
        sdcard = self.printer.lookup_object("virtual_sdcard", None)
        if sdcard is None:
            return False
        try:
            return bool(sdcard.is_active())
        except Exception:
            return False

    def resolve(self, filename):
        """The path the stock handler would open, built the same way."""
        sdcard = self.printer.lookup_object("virtual_sdcard", None)
        folder = getattr(sdcard, "sdcard_dirname", "") if sdcard is not None else ""
        name = str(filename)
        if name.startswith("/"):
            name = name[1:]
        return os.path.join(folder, name) if folder else name

    def breathe(self):
        self.reactor.pause(self.reactor.monotonic() + 0.001)

    def slot_map(self):
        return self.printer.lookup_object("kctrl_slot_map", None)

    def identities(self):
        """{slot: {material, type, colour}} for every loaded slot."""
        module = _slot_map_module()
        slot_map = self.slot_map()
        types = {}
        if slot_map is not None:
            try:
                slot_map.refresh_temps()
                types = dict(slot_map.types)
            except Exception:
                types = {}
        return module.slot_identities(self.status_of("box"), types)

    def slots_status(self):
        """Every slot of every connected unit, loaded or empty, for the page."""
        box = self.status_of("box")
        identities = self.identities()
        slots = {}
        units = []
        for unit_id in BOXES:
            unit = box.get("T" + unit_id) or {}
            if str(unit.get("state", "None")) != "connect":
                continue
            units.append("T" + unit_id)
            remains = unit.get("remain_len") or []
            for index, letter in enumerate(SLOTS):
                name = "T" + unit_id + letter
                identity = identities.get(name)
                try:
                    remain = int(float(remains[index]))
                except (IndexError, TypeError, ValueError):
                    remain = -1
                if identity is None:
                    slots[name] = {"loaded": 0, "type": "", "colour": "",
                                   "material": "", "remain": remain}
                else:
                    slots[name] = {"loaded": 1, "type": identity["type"],
                                   "colour": identity["colour"],
                                   "material": identity["material"],
                                   "remain": remain}
        return slots, units

    def filaments_of(self, job, used):
        """One entry per filament the file declares or uses, in slicer order."""
        module = _slot_map_module()
        count = int(job.get("count", 0) or 0)
        indices = sorted(set(range(count)) | set(used or []))
        kinds = job.get("types") or []
        colours = job.get("colours") or []
        names = job.get("names") or []
        entries = []
        for index in indices:
            logical = module.logical_of_index(index)
            entries.append({
                "index": index,
                "logical": logical,
                "type": (kinds[index] if index < len(kinds) else "").strip().upper(),
                "colour": module.colour_key(colours[index] if index < len(colours) else ""),
                "name": (names[index] if index < len(names) else "").strip(),
                "declared": 1 if index < count else 0,
                "used": 1 if index in (used or []) else 0,
            })
        return entries

    def candidates(self, filaments, identities):
        """exact (same type and colour) and same_type spools per filament."""
        out = []
        for entry in filaments:
            same_type = [name for name in NAMES if name in identities
                         and entry["type"] and identities[name]["type"] == entry["type"]]
            exact = [name for name in same_type
                     if entry["colour"] and identities[name]["colour"] == entry["colour"]]
            item = dict(entry)
            item["same_type"] = same_type
            item["exact"] = exact
            out.append(item)
        return out

    def prompt_open(self, name, used_count):
        lines = [
            "// action:prompt_begin Choix des bobines",
            "// action:prompt_text Le fichier %s attend que vous raccordiez "
            "%s aux bobines du CFS. Rien ne chauffe tant que ce n'est pas fait."
            % (name, "son filament" if used_count == 1
               else "ses %d filaments" % used_count),
            "// action:prompt_text Ouvrez la page Bobines : %s" % self.page,
            "// action:prompt_footer_button Annuler cette impression|KCTRL_GATE_CANCEL|error",
            "// action:prompt_show",
        ]
        for line in lines:
            self.gcode.respond_raw(line)

    def prompt_close(self):
        self.gcode.respond_raw("// action:prompt_end")

    def start_stock(self, rest):
        self.gcode.run_script_from_command(STOCK + rest)

    # ----------------------------------------------------------- commands
    def cmd_SDCARD_PRINT_FILE(self, gcmd):
        line = gcmd.get_commandline()
        found = HEAD.match(line)
        rest = found.group(1) if found is not None else ""
        if not rest.strip():
            # Nothing to replay from the line itself: rebuild the parameters.
            rest = " " + " ".join(
                '%s="%s"' % (key, value)
                for key, value in gcmd.get_command_parameters().items())
        filename = gcmd.get("FILENAME")
        if gcmd.get("ISCONTINUEPRINT", None) is not None:
            self.last = "reprise apres coupure passee sans choix: %s" % filename
            logging.info("kctrl_print_gate: %s", self.last)
            self.start_stock(rest)
            return
        if self.sd_busy() or self.print_state() in ("printing", "paused"):
            self.start_stock(rest)
            return
        path = self.resolve(filename)
        if not os.path.isfile(path):
            self.start_stock(rest)
            return
        module = _slot_map_module()
        job, job_note = module.read_job_filaments(path)
        used, used_note = scan_used_tools(path, self.breathe)
        if used is None:
            raise gcmd.error("K1 Control: %s" % used_note)
        filaments = self.filaments_of(job, used)
        self.confirmed = None
        self.pending = {
            "file": path,
            "name": str(filename),
            "rest": rest,
            "since": time.time(),
            "job": job,
            "used": list(used),
            "filaments": filaments,
            "note": "%s, %s" % (job_note, used_note),
        }
        used_count = len(used)
        self.last = "en attente du choix pour %s" % filename
        logging.info("kctrl_print_gate: holding %s (%s)", path, self.pending["note"])
        gcmd.respond_info(
            "K1 Control: %s attend le choix des bobines (%s). Raccordez %s "
            "sur la page Bobines %s puis lancez; KCTRL_GATE_CANCEL pour "
            "abandonner. Rien ne chauffe."
            % (filename, self.pending["note"],
               "son filament" if used_count == 1 else "ses %d filaments" % used_count,
               self.page))
        self.prompt_open(str(filename), used_count)

    cmd_KCTRL_GATE_CONFIRM_help = (
        "Connect the waiting file's filaments to CFS slots and start it, "
        "e.g. KCTRL_GATE_CONFIRM MAP=T1A:T2D,T1B:T1B")

    def cmd_KCTRL_GATE_CONFIRM(self, gcmd):
        pending = self.pending
        if pending is None:
            raise gcmd.error("K1 Control: aucune impression n'attend un choix de "
                             "bobines; lancez le fichier depuis Mainsail d'abord")
        expected = gcmd.get("FILE", None)
        if expected is not None and expected not in (pending["name"], pending["file"]):
            raise gcmd.error("K1 Control: la page parle de %s mais le fichier en "
                             "attente est %s; rechargez la page"
                             % (expected, pending["name"]))
        try:
            mapping = parse_map(gcmd.get("MAP"))
        except ValueError as exception:
            raise gcmd.error("K1 Control: %s" % exception)
        state = self.print_state()
        if state in ("printing", "paused") or self.sd_busy():
            raise gcmd.error("K1 Control: impression en cours (%s), rien n'est "
                             "lance par-dessus" % (state or "SD occupee"))
        known = {entry["logical"]: entry for entry in pending["filaments"]}
        unknown = [logical for logical in mapping if logical not in known]
        if unknown:
            raise gcmd.error("K1 Control: le fichier n'a pas de filament %s"
                             % ", ".join(unknown))
        missing = [entry["logical"] for entry in pending["filaments"]
                   if entry["used"] and entry["logical"] not in mapping]
        if missing:
            raise gcmd.error("K1 Control: filament(s) sans bobine: %s; chaque "
                             "filament utilise par le fichier doit etre raccorde"
                             % ", ".join(missing))
        identities = self.identities()
        empty = [slot for slot in mapping.values() if slot not in identities]
        if empty:
            raise gcmd.error("K1 Control: emplacement(s) vide(s) ou unite non "
                             "connectee: %s" % ", ".join(sorted(set(empty))))
        lines = ["K1 Control: bobines raccordees pour %s" % pending["name"]]
        for logical in NAMES:
            if logical not in mapping:
                continue
            slot = mapping[logical]
            entry = known[logical]
            self.gcode.run_script_from_command("BOX_MODIFY_TN %s=%s" % (logical, slot))
            self.gcode.run_script_from_command(
                "SAVE_VARIABLE VARIABLE=slot_choice_%s VALUE='\"%s\"'"
                % (logical.lower(), slot))
            if logical == "T1A":
                self.gcode.run_script_from_command(
                    "SAVE_VARIABLE VARIABLE=slot_last_choice VALUE='\"%s\"'" % slot)
            identity = identities[slot]
            lines.append("  filament %d (%s) %s %s -> %s, %s %s%s" % (
                entry["index"] + 1, logical, entry["type"] or "?",
                entry["colour"] or "sans couleur", slot,
                identity["type"] or "?", identity["colour"] or "-",
                "" if entry["used"] else ", declare mais non utilise"))
        slot_map = self.slot_map()
        if slot_map is not None:
            # The table on disk changed under its cache.
            slot_map.stamp = None
        self.confirmed = {
            "file": pending["file"], "name": pending["name"],
            "at": time.time(), "map": dict(mapping),
        }
        self.pending = None
        self.prompt_close()
        lines.append("  impression lancee: %s" % pending["name"])
        gcmd.respond_info("\n".join(lines))
        self.last = "lance avec %s: %s" % (
            ", ".join("%s=%s" % (k, mapping[k]) for k in NAMES if k in mapping),
            pending["name"])
        logging.info("kctrl_print_gate: %s", self.last)
        try:
            self.start_stock(pending["rest"])
        except Exception:
            self.confirmed = None
            self.last = "le demarrage a echoue apres le choix: %s" % pending["name"]
            raise

    cmd_KCTRL_GATE_CANCEL_help = "Forget the file waiting for a spool choice"

    def cmd_KCTRL_GATE_CANCEL(self, gcmd):
        pending = self.pending
        self.pending = None
        self.prompt_close()
        if pending is None:
            gcmd.respond_info("K1 Control: aucune impression en attente")
            return
        self.last = "abandonne: %s" % pending["name"]
        logging.info("kctrl_print_gate: %s", self.last)
        gcmd.respond_info("K1 Control: impression abandonnee, %s ne partira pas"
                          % pending["name"])

    cmd_KCTRL_GATE_help = "Show the file waiting for a spool choice, if any"

    def cmd_KCTRL_GATE(self, gcmd):
        status = self.get_status()
        lines = ["K1 Control: porte de depart %s, page %s"
                 % ("active" if status["wrapped"] else "INACTIVE", self.page)]
        if status["pending"]:
            lines.append("  en attente: %s (%s)" % (status["name"], status["note"]))
            for entry in status["filaments"]:
                lines.append("    filament %d (%s) %s %s%s, identiques: %s" % (
                    entry["index"] + 1, entry["logical"], entry["type"] or "?",
                    entry["colour"] or "sans couleur",
                    "" if entry["used"] else " (declare, non utilise)",
                    ", ".join(entry["exact"]) or "aucune"))
        else:
            lines.append("  aucune impression en attente")
        for name in NAMES:
            slot = status["slots"].get(name)
            if slot is None:
                continue
            lines.append("    %s %s" % (name, "vide" if not slot["loaded"] else
                                        "%s %s, reste %s%%" % (slot["type"] or "?",
                                                              slot["colour"] or "-",
                                                              slot["remain"])))
        lines.append("  dernier evenement: %s" % status["last"])
        gcmd.respond_info("\n".join(lines))

    # ------------------------------------------------------------- status
    def get_status(self, eventtime=None):
        slots, units = self.slots_status()
        identities = {name: slot for name, slot in slots.items() if slot["loaded"]}
        pending = self.pending
        filaments = self.candidates(pending["filaments"], identities) if pending else []
        confirmed = self.confirmed or {}
        slot_map = self.slot_map()
        table = {}
        if slot_map is not None:
            try:
                slot_map.refresh()
                table = dict(slot_map.map)
            except Exception:
                table = {}
        return {
            "wrapped": 1 if self.wrapped else 0,
            "page": self.page,
            "pending": 1 if pending else 0,
            "file": pending["file"] if pending else "",
            "name": pending["name"] if pending else "",
            "since": pending["since"] if pending else 0,
            "note": pending["note"] if pending else "",
            "filaments": filaments,
            "used_count": len(pending["used"]) if pending else 0,
            "declared_count": int(pending["job"].get("count", 0) or 0) if pending else 0,
            "slots": slots,
            "units": units,
            "table": table,
            "confirmed_file": confirmed.get("file", ""),
            "confirmed_name": confirmed.get("name", ""),
            "confirmed_at": confirmed.get("at", 0),
            "confirmed_map": dict(confirmed.get("map", {})),
            "last": self.last,
        }


def load_config(config):
    return KctrlPrintGate(config)
