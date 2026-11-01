"""Mechanical bin clearance at the kinematic check, below all G-code owners.

Checks real transformed XYZ, including stock direct toolhead calls. Never
generates a compensating move. A refusal cuts heat and raises a command error,
not an emergency stop. This protects the machine independently of START_PRINT.

The same layer refuses a filament push on a cold nozzle that nobody heats
(ADR-076). Creality commented out Klipper's own check in extruder.check_move,
so the stock CFS loop pushed down to 36 C on 2026-10-31. This check is
narrower than Klipper's: a retraction always passes, and a push passes while
the nozzle is at extrusion temperature or while its target reaches it. A
refusal raises a command error only: no heater, no motion, no shutdown.
"""

import logging

from .kctrl_start_policy import PurgeEnvelope, StartRefused

COLD_REVISION = 'cold-push-guard-v1'
COLD_LOG_SECONDS = 10.


class KctrlPurgeGuard:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.envelope = PurgeEnvelope()
        self.toolhead = None
        self.original_check = None
        self.denied = 0
        self.last_error = ''
        self.extruder = None
        self.heater = None
        self.original_extrude_check = None
        self.cold_refused = 0
        self.cold_last = ''
        self.cold_logged = None
        self.printer.register_event_handler('klippy:ready', self._ready)

    def _ready(self):
        if self.original_check is not None:
            return
        self.toolhead = self.printer.lookup_object('toolhead')
        kin = self.toolhead.get_kinematics()
        self.original_check = kin.check_move
        kin.check_move = self.check_move
        # toolhead.move calls extruder.check_move for every move with E.
        extruder = self.printer.lookup_object('extruder')
        self.heater = extruder.get_heater()
        self.original_extrude_check = extruder.check_move
        extruder.check_move = self.check_extrude
        self.extruder = extruder

    def check_move(self, move):
        # This hook is below gcode_move/bed_mesh and catches already-bound
        # toolhead.move references too. Do not replace the range/speed check.
        self.original_check(move)
        homed = self.toolhead.get_status(self.reactor.monotonic()).get('homed_axes', '')
        try:
            next_latch = self.envelope.check(move.start_pos, move.end_pos,
                                              homed=set(homed) == set('xyz'))
        except StartRefused as error:
            self.denied += 1
            self.last_error = str(error)
            logging.error('kctrl_purge_guard: refused %s -> %s: %s',
                          move.start_pos, move.end_pos, error)
            # No position mutation, no homing, no M112, no automatic escape.
            try:
                self.printer.lookup_object('heaters').turn_off_all_heaters()
            except Exception:
                logging.exception('kctrl_purge_guard: heater stop failed')
            raise self.printer.command_error(
                'K1 Control: mouvement refuse pour proteger le bac (%s). '
                'Plateau >=30 mm et sortie vers Y<=280 avant remontee.' % error)
        self.envelope.commit(next_latch)

    def check_extrude(self, move):
        self.original_extrude_check(move)
        push = move.axes_d[3]
        heater = self.heater
        if push <= 0. or heater.can_extrude or heater.target_temp >= heater.min_extrude_temp:
            return
        temp = heater.smoothed_temp
        self.cold_refused += 1
        self.cold_last = 'poussee %.2f mm a %.0f C, cible %.0f C' % (push, temp, heater.target_temp)
        now = self.reactor.monotonic()
        if self.cold_logged is None or now - self.cold_logged >= COLD_LOG_SECONDS:
            # A retrying stock loop would otherwise write one line per attempt.
            self.cold_logged = now
            logging.error('kctrl_purge_guard: cold push refused (%d) %s -> %s: %s',
                          self.cold_refused, move.start_pos, move.end_pos, self.cold_last)
        # No heater change, no position mutation, no shutdown.
        raise self.printer.command_error(
            'K1 Control: poussee de filament refusee, buse froide (%.0f C, minimum %.0f C) '
            'sans chauffe demandee.' % (temp, heater.min_extrude_temp))

    def _cold_hooked(self):
        return (self.extruder is not None and self.toolhead.get_extruder() is self.extruder
                and self.extruder.check_move == self.check_extrude)

    def get_status(self, eventtime):
        return {'revision': 'retained-start-v1', 'installed': self.original_check is not None,
                'bin_latched': self.envelope.latched, 'minimum_z': self.envelope.minimum_z,
                'denied': self.denied, 'last_error': self.last_error,
                'cold_revision': COLD_REVISION, 'cold_installed': self._cold_hooked(),
                'cold_refused': self.cold_refused, 'cold_last': self.cold_last}


def load_config(config):
    return KctrlPurgeGuard(config)
