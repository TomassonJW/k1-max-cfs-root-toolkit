"""Candidate stock choreography adapter; installed only with the global guard.

Keep the manufacturer's own Z displacement accounting. Change only the
absolute clearance it requests on entry, and exit forward before its restore.
Never repair a rejected move or synthesize a homed position.
"""

import math


class KctrlBinMotion:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object('gcode')
        self.entering = False
        self.originals = {}
        self.printer.register_event_handler('klippy:ready', self._ready)

    def _ready(self):
        if self.originals:
            return
        self.toolhead = self.printer.lookup_object('toolhead')
        self.guard = self.printer.lookup_object('kctrl_purge_guard')
        action = self.printer.lookup_object('box').box_action
        names = ('go_to_extrude_pos', 'z_down', 'z_restore')
        originals = {name: getattr(action, name, None) for name in names}
        if not all(callable(value) for value in originals.values()):
            raise self.printer.config_error('kctrl_bin_motion: stock interface missing')
        self.originals = originals
        try:
            action.go_to_extrude_pos = self.enter
            action.z_down = self.z_down
            action.z_restore = self.restore
        except Exception:
            for name, method in originals.items():
                setattr(action, name, method)
            self.originals = {}
            raise

    def _referenced(self):
        status = self.toolhead.get_status(self.reactor.monotonic())
        if set(status.get('homed_axes', '')) != set('xyz'):
            raise self.printer.command_error('K1 Control: references XYZ requises avant le bac')
        return list(self.toolhead.get_position())

    def enter(self, *args, **kwargs):
        self._referenced()
        if self.entering:
            raise self.printer.command_error('K1 Control: entree de bac deja active')
        self.entering = True
        try:
            return self.originals['go_to_extrude_pos'](*args, **kwargs)
        finally:
            self.entering = False

    def z_down(self, *args, **kwargs):
        if self.entering:
            # Exact binary trace: z_down(distance=25, absolute=True, wait=True).
            # Let stock calculate and retain move_z itself, including when the
            # bed is already lower. Pre-moving it would lose the return height.
            self._referenced()
            if args or kwargs.get('absolute') is not True:
                raise self.printer.command_error('K1 Control: entree de bac stock non reconnue')
            kwargs = dict(kwargs)
            distance = kwargs.get('distance')
            if (type(distance) not in (int, float) or not math.isfinite(distance)
                    or distance <= 0.):
                raise self.printer.command_error('K1 Control: distance de bac invalide')
            kwargs['distance'] = max(35., distance)
        return self.originals['z_down'](*args, **kwargs)

    def restore(self, *args, **kwargs):
        if self.guard.envelope.latched:
            position = self._referenced()
            if position[2] < 30.:
                raise self.printer.command_error('K1 Control: degagement du bac non confirme')
            # This is the normal pre-restore choreography, not an emergency
            # escape after rejection. No Z or E is commanded here.
            self.gcode.run_script_from_command(
                'SAVE_GCODE_STATE NAME=KCTRL_BIN_EXIT\nG90\n'
                'G1 Y273 F24000\nM400\n'
                'RESTORE_GCODE_STATE NAME=KCTRL_BIN_EXIT MOVE=0')
            if self.guard.envelope.latched:
                raise self.printer.command_error('K1 Control: sortie du bac non confirmee')
        return self.originals['z_restore'](*args, **kwargs)

    def get_status(self, eventtime=None):
        return {'installed': bool(self.originals), 'entering': self.entering,
                'revision': 'retained-start-v1'}


def load_config(config):
    return KctrlBinMotion(config)
