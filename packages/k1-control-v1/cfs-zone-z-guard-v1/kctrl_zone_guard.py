"""Refuse a Z that would drive the bed into the head in the CFS service zone.

On 2026-09-09 the head went to the purge chute, the bed rose to its top stop
and jammed the head in the chute. Thomas cut the power to stop the motors from
grinding. What the gcode store held afterwards was this, in that order:

    // Cut sensor not triggered.
    !! key841 "cut error, cut sensor not detected, cutting not rebound"
    // can_break_flag = 3
    !! key243 "Move out of range: 185.500 291.500 -18.951 [233.500]"

185.5 is `extrude_pos_x` and 291.5 is `safe_pos_y`, both from box.cfg: the CFS
service zone behind the bed. -18.951 is a Z below `position_min: -10`, which is
why Klipper refused that one. The refusal is the proof that the routine
computes its Z instead of reading it back, and a computed Z anywhere in
[-10, 0) is accepted, executed, and drives the bed above the nozzle plane. That
is the jam.

The routine belongs to `box_wrapper.cpython-38-mipsel-linux-gnu.so`. It is
compiled, unmodifiable, and it fires on its own whenever the CFS decides the
filament broke (`can_break_flag = 3`). Nothing in box.cfg switches it off. So
the guard has to sit under it, in the one place every motion passes through:
`ToolHead.move`.

The zone is defined by the machine, not by us. `[stepper_y]` declares
`position_max: 307.5` and `gcode_position_max: 295`: a sliced file cannot ask
for a Y beyond 295, only the CFS primitives reach 296 and above. So a floor
that applies from Y 296 outward cannot touch printing, probing, meshing or
homing. It only touches the CFS. That is where the head was when it jammed:
the purge chute is `extrude_pos_y: 305.0`, the cutter `cut_pos_y: 303.2`, the
wiper `clean_left_pos_y: 305.5`.

What this guard deliberately does NOT cover: the Y 291.5 of the logged refusal.
`safe_pos_y: 291.5` sits under `gcode_position_max: 295`, so a sliced file can
legitimately reach it, and `[bed_mesh]` declares `mesh_max: 295,295`, so the
probe can too. A Z floor there would have to tell a CFS retreat apart from a
probe point, and nothing in the move itself says which is which. Klipper
already refused that particular move on its own (`position_min: -10` for Z),
which is exactly how -18.951 got into the log. The gap that stays open is a Z
between -10 and 0 at Y 285..295 - the nozzle into the plate rather than the
head into the chute. It is written down here rather than papered over.

The floor is Z 0. Beyond the rear edge of the bed there is no bed under the
nozzle, so no CFS operation has a reason to ask for a bed above the nozzle
plane; every cut, wipe and purge position in box.cfg sits well above it
(`extrude_pos_z: 30.0`). Anything below 0 out there is the computed Z going
wrong, and the only honest answer is to refuse it and say so, the way Klipper
refused -18.951 by itself.

Refusing turns a jam into a paused print. That is the whole point: a paused
print is recoverable, a head pressed into the chute is not.

The guard wraps `toolhead.move` at `klippy:connect`, before `gcode_move`
captures it at `klippy:ready`, so both paths are covered: the primitives that
call the toolhead directly, and the G-code path, whose transform chain
(bed_mesh, skew) ends on a fresh attribute lookup of `toolhead.move`. The check
itself is one float comparison on the target Y, which is false for every move
of a real print.
"""

import logging


class KctrlZoneGuard:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object("gcode")
        self.zone_y_min = config.getfloat("zone_y_min", 296.0)
        self.z_floor = config.getfloat("z_floor", 0.0)
        self.action = config.getchoice(
            "action", {"refuse": "refuse", "clamp": "clamp"}, "refuse"
        )
        self.enabled = config.getboolean("enable", True)
        self.installed = False
        self.trips = 0
        self.last_trip = ""
        self.printer.register_event_handler("klippy:connect", self._connect)
        self.gcode.register_command(
            "KCTRL_ZONE_GUARD", self.cmd_KCTRL_ZONE_GUARD,
            desc="Etat du garde Z de la zone de service CFS",
        )

    def _connect(self):
        toolhead = self.printer.lookup_object("toolhead")
        if self.installed:
            return
        original = toolhead.move
        zone_y_min = self.zone_y_min

        def guarded_move(newpos, speed):
            if newpos[1] >= zone_y_min and self.enabled:
                newpos = self._inspect(newpos)
            return original(newpos, speed)

        toolhead.move = guarded_move
        self.installed = True
        logging.info(
            "kctrl_zone_guard: armed, Y >= %.1f requires Z >= %.3f (%s)",
            self.zone_y_min, self.z_floor, self.action,
        )

    def _inspect(self, newpos):
        z = newpos[2]
        if z >= self.z_floor:
            return newpos
        self.trips += 1
        self.last_trip = "X%.3f Y%.3f Z%.3f" % (newpos[0], newpos[1], z)
        detail = (
            "zone de service CFS (Y >= %.1f) : Z %.3f demande, plancher %.3f"
            % (self.zone_y_min, z, self.z_floor)
        )
        logging.warning("kctrl_zone_guard: trip %d, %s -> %s",
                        self.trips, self.last_trip, self.action)
        if self.action == "clamp":
            self.gcode.respond_info(
                "K1 Control: garde Z, %s -- Z releve au plancher" % (detail,)
            )
            clamped = list(newpos)
            clamped[2] = self.z_floor
            return clamped
        raise self.printer.command_error(
            "K1 Control: garde Z, mouvement refuse. %s. "
            "C'est la routine CFS qui calcule un Z hors plage ; la laisser "
            "passer coince la tete dans la goulotte de purge." % (detail,)
        )

    def cmd_KCTRL_ZONE_GUARD(self, gcmd):
        enable = gcmd.get_int("ENABLE", None)
        if enable is not None:
            self.enabled = bool(enable)
        gcmd.respond_info(
            "garde Z zone CFS : %s, Y >= %.1f impose Z >= %.3f, action %s, "
            "%d refus%s"
            % (
                "actif" if self.enabled else "inactif",
                self.zone_y_min, self.z_floor, self.action, self.trips,
                (" (dernier %s)" % self.last_trip) if self.last_trip else "",
            )
        )

    def get_status(self, eventtime=None):
        return {
            "enabled": self.enabled,
            "installed": self.installed,
            "zone_y_min": self.zone_y_min,
            "z_floor": self.z_floor,
            "action": self.action,
            "trips": self.trips,
            "last_trip": self.last_trip,
        }


def load_config(config):
    return KctrlZoneGuard(config)
