"""Mechanical bin clearance at the kinematic check, below all G-code owners.

Checks real transformed XYZ, including stock direct toolhead calls. Never
generates a compensating move. A refusal cuts heat and raises a command error,
not an emergency stop. This protects the machine independently of START_PRINT.
"""

import logging

from .kctrl_start_policy import PurgeEnvelope, StartRefused


class KctrlPurgeGuard:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.envelope = PurgeEnvelope()
        self.toolhead = None
        self.original_check = None
        self.denied = 0
        self.last_error = ''
        self.printer.register_event_handler('klippy:ready', self._ready)

    def _ready(self):
        if self.original_check is not None:
            return
        self.toolhead = self.printer.lookup_object('toolhead')
        kin = self.toolhead.get_kinematics()
        self.original_check = kin.check_move
        kin.check_move = self.check_move

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

    def get_status(self, eventtime):
        return {'revision': 'retained-start-v1', 'installed': self.original_check is not None,
                'bin_latched': self.envelope.latched, 'minimum_z': self.envelope.minimum_z,
                'denied': self.denied, 'last_error': self.last_error}


def load_config(config):
    return KctrlPurgeGuard(config)
