"""ADR-070 overlap correction: defer the end, resolve the live slot, prove the cut.

Disabled by default; no handler is replaced and no output hook is installed
until enabled at klippy:ready. See README.md for installation and physical qualification status.
Only the end of a job begun through START_PRINT is owned. No firmware resume
flag is written, no tool is selected, and there is no retry of a filament effect.
"""

import logging
import math
import re

SLOTS = tuple('T%d%s' % (box, slot) for box in range(1, 5) for slot in 'ABCD')
ACTIVE = ('waiting', 'heating', 'cutting', 'rewinding', 'finalizing')


class EndRefused(Exception):
    pass


def live_route(box, boxes=2):
    """A single engaged route, or None. Declared spool material is not a route."""
    if box.get('enable') != 1 or box.get('state') != 'connect':
        raise EndRefused('cfs_not_ready')
    routes = []
    for number in range(1, 5):
        unit = box.get('T%d' % number)
        if number <= boxes:
            if not isinstance(unit, dict) or unit.get('state') != 'connect':
                raise EndRefused('cfs_unit_missing')
        elif not unit or unit.get('state') in (None, 'None', 'disconnect'):
            continue
        else:
            raise EndRefused('unexpected_cfs_unit')
        slot = unit.get('filament', '__missing__')
        if slot == 'None':
            continue
        if slot not in ('A', 'B', 'C', 'D'):
            raise EndRefused('cfs_route_unknown')
        routes.append('T%d%s' % (number, slot))
    if len(routes) > 1:
        raise EndRefused('cfs_routes_ambiguous')
    return routes[0] if routes else None


class CutProof:
    """Console events scoped to one owned cut; box.cut_pos is never read.

    ADR-041/044 identify these events; the 2026-09-21 recovery trace proves
    release may arrive only after rewind. Confirm cut before rewind, and
    release before finalization (document 85). Deferred live end is untested.
    An old event or a successful command return alone is deliberately useless.
    """
    def __init__(self):
        self.contact = False
        self.returned = False
        self.triggered = False
        self.released = False
        self.failed = False

    def feed(self, text):
        for line in str(text).splitlines():
            line = line.strip()
            if line.startswith('// '):
                line = line[3:]
            if line.startswith('!!') or 'can not cut material' in line or 'failed' in line.lower():
                self.failed = True
            if line == '[box] cut sensor state:1':
                if self.released:
                    self.failed = True
                self.contact = True
            elif line == '[box] cut to return OK' and self.contact:
                self.returned = True
            elif line == 'Cut sensor triggered.' and self.contact:
                self.triggered = True
            elif line == '[box] cut sensor state:0' and self.returned and self.triggered:
                self.released = True

    @property
    def cut_confirmed(self):
        return self.contact and self.returned and self.triggered and not self.failed

    @property
    def complete(self):
        return self.cut_confirmed and self.released


class KctrlEnd:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object('gcode')
        self.enabled = config.getboolean('enabled', False)
        self.timeout = config.getfloat('timeout', 180., minval=10., maxval=300.)
        self.cut_timeout = config.getfloat('cut_proof_timeout', 5., minval=0.1, maxval=15.)
        self.settle_timeout = config.getfloat('rewind_settle_timeout', 20., minval=1., maxval=30.)
        self.boxes = config.getint('boxes', 2, minval=1, maxval=4)
        self.epoch = 0
        self.job = None
        self.run = None
        self.inflight = False
        self.phase = 'disabled' if not self.enabled else 'idle'
        self.reason = ''
        self.failure = ''
        self.thermal_failure = ''
        self.proof = None
        self.command_error = ''
        self.originals = {}
        self.printer.register_event_handler('klippy:ready', self._ready)
        self.printer.register_event_handler('klippy:shutdown', self._shutdown)
        self.printer.register_event_handler('klippy:disconnect', self._shutdown)
        self.printer.register_event_handler('gcode:cancel', self._cancel_event)

    def _ready(self):
        if not self.enabled or self.originals:
            return
        # Atomically restore all originals if any dependency or registration
        # fails. No partially wrapped START/END/CANCEL set is retained.
        for name in ('heaters', 'extruder', 'heater_bed', 'virtual_sdcard',
                     'pause_resume', 'box', 'toolhead', 'filament_switch_sensor filament_sensor_2'):
            if self.printer.lookup_object(name, None) is None:
                raise self.printer.config_error('kctrl_end: missing ' + name)
        required = ('BOX_CUT_MATERIAL', 'BOX_SET_BOX_MODE',
                    'BOX_CTRL_CONNECTION_MOTOR_ACTION', 'BOX_RETRUDE_PROCESS')
        handlers = self.gcode.ready_gcode_handlers
        for name in required:
            if not callable(handlers.get(name)):
                raise self.printer.config_error('kctrl_end: missing primitive ' + name)
        action = self.printer.lookup_object('box').box_action
        for name in ('communication_set_box_mode',
                     'communication_ctrl_connection_motor_action',
                     'communication_retrude_process'):
            if not callable(getattr(action, name, None)):
                raise self.printer.config_error('kctrl_end: missing primitive ' + name)
        replacements = {'START_PRINT': self.start, 'END_PRINT': self.end,
                        'CANCEL_PRINT': self.cancel}
        installed = []
        try:
            for name in replacements:
                original = self.gcode.register_command(name, None)
                if original is None:
                    raise self.printer.config_error('kctrl_end: missing ' + name)
                self.originals[name] = original
            for name, handler in replacements.items():
                self.gcode.register_command(name, handler)
                installed.append(name)
            self.gcode.register_output_handler(self._output)
        except Exception:
            for name in installed:
                self.gcode.register_command(name, None)
            for name, original in self.originals.items():
                self.gcode.register_command(name, original)
            self.originals.clear()
            raise

    def _status(self, name):
        obj = self.printer.lookup_object(name, None)
        if obj is None:
            raise EndRefused('missing_' + name)
        value = obj.get_status(self.reactor.monotonic())
        if not isinstance(value, dict):
            raise EndRefused('invalid_' + name)
        return value

    def _head(self):
        value = self._status('filament_switch_sensor filament_sensor_2').get('filament_detected')
        if type(value) is not bool:
            raise EndRefused('head_sensor_unknown')
        return value

    def _route(self):
        return live_route(self._status('box'), self.boxes)

    def start(self, gcmd):
        if not self.enabled:
            raise gcmd.error('K1 Control: candidat de fin desactive')
        if self.inflight:
            raise gcmd.error('K1 Control: finalisation encore en cours')
        self.epoch += 1
        self.job = (self.epoch, self._status('print_stats').get('filename'))
        self.run = None
        self.phase, self.failure, self.thermal_failure = 'idle', '', ''
        # The cache belongs to the new job only. It is still not route proof.
        change = self.printer.lookup_object('kctrl_tool_change', None)
        if change is not None:
            change.last = {}
        try:
            self.originals['START_PRINT'](gcmd)
        except Exception:
            self.job = None
            self._thermal_stop()
            raise

    def end(self, gcmd):
        self._request(gcmd, 'fin')

    def cancel(self, gcmd):
        if not self.enabled:
            raise gcmd.error('K1 Control: candidat de fin desactive')
        # Abort an already-owned finalization immediately, never start another
        # cut/rewind behind it. Cancellation of the SD job remains available.
        pending = self.phase in ACTIVE
        if pending:
            self._fail('cancelled_during_end')
        try:
            self.gcode.run_script_from_command('CANCEL_PRINT_BASE')
        except Exception:
            self._fail('cancel_base_failed')
            raise
        if not pending:
            self._request(gcmd, 'annulation')

    def _request(self, gcmd, reason):
        if not self.enabled:
            raise gcmd.error('K1 Control: candidat de fin desactive')
        if self.run is not None:
            gcmd.respond_info('K1 Control: fin deja demandee (%s)' % self.phase)
            return
        try:
            if not self.job or not self.job[1]:
                raise EndRefused('job_identity_missing')
            if self._status('print_stats').get('filename') != self.job[1]:
                raise EndRefused('job_changed')
            self.reason = reason
            self.command_error = ''
            target = self._status('extruder').get('target')
            self.run = {'job': self.job, 'deadline': self.reactor.monotonic() + self.timeout,
                        'route': None, 'target': target, 'watchdog': None}
            run = self.run
            self.phase = 'waiting'
            self.inflight = True
            run['watchdog'] = self.reactor.register_timer(self._watchdog, run['deadline'])
            # Request returns to the SD worker. It must be allowed to leave its
            # resume context; waiting inside END_PRINT would deadlock that exit.
            self.reactor.register_callback(lambda eventtime: self._finish(run))
            gcmd.respond_info('K1 Control: fin en cours de verification, retrait non termine')
        except Exception as error:
            self._fail(str(error))
            self.inflight = False
            if self.run and self.run['watchdog'] is not None:
                self.reactor.unregister_timer(self.run['watchdog'])
            gcmd.respond_info('K1 Control: fin incomplete (%s)' % self.failure)

    def _output(self, text):
        if self.phase not in ACTIVE:
            return
        if any(line.lstrip().startswith('!!') for line in str(text).splitlines()):
            self.command_error = 'firmware_reported_error'
        if self.proof is not None:
            self.proof.feed(text)

    def _check(self, run):
        if run is not self.run or run['job'] != self.job or self.phase not in ACTIVE:
            raise EndRefused('end_invalidated')
        if self.reactor.monotonic() >= run['deadline']:
            raise EndRefused('end_timeout')
        if self._status('print_stats').get('filename') != self.job[1]:
            raise EndRefused('job_changed')
        if self.command_error:
            raise EndRefused(self.command_error)

    def _busy(self):
        sd = self.printer.lookup_object('virtual_sdcard')
        # An absent resume flag is unknown, never silently treated as clear.
        resume = getattr(sd, 'do_resume_status', None)
        if type(resume) is not bool:
            raise EndRefused('resume_state_unknown')
        return sd.is_active() or resume

    def _unchanged_route(self, run):
        self._check(run)
        if self._busy() or self._status('pause_resume').get('is_paused') is not False:
            raise EndRefused('resume_or_pause_active')
        if self._route() != run['route']:
            raise EndRefused('route_changed')

    def _resolve(self):
        route = self._route()
        if route is None:
            raise EndRefused('head_loaded_without_route')
        change = self.printer.lookup_object('kctrl_tool_change', None)
        last = dict(change.last) if change is not None else {}
        # A failed attempt can target another slot without reaching it. Do not
        # use its logical destination either. Live physical route stays primary.
        logical = None
        if last.get('outcome') == 'done':
            match = re.fullmatch(r'T([0-9]|1[0-5])', str(last.get('tool', '')))
            if match:
                logical = SLOTS[int(match.group(1))]
        mapping = self.printer.lookup_object('kctrl_slot_map', None)
        if mapping is not None:
            mapping.refresh()
            if logical and logical in mapping.map:
                if mapping.map[logical] != route:
                    raise EndRefused('mapping_route_conflict')
        return route

    def _script(self, run, text):
        self._check(run)
        self.gcode.run_script_from_command(text)
        self._check(run)

    def _wait_cut_proof(self, run, release=False):
        deadline = min(self.reactor.monotonic() + self.cut_timeout, run['deadline'])
        while not (self.proof.complete if release else self.proof.cut_confirmed):
            self._check(run)
            if self.proof.failed or self.reactor.monotonic() >= deadline:
                raise EndRefused('cutter_release_not_confirmed' if release else 'cut_not_confirmed')
            self.reactor.pause(min(self.reactor.monotonic() + .05, deadline))

    def _release_cutter(self, run):
        # Physical coordinates: no G-code offset, no X/Z/E movement. The
        # qualified safe Y withdraws the lever without a trip to the bin.
        toolhead = self.printer.lookup_object('toolhead')
        position = self._status('toolhead').get('position')
        if (not isinstance(position, (list, tuple)) or len(position) < 3
                or any(type(v) not in (int, float) or not math.isfinite(v)
                       for v in position[:3])
                or abs(position[0] - 38.) > .25
                or not 303. <= position[1] <= 306.):
            raise EndRefused('cutter_position_not_confirmed')
        self._unchanged_route(run)
        toolhead.manual_move([None, 291.5, None, None], 30.)
        toolhead.wait_moves()
        self._check(run)
        self._wait_cut_proof(run, release=True)
        after = self._status('toolhead').get('position')
        if (not isinstance(after, (list, tuple)) or len(after) < 3
                or any(type(v) not in (int, float) or not math.isfinite(v)
                       for v in after[:3])
                or abs(after[0] - position[0]) > .01
                or abs(after[1] - 291.5) > .01
                or abs(after[2] - position[2]) > .01):
            raise EndRefused('cutter_release_position_changed')

    def _separated_rewind(self, run):
        self._release_cutter(run)
        self._unchanged_route(run)
        self.phase = 'rewinding'
        # Stock Tn_Extrude drains the fast -20 mm move. The following slow
        # -15 mm move MUST remain queued while the CFS withdrawal starts.
        # A barrier there removed overlap in the physical key849 trial.
        # Exact installed stock distances/speeds, but no stock temperature
        # floor, no hidden XYZ and no combined BOX_RETRUDE_MATERIAL call.
        self._script(run, 'SAVE_GCODE_STATE NAME=kctrl_end_withdraw')
        try:
            for command in ('M83', 'M221 S100', 'G1 E-20 F5000', 'M400', 'G1 E-15 F120'):
                self._unchanged_route(run)
                extruder = self._status('extruder')
                actual = extruder.get('temperature')
                if (extruder.get('target') != run['target']
                        or extruder.get('can_extrude') is not True
                        or type(actual) not in (int, float) or not math.isfinite(actual)
                        or abs(actual - run['target']) > 5.):
                    raise EndRefused('temperature_changed_during_withdraw')
                self._script(run, command)
        finally:
            # Restore parser state only; MOVE=0 can never raise the bed.
            self.gcode.run_script_from_command(
                'RESTORE_GCODE_STATE NAME=kctrl_end_withdraw MOVE=0')
        self._unchanged_route(run)
        addr, slot = int(run['route'][1]), run['route'][2]
        action = self.printer.lookup_object('box').box_action
        # G-code wrappers discard the boolean transport result. Call these
        # same elementary methods directly and require an explicit True ACK.
        for name, args in (
                ('communication_set_box_mode', (addr, 'IDLE')),
                ('communication_ctrl_connection_motor_action', (addr, 'STOP')),
                ('communication_retrude_process', (addr, slot, 'MATERIAL'))):
            self._unchanged_route(run)
            result = getattr(action, name)(*args)
            self._check(run)
            if result is not True:
                raise EndRefused('cfs_ack_not_confirmed_' + name)
        # Drain the slow extruder move only AFTER the CFS acknowledgement;
        # an early ACK must not permit parking while extrusion still runs.
        self._script(run, 'M400')
        # The CFS reports completion before its next periodic state refresh.
        # Allow the SAME old route to settle; a different/unknown route fails.
        # There is one withdrawal attempt only, never a timeout-driven retry.
        deadline = min(self.reactor.monotonic() + self.settle_timeout, run['deadline'])
        clear_since = None
        while True:
            self._check(run)
            if self._busy() or self._status('pause_resume').get('is_paused') is not False:
                raise EndRefused('resume_or_pause_active')
            route = self._route()
            if route not in (None, run['route']):
                raise EndRefused('route_changed_during_rewind')
            if self.proof.failed or not self.proof.complete:
                raise EndRefused('cutter_release_lost')
            clear = not self._head() and route is None
            now = self.reactor.monotonic()
            if clear:
                if clear_since is None:
                    clear_since = now
                if now - clear_since >= .5:
                    return
            else:
                clear_since = None
            if now >= deadline:
                raise EndRefused('rewind_not_confirmed')
            self.reactor.pause(min(now + .1, deadline))

    def _finish(self, run):
        try:
            while self._busy():
                self._check(run)
                self.reactor.pause(min(self.reactor.monotonic() + .1, run['deadline']))
            # Serialize every physical action against manual commands and new
            # starts. The independent heater watchdog does not take this mutex.
            with self.gcode.get_mutex():
                self._check(run)
                if self._busy() or self._status('pause_resume').get('is_paused') is not False:
                    raise EndRefused('resume_or_pause_active')
                head = self._head()
                if not head:
                    if self._route() is not None:
                        raise EndRefused('head_empty_but_route_engaged')
                else:
                    run['route'] = self._resolve()
                    if self._status('toolhead').get('homed_axes') != 'xyz':
                        raise EndRefused('axes_not_referenced')
                    temp = self._status('extruder').get('target')
                    if isinstance(temp, bool) or not isinstance(temp, (float, int)) or not math.isfinite(temp) or not 150 <= temp <= 320:
                        raise EndRefused('approved_temperature_missing')
                    if temp != run['target']:
                        raise EndRefused('temperature_target_changed')
                    self._script(run, 'SET_FILAMENT_SENSOR SENSOR=filament_sensor_2 ENABLE=0')
                    self.phase = 'heating'
                    # Keep the already-approved print target; do not invent a
                    # 200 C floor or reheat a cancelled, already-cold nozzle.
                    while True:
                        self._unchanged_route(run)
                        extruder = self._status('extruder')
                        if extruder.get('target') != run['target']:
                            raise EndRefused('temperature_target_changed')
                        actual = extruder.get('temperature')
                        if type(actual) not in (int, float) or not math.isfinite(actual):
                            raise EndRefused('temperature_invalid')
                        if extruder.get('can_extrude') is True and abs(actual - temp) <= 5.:
                            break
                        self.reactor.pause(min(self.reactor.monotonic() + .1, run['deadline']))
                    self._unchanged_route(run)
                    self.phase = 'cutting'
                    self.proof = CutProof()
                    self._script(run, 'BOX_CUT_MATERIAL')
                    # A successful cut can keep its sensor engaged until the
                    # rewind finishes. Waiting for release here deadlocks the
                    # valid stock sequence observed on 2026-09-21.
                    self._wait_cut_proof(run)
                    self._unchanged_route(run)
                    extruder = self._status('extruder')
                    actual = extruder.get('temperature')
                    if (extruder.get('target') != run['target']
                            or extruder.get('can_extrude') is not True
                            or type(actual) not in (int, float)
                            or not math.isfinite(actual)
                            or abs(actual - run['target']) > 5.):
                        raise EndRefused('temperature_changed_after_cut')
                    self._separated_rewind(run)
                    self.proof = None
                self.phase = 'finalizing'
                # BOX_END is inside this macro. It is permitted only after two
                # fresh observations prove no head filament AND no CFS route.
                self._check(run)
                if self._head() or self._route() is not None:
                    raise EndRefused('final_state_changed')
                self._script(run, 'END_PRINT_NO_M84')
                self._script(run, 'M84')
                if not self._thermal_stop():
                    raise EndRefused('heaters_not_off')
                self.phase = 'complete'
        except Exception as error:
            if self.phase not in ('failed', 'shutdown'):
                self._fail(str(error))
        finally:
            self.proof = None
            if self.phase != 'complete':
                self._thermal_stop()
            if run['watchdog'] is not None:
                self.reactor.unregister_timer(run['watchdog'])
            self.inflight = False
            logging.info('kctrl_end: phase=%s route=%s failure=%s thermal=%s',
                         self.phase, run['route'], self.failure, self.thermal_failure)
            self.gcode.respond_info('K1 Control: fin %s%s' % (
                'terminee, tete vide et chauffes coupees' if self.phase == 'complete' else 'incomplete',
                (' (' + self.failure + ')') if self.failure else ''))

    def _thermal_stop(self):
        try:
            self.printer.lookup_object('heaters').turn_off_all_heaters()
            if any(self._status(name).get('target') != 0 for name in ('extruder', 'heater_bed')):
                raise EndRefused('targets_not_zero')
            return True
        except Exception as error:
            self.thermal_failure = str(error)
            self.printer.invoke_shutdown('K1 Control: arret thermique de fin non confirme')
            return False

    def _fail(self, reason):
        self.phase, self.failure = 'failed', reason
        self._thermal_stop()

    def _watchdog(self, eventtime):
        if self.phase in ACTIVE:
            self._fail('end_timeout')
        return self.reactor.NEVER

    def _cancel_event(self, *args):
        # Creality GCodeDispatch.invoke_cancel emits this BEFORE waiting for
        # the G-code mutex. Stop heaters even when a stock action holds it.
        if self.enabled and self.inflight:
            self._fail('cancelled_during_end')

    def _shutdown(self, *args):
        if self.phase in ACTIVE:
            self.phase, self.failure = 'shutdown', 'printer_shutdown_or_disconnect'
        self.job = None

    def get_status(self, eventtime=None):
        return {'enabled': self.enabled, 'phase': self.phase, 'reason': self.reason,
                'failure': self.failure, 'thermal_failure': self.thermal_failure,
                'job_epoch': self.epoch, 'pending': self.inflight,
                'slot': self.run['route'] if self.run else None,
                'physical_validation': False, 'revision': 'end-overlap-v2',
                'wrapped': sorted(self.originals)}


def load_config(config):
    return KctrlEnd(config)
