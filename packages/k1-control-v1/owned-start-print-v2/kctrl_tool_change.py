"""Wrap the CFS tool-change commands so a mid-print change heats to the file.

T0..T15 are registered by the compiled CFS module (box_wrapper). Each one is
the whole filament change: cut, retract, feed the new spool, pull it to the
nozzle, purge over the bin, restore Z. Its temperatures come from the material
record of the slot it pulls from - the cloud value of the material, rewritten
by the firmware at every boot - never from what the sliced file asked for.
START_PRINT already aligns the record of the filament the job starts on
(KCTRL_MATERIAL_ALIGN, docs/67). Every later T of the file went through the
stock command untouched, so a two-filament job changed spools at whatever the
cloud said for that material. This is point 4 of the daily flow of
2026-09-10: "Le multi-filament en cours d'impression est bien géré".

This object takes the sixteen commands over at load time, the way a
gcode_macro with rename_existing would, and around each stock change it:

  1. resolves the slot the filament points at (the same tnn_map the stock
     command reads, through kctrl_slot_map) and refuses clearly when the
     filament points nowhere, at an absent unit or at an empty slot - the
     stock command fails those silently, "return False", and the print goes
     on printing air;
  2. reads the temperature the sliced file gives that filament (first layer
     or running, from the config block at the end of the file) and writes it
     into the material record of that slot, the way START_PRINT does for the
     first one;
  3. calls the stock command;
  4. outside START_PRINT: waits for the queue, and if the head sensor sees
     no filament the print is paused with a message rather than continued
     into the void; otherwise the nozzle target is set back to the file's
     value, because the stock purge leaves it at max(record, 200).

It must be loaded after [box], which is where the commands come from: this
section lives in a file included after box.cfg. A T that the box did not
register is left alone and listed by KCTRL_TOOLS; nothing here fails the
Klipper start.

The order of the sixteen names is the slicer's: T0 is the job's first
filament and the logical slot T1A; T15 the sixteenth and T4D. Same
convention as kctrl_slot_map.py.
"""

import logging

BOXES = ("1", "2", "3", "4")
SLOTS = ("A", "B", "C", "D")
NAMES = tuple("T" + box + slot for box in BOXES for slot in SLOTS)
TEMP_MIN, TEMP_MAX = 150.0, 320.0


def material_key(slot_type):
    text = str(slot_type)
    if len(text) == 6 and text.startswith("0"):
        return text[1:]
    return text


class Refusal(Exception):
    """The change cannot be made safely; the message says why, in French."""


class KctrlToolChange:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object("gcode")
        self.sensor = config.get("sensor", "filament_sensor_2")
        # 1 pauses the print when the change ends without filament at the
        # head; 0 only says so. Pausing is the default because the alternative
        # is a part finished with nothing coming out of the nozzle.
        self.pause_on_empty = config.getint("pause_on_empty", 1, minval=0, maxval=1)
        self.wrapped = []
        self.missing = []
        self.last = {}
        for index in range(len(NAMES)):
            name = "T%d" % index
            stock = self.gcode.register_command(name, None)
            if stock is None:
                self.missing.append(name)
                continue
            self.wrapped.append(name)
            self.gcode.register_command(
                name, self.handler(index, stock),
                desc="K1 Control: tool change to filament %d of the job, "
                     "aligned on the file, then the CFS command" % (index + 1))
        self.gcode.register_command(
            "KCTRL_TOOLS", self.cmd_KCTRL_TOOLS, desc=self.cmd_KCTRL_TOOLS_help)
        logging.info("kctrl_tool_change: wrapped %s; not registered by the box: %s",
                     ",".join(self.wrapped) or "-", ",".join(self.missing) or "-")

    def handler(self, index, stock):
        def call(gcmd):
            self.change(index, stock, gcmd)
        return call

    # ------------------------------------------------------------ helpers
    def status_of(self, name):
        obj = self.printer.lookup_object(name, None)
        if obj is None:
            return {}
        try:
            return obj.get_status(self.printer.get_reactor().monotonic()) or {}
        except Exception:
            return {}

    def in_start(self):
        """True while START_PRINT runs: it owns the checks and the target."""
        try:
            return int(self.status_of("gcode_macro START_PRINT").get("start_running", 0)) == 1
        except (TypeError, ValueError):
            return False

    def head_sees_filament(self):
        return bool(self.status_of("filament_switch_sensor " + self.sensor)
                    .get("filament_detected", False))

    def is_paused(self):
        return bool(self.status_of("pause_resume").get("is_paused", False))

    def first_layer(self, job):
        """Below the second layer's height, in G-code coordinates."""
        try:
            z = float(self.status_of("gcode_move").get("gcode_position", [0, 0, 0])[2])
        except (TypeError, ValueError, IndexError):
            return False
        first = float(job.get("initial_layer_height") or 0.0)
        step = float(job.get("layer_height") or 0.0)
        if first <= 0.0:
            return False
        return z < first + max(step, 0.0) + 0.001

    def resolve(self, index):
        """Everything a change of filament `index` needs, or a Refusal.

        Returns None when there is nothing to do here: the CFS is disabled,
        or no file is printing (a T typed at the console). The stock command
        then runs alone, as before.
        """
        slot_map = self.printer.lookup_object("kctrl_slot_map", None)
        box = self.printer.lookup_object("box", None)
        if slot_map is None or box is None:
            return None
        state = self.status_of("box")
        try:
            if int(state.get("enable", 0)) != 1:
                return None
        except (TypeError, ValueError):
            return None
        target = slot_map.printing_file()
        if not target:
            return None
        slot_map.refresh()
        slot_map.refresh_job(target)
        job = slot_map.job
        position = index + 1
        logical = NAMES[index]
        if job["count"] == 0:
            raise Refusal("le fichier ne dit pas ses temperatures (%s); le CFS "
                          "chaufferait a la valeur du cloud" % slot_map.job_note)
        if index >= job["count"]:
            raise Refusal("le fichier ne declare que %d filament(s), pas de "
                          "filament %d" % (job["count"], position))
        physical = slot_map.map.get(logical)
        if physical is None:
            raise Refusal("le filament %d (%s) ne pointe sur aucun emplacement "
                          "(%s); KCTRL_SLOT SLOT=... TOOL=%s pour l'associer"
                          % (position, logical, slot_map.error or "table sans entree",
                             logical))
        unit = state.get("T" + physical[1], {})
        slot_index = SLOTS.index(physical[2])
        if str(unit.get("state", "None")) != "connect":
            raise Refusal("le filament %d (%s) veut l'emplacement %s, mais l'unite "
                          "CFS %s n'est pas connectee" % (position, logical, physical,
                                                           physical[1]))
        slot_type = str(unit.get("material_type", ["-1"] * 4)[slot_index])
        if slot_type in ("-1", "None", ""):
            raise Refusal("le filament %d (%s) veut l'emplacement %s, qui est vide; "
                          "KCTRL_SLOTS pour voir les bobines" % (position, logical,
                                                                 physical))
        first = self.in_start() or self.first_layer(job)
        temp = float((job["initial"] if first else job["temps"])[index])
        if temp < TEMP_MIN or temp > TEMP_MAX:
            raise Refusal("le fichier demande %d C pour le filament %d, hors de "
                          "la plage %d..%d" % (temp, position, TEMP_MIN, TEMP_MAX))
        return {
            "index": index, "position": position, "logical": logical,
            "physical": physical, "material": material_key(slot_type),
            "temp": temp, "first_layer": first,
            "type": job["types"][index], "colour": job["colours"][index],
            "slot_map": slot_map,
        }

    # ------------------------------------------------------------ the change
    def change(self, index, stock, gcmd):
        name = "T%d" % index
        try:
            plan = self.resolve(index)
        except Refusal as exception:
            self.last = {"tool": name, "outcome": "refuse", "detail": str(exception)}
            raise gcmd.error("K1 Control: changement d'outil %s refuse, %s"
                             % (name, exception))
        if plan is None:
            self.last = {"tool": name, "outcome": "stock", "detail": "hors travail"}
            stock(gcmd)
            return
        try:
            changed, record, before = plan["slot_map"].align(plan["material"], plan["temp"])
        except Exception as exception:
            self.last = {"tool": name, "outcome": "refuse", "detail": str(exception)}
            raise gcmd.error("K1 Control: changement d'outil %s refuse, fiche "
                             "matiere %s non alignee (%s); le chargeur CFS "
                             "chaufferait a une valeur que personne n'a choisie"
                             % (name, plan["material"], exception))
        gcmd.respond_info(
            "K1 Control: %s -> filament %d (%s) sur %s, %s %s, fiche %s (%s) %s %d C%s"
            % (name, plan["position"], plan["logical"], plan["physical"],
               plan["type"] or "matiere ?", plan["colour"] or "",
               plan["material"], record,
               "alignee %s ->" % "/".join(str(v) for v in before) if changed else "deja a",
               plan["temp"], ", premiere couche" if plan["first_layer"] else ""))
        stock(gcmd)
        if self.in_start():
            # START_PRINT waits for the head sensor itself, with a grace
            # period, and restores the file temperature after the loader.
            self.last = {"tool": name, "outcome": "start", "slot": plan["physical"],
                         "temp": plan["temp"]}
            return
        self.gcode.run_script_from_command("M400")
        if self.is_paused():
            # The firmware paused on its own (cutter, feed): its screen says
            # why, and a resume goes through its own path. Nothing to add.
            self.last = {"tool": name, "outcome": "paused_by_firmware",
                         "slot": plan["physical"], "temp": plan["temp"]}
            gcmd.respond_info(
                "K1 Control: le firmware a mis l'impression en pause pendant "
                "%s -> %s; voir l'ecran, puis RESUME" % (name, plan["physical"]))
            return
        if not self.head_sees_filament():
            self.last = {"tool": name, "outcome": "empty", "slot": plan["physical"],
                         "temp": plan["temp"]}
            if self.pause_on_empty:
                self.gcode.run_script_from_command("PAUSE")
            gcmd.respond_info(
                "K1 Control: %s -> %s termine sans filament a la tete; %s"
                % (name, plan["physical"],
                   "impression mise en pause, charger a la main puis RESUME"
                   if self.pause_on_empty else "l'impression continue a vide"))
            return
        self.gcode.run_script_from_command("M104 S%d" % plan["temp"])
        self.last = {"tool": name, "outcome": "done", "slot": plan["physical"],
                     "temp": plan["temp"]}
        gcmd.respond_info("K1 Control: %s fait, filament a la tete, cible %d C"
                          % (name, plan["temp"]))

    # ------------------------------------------------------------ KCTRL_TOOLS
    cmd_KCTRL_TOOLS_help = (
        "Show each filament of the job: file temperatures, slot, material "
        "record; FILE=<path> for a file that is not printing")

    def cmd_KCTRL_TOOLS(self, gcmd):
        slot_map = self.printer.lookup_object("kctrl_slot_map", None)
        if slot_map is None:
            raise gcmd.error("K1 Control: kctrl_slot_map absent")
        target = gcmd.get("FILE", None) or slot_map.printing_file()
        lines = ["K1 Control: commandes T enveloppees: %s; laissees au CFS: %s"
                 % (", ".join(self.wrapped) or "aucune",
                    ", ".join(self.missing) or "aucune")]
        if not target:
            lines.append("  aucun fichier en cours; KCTRL_TOOLS FILE=/chemin/du/fichier.gcode")
            gcmd.respond_info("\n".join(lines))
            return
        slot_map.refresh()
        slot_map.refresh_job(target)
        slot_map.refresh_temps()
        job = slot_map.job
        state = self.status_of("box")
        lines.append("  fichier: %s, %s" % (target, slot_map.job_note))
        for index in range(job["count"]):
            logical = NAMES[index]
            physical = slot_map.map.get(logical)
            temps = "%d C (1re couche %d C)" % (job["temps"][index], job["initial"][index])
            head = "  filament %d (%s) %s %s, %s" % (
                index + 1, logical, job["types"][index] or "?",
                job["colours"][index] or "", temps)
            if physical is None:
                lines.append(head + " -> non associe")
                continue
            unit = state.get("T" + physical[1], {})
            slot_index = SLOTS.index(physical[2])
            slot_type = str(unit.get("material_type", ["-1"] * 4)[slot_index])
            if str(unit.get("state", "None")) != "connect":
                lines.append(head + " -> %s, unite non connectee" % physical)
            elif slot_type in ("-1", "None", ""):
                lines.append(head + " -> %s, emplacement vide" % physical)
            else:
                record = material_key(slot_type)
                now = slot_map.temps.get(record)
                lines.append(head + " -> %s, fiche %s a %s C%s" % (
                    physical, record,
                    "?" if now is None else "%d" % now,
                    "" if now is None or int(now) == int(job["temps"][index])
                    else " (sera alignee au changement)"))
        if self.last:
            lines.append("  dernier changement: %s" % ", ".join(
                "%s=%s" % (k, v) for k, v in sorted(self.last.items())))
        gcmd.respond_info("\n".join(lines))

    def get_status(self, eventtime=None):
        return {
            "wrapped": list(self.wrapped),
            "missing": list(self.missing),
            "last": dict(self.last),
        }


def load_config(config):
    return KctrlToolChange(config)
