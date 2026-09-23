"""Candidate start coordinator. Disabled by default; not yet installed.

PLAN only records identity. REFERENCE_READY requires an observed successful
ACCURATE_G28 after that plan. MATERIAL then owns the one conditional step:
normal stock T for an empty/different filament, or a retained purge without T.
The installed end-of-job owner and the existing prime sequence are unchanged.
"""

import logging

from .kctrl_end import live_route
from .kctrl_start_context import file_identity, file_motion
from .kctrl_start_policy import SLOTS, StartRefused, current_is_ready, decide_start, finite


class KctrlStart:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object('gcode')
        self.enabled = config.getboolean('enabled', False)
        self.boxes = config.getint('boxes', 2, minval=1, maxval=4)
        self.timeout = config.getfloat('material_timeout', 240., minval=60., maxval=300.)
        self.originals = {}
        self.run = None
        self.attempt = None
        self.adopted = None
        self.reference = 0
        self.reference_valid = False
        self.reference_running = False
        self.phase = 'idle' if self.enabled else 'disabled'
        self.failure = ''
        self.command_error = ''
        for name, handler in (
                ('KCTRL_START_PLAN', self.plan),
                ('KCTRL_START_REFERENCE_READY', self.reference_ready),
                ('KCTRL_START_MATERIAL', self.material),
                ('KCTRL_RETAINED_ADOPT', self.adopt)):
            self.gcode.register_command(name, handler)
        self.printer.register_event_handler('klippy:ready', self._ready)
        self.printer.register_event_handler('stepper_enable:motor_off', self._lose_reference)
        self.printer.register_event_handler('klippy:shutdown', self._disconnect)
        self.printer.register_event_handler('klippy:disconnect', self._disconnect)
        self.printer.register_event_handler('gcode:cancel', self._cancel)

    def _status(self, name):
        value = self.printer.lookup_object(name).get_status(self.reactor.monotonic())
        if not isinstance(value, dict):
            raise StartRefused('status_unknown_' + name)
        return value

    def _ready(self):
        if not self.enabled or self.originals:
            return
        for name in ('toolhead', 'heaters', 'extruder', 'heater_bed', 'pause_resume',
                     'print_stats', 'configfile', 'tmc2209 extruder', 'kctrl_end',
                     'kctrl_tool_change', 'kctrl_slot_map', 'kctrl_purge_guard',
                     'kctrl_bin_motion', 'filament_switch_sensor filament_sensor',
                     'filament_switch_sensor filament_sensor_2'):
            self.printer.lookup_object(name)
        self.toolhead = self.printer.lookup_object('toolhead')
        self.action = self.printer.lookup_object('box').box_action
        self.change = self.printer.lookup_object('kctrl_tool_change')
        for name in ('communication_set_box_mode', 'communication_get_buffer_state',
                     'send_data', 'update_filament_pos'):
            if not callable(getattr(self.action, name, None)):
                raise self.printer.config_error('kctrl_start: missing ' + name)
        handlers = self.gcode.ready_gcode_handlers
        names = ('ACCURATE_G28', 'BOX_QUIT_MATERIAL', 'BOX_EXTRUDE_MATERIAL',
                 'BOX_CUT_MATERIAL', 'BOX_RETRUDE_MATERIAL')
        if not all(callable(handlers.get(name)) for name in names):
            raise self.printer.config_error('kctrl_start: stock handlers missing')
        originals = {name: handlers[name] for name in names}
        originals['run_stock'] = self.change.run_stock
        replaced = []
        try:
            for name in names:
                self.gcode.register_command(name, None)
                replaced.append(name)
                handler = self._reference if name == 'ACCURATE_G28' else self._manual_effect(name)
                self.gcode.register_command(name, handler)
            self.change.run_stock = self._stock
            self.originals = originals
            self.gcode.register_output_handler(self._output)
        except Exception:
            for name in replaced:
                self.gcode.register_command(name, None)
                self.gcode.register_command(name, originals[name])
            self.change.run_stock = originals['run_stock']
            self.originals = {}
            raise

    def _manual_effect(self, name):
        def call(gcmd):
            # A manual removal/insertion breaks the provenance of a failed
            # insertion even if it later leaves the same sensor levels.
            self.attempt = self.adopted = None
            return self.originals[name](gcmd)
        return call

    def _reference(self, gcmd):
        self.reference_valid = False
        if self.phase != 'planned':
            # A manual calibration outside this start keeps its own behavior.
            # It cannot satisfy a later start's required fresh reference.
            return self.originals['ACCURATE_G28'](gcmd)
        self.reference_running = True
        try:
            self.originals['ACCURATE_G28'](gcmd)
            self.toolhead.wait_moves()
            if self.command_error:
                raise StartRefused(self.command_error)
            self._xyz()
            self.reference += 1
            self.reference_valid = True
        finally:
            self.reference_running = False

    def _lose_reference(self, *args):
        self.reference_valid = False

    def _disconnect(self, *args):
        self._lose_reference()
        self.attempt = self.adopted = None
        if self.run:
            self.phase, self.failure = 'failed', 'printer_disconnected'

    def _cancel(self, *args):
        if self.phase in ('planned', 'referenced', 'material'):
            self.phase, self.failure = 'failed', 'start_cancelled'
            self._cool()

    def _output(self, text):
        if (self.phase == 'material' or self.reference_running) and any(
                line.lstrip().startswith('!!') for line in str(text).splitlines()):
            self.command_error = 'firmware_reported_error'

    def _cool(self):
        self.printer.lookup_object('heaters').turn_off_all_heaters()

    def _enabled(self):
        if not self.enabled or not self.originals:
            raise StartRefused('retained_start_disabled_or_not_ready')
        if (not self._status('kctrl_purge_guard').get('installed')
                or not self._status('kctrl_bin_motion').get('installed')):
            raise StartRefused('bin_guards_not_installed')

    def _xyz(self):
        if set(self._status('toolhead').get('homed_axes', '')) != set('xyz'):
            raise StartRefused('axes_not_referenced')

    def _sensors(self):
        values = tuple(self._status('filament_switch_sensor ' + name).get('filament_detected')
                       for name in ('filament_sensor_2', 'filament_sensor'))
        if not all(type(value) is bool for value in values):
            raise StartRefused('filament_sensor_unknown')
        return values

    def _route(self):
        return live_route(self._status('box'), self.boxes)

    def _current(self):
        settings = self._status('configfile')['settings']['tmc2209 extruder']
        expected = settings['run_current']
        # Creality records 2 A as the default hold request; its TMC driver
        # clamps that request to run_current. Never command more than run.
        hold = min(settings.get('hold_current', expected), expected)
        if not current_is_ready(expected, expected) or not current_is_ready(hold, hold):
            raise StartRefused('extruder_current_configuration_invalid')
        self.gcode.run_script_from_command('M400')
        actual = self._status('tmc2209 extruder')
        if not (current_is_ready(actual.get('run_current'), expected)
                and current_is_ready(actual.get('hold_current'), hold)):
            self.gcode.run_script_from_command(
                'SET_TMC_CURRENT STEPPER=extruder CURRENT=%.6f HOLDCURRENT=%.6f\nM400'
                % (expected, hold))
        actual = self._status('tmc2209 extruder')
        if not (current_is_ready(actual.get('run_current'), expected)
                and current_is_ready(actual.get('hold_current'), hold)):
            raise StartRefused('extruder_current_readback_failed')

    def _stock(self, name, plan, stock, gcmd):
        self.attempt = self.adopted = None
        head, upstream = self._sensors()
        self._current()
        try:
            return self.originals['run_stock'](name, plan, stock, gcmd)
        finally:
            # Only an insertion which began with an empty head can attribute
            # a newly occupied head to this slot after a failed stock command.
            now_head, now_upstream = self._sensors()
            if (not head and now_head and now_upstream
                    and getattr(self.action, 'extrude_tnn', None) == plan['physical']):
                self.attempt = {'slot': plan['physical'], 'has_head': True}

    def adopt(self, gcmd):
        """Explicit operator attribution only; never commits a CFS cache."""
        self._enabled()
        slot = gcmd.get('SLOT', '').upper()
        if slot not in SLOTS or self._sensors() != (True, True):
            raise gcmd.error('K1 Control: attribution impossible, filament continu requis')
        if (self._status('print_stats').get('state') not in ('standby', 'error', 'cancelled', 'complete')
                or self._status('kctrl_end').get('pending') is not False
                or self.phase in ('planned', 'referenced', 'material')):
            raise gcmd.error('K1 Control: attribution refusee pendant une operation')
        if self._route() not in (None, slot):
            raise gcmd.error('K1 Control: une autre route est engagee')
        unit = self._status('box').get('T' + slot[1], {})
        if unit.get('state') != 'connect':
            raise gcmd.error('K1 Control: unite deconnectee')
        self.adopted = slot
        gcmd.respond_info('K1 Control: %s attribue par operateur, purge encore requise' % slot)

    def plan(self, gcmd):
        try:
            self._enabled()
            epoch = self._status('kctrl_end').get('job_epoch')
            if type(epoch) is not int or epoch <= 0:
                raise StartRefused('job_epoch_missing')
            if (self.phase in ('planned', 'referenced', 'material') and self.run
                    and self.run['epoch'] == epoch):
                raise StartRefused('start_already_active')
            self.run = None
            self.failure = self.command_error = ''
            slot = gcmd.get('SLOT', '').upper()
            index = gcmd.get_int('INDEX', minval=0, maxval=15)
            temp = gcmd.get_float('TEMP', minval=150., maxval=300.)
            if slot not in SLOTS:
                raise StartRefused('requested_route_invalid')
            if self._status('kctrl_end').get('pending') is not False:
                raise StartRefused('end_still_active')
            job = self._status('print_stats')
            if job.get('state') != 'printing' or not job.get('filename'):
                raise StartRefused('new_print_not_active')
            head, upstream = self._sensors()
            route = self._route()
            attempt = self.attempt or {}
            attributable = (self.adopted == slot or
                            (attempt.get('slot') == slot and attempt.get('has_head') is True
                             and getattr(self.action, 'extrude_tnn', None) == slot))
            # Identity only. Do not invent XYZ or call the movement policy
            # with pretend homing. The actual decision is made after probing.
            if head and (not upstream or (route is None and not attributable)):
                raise StartRefused('retained_identity_or_continuity_unproven')
            if not head and route:
                raise StartRefused('partial_filament_requires_recovery')
            path = self.printer.lookup_object('kctrl_slot_map').printing_file()
            if not path:
                raise StartRefused('job_file_missing')
            motion = file_motion(path, index)
            self.run = {'slot': slot, 'index': index, 'temp': temp, 'head': head,
                        'upstream': upstream, 'route': route, 'attributable': attributable,
                        'reference_before': self.reference, 'path': path, 'motion': motion,
                        'filename': job['filename'], 'epoch': epoch}
            self.phase = 'planned'
        except Exception as error:
            self.phase, self.failure = 'failed', str(error)
            raise gcmd.error('K1 Control: preparation refusee (%s)' % error)

    def _check(self, run, phases, geometry=True):
        self._enabled()
        if run is None or run is not self.run or self.phase not in phases:
            raise StartRefused(self.failure or 'start_invalidated')
        if (self._status('print_stats').get('filename') != run['filename']
                or self.printer.lookup_object('kctrl_slot_map').printing_file() != run['path']
                or file_identity(run['path']) != run['motion']['identity']):
            raise StartRefused('job_changed')
        if self._status('kctrl_end').get('pending') is not False:
            raise StartRefused('end_still_active')
        if self._status('kctrl_end').get('job_epoch') != run['epoch']:
            raise StartRefused('job_epoch_changed')
        if self._status('pause_resume').get('is_paused') is not False:
            raise StartRefused('start_paused')
        if self._status('print_stats').get('state') != 'printing':
            raise StartRefused('print_no_longer_active')
        if self.command_error:
            raise StartRefused(self.command_error)
        if 'deadline' in run and self.reactor.monotonic() >= run['deadline']:
            raise StartRefused('material_timeout')
        if geometry:
            self._xyz()
            if not self.reference_valid or self.reference <= run['reference_before']:
                raise StartRefused('fresh_reference_missing')

    def reference_ready(self, gcmd):
        try:
            run = self.run
            self._check(run, ('planned',))
            if self._sensors() != (run['head'], run['upstream']) or self._route() != run['route']:
                raise StartRefused('filament_changed_during_reference')
            nozzle = self._status('extruder')
            if (not finite(nozzle.get('temperature')) or nozzle['temperature'] > 103.
                    or not finite(nozzle.get('target')) or nozzle['target'] > 100.):
                raise StartRefused('contact_temperature_not_confirmed')
            run['branch'] = decide_start(
                run['head'], run['upstream'], run['slot'], run['route'], run['slot'],
                self._status('toolhead')['homed_axes'], run['attributable'], run['attributable'])
            self.phase = 'referenced'
        except Exception as error:
            self._fail(error)
            raise gcmd.error('K1 Control: reference de depart refusee (%s)' % error)

    def _fail(self, error):
        self.phase, self.failure = 'failed', str(error)
        self._cool()

    def _watchdog(self, eventtime):
        if self.phase == 'material':
            self._fail('material_timeout')
        return self.reactor.NEVER

    def _script(self, run, command):
        self._check(run, ('material',))
        self.gcode.run_script_from_command(command)
        self._check(run, ('material',))

    def material(self, gcmd):
        watchdog = None
        try:
            run = self.run
            self._check(run, ('referenced',))
            if self._sensors() != (run['head'], run['upstream']) or self._route() != run['route']:
                raise StartRefused('filament_changed_before_material')
            self.phase = 'material'
            run['deadline'] = self.reactor.monotonic() + self.timeout
            watchdog = self.reactor.register_timer(self._watchdog, run['deadline'])
            self._current()
            self._check(run, ('material',))
            self._motion(run)
            if run['branch'] in ('keep', 'recover'):
                self._purge(run)
            else:
                self._script(run, 'T%d\nM400' % run['index'])
            self._check(run, ('material',))
            if self._sensors()[0] is not True:
                raise StartRefused('stock_load_left_head_empty')
            self.phase = 'complete'
            gcmd.respond_info('K1 Control: filament %s pret (%s)' % (run['slot'], run['branch']))
        except Exception as error:
            self._fail(error)
            raise gcmd.error('K1 Control: depart interrompu (%s)' % error)
        finally:
            if watchdog is not None:
                self.reactor.unregister_timer(watchdog)

    def _temperature(self, run):
        self._check(run, ('material',))
        nozzle = self._status('extruder')
        target = max(200., run['temp'])
        if (nozzle.get('can_extrude') is not True or nozzle.get('target') != target
                or not finite(nozzle.get('temperature'))
                or abs(nozzle['temperature'] - target) > 5.):
            raise StartRefused('purge_temperature_changed')
        if self._sensors() != (True, True) or self._route() != run['route']:
            raise StartRefused('retained_filament_changed')

    def _thermal(self, run):
        self._temperature(run)
        if str(self._status('box')['T' + run['slot'][1]].get('mode')) != '2':
            raise StartRefused('cfs_print_mode_lost')
        if not current_is_ready(self._status('tmc2209 extruder').get('run_current'),
                                self._status('configfile')['settings']['tmc2209 extruder']['run_current']):
            raise StartRefused('extruder_current_changed')

    def _motion(self, run):
        cfg = self._status('configfile')['settings']['printer']
        accel = min(float(cfg['max_accel']), run['motion']['travel_acceleration'])
        decel = min(accel, float(cfg['max_accel_to_decel']))
        velocity = float(cfg['max_velocity'])
        if not all(finite(v) and v > 0 for v in (accel, decel, velocity)):
            raise StartRefused('motion_configuration_invalid')
        self._script(run, 'SET_VELOCITY_LIMIT VELOCITY=%.3f ACCEL=%.3f ACCEL_TO_DECEL=%.3f'
                     % (velocity, accel, decel))

    def _purge(self, run):
        self._script(run, 'SAVE_GCODE_STATE NAME=KCTRL_RETAINED_START')
        try:
            self._script(run, 'M220 S100\nM221 S100\nG90')
            z = self.toolhead.get_position()[2]
            if not finite(z):
                raise StartRefused('position_unknown')
            if z < 35.:
                self._script(run, 'G91\nG1 Z%.5f F1200\nG90\nM400' % (35.1 - z))
            if self.toolhead.get_position()[2] < 35.:
                raise StartRefused('purge_margin_missing')
            self._script(run, 'G1 Y273 F24000\nG1 X185.5 F24000\n'
                         'G1 Y305 F6000\nM400')
            self._script(run, 'M109 S%.3f' % max(200., run['temp']))
            self._temperature(run)
            # Clear old failure flags for this new, attributed retained start.
            # This is not a new feed request and never performs a retry.
            self._script(run, 'BOX_ERROR_CLEAR')
            addr, slot = int(run['slot'][1]), run['slot'][2]
            self._check(run, ('material',))
            result = self.action.communication_set_box_mode(addr, 'PRINT', slot)
            self._check(run, ('material',))
            if result is not True:
                raise StartRefused('cfs_print_ack_missing')
            # Exact isolated binary trace: GET_BOX_STATE sends [addr], [0x0a]
            # with a 3600-second timeout. Keep its read-only frame but bound
            # the wait to 2 seconds, like GET_BUFFER_STATE, with no retry.
            result = self.action.send_data(bytes([addr]), bytes([0x0a]), 2)
            self._check(run, ('material',))
            if result is not True:
                raise StartRefused('cfs_state_ack_missing')
            self._thermal(run)
            self._script(run, 'M83')
            consumed = False
            for _ in range(7):
                self._thermal(run)
                self._script(run, 'G1 E20 F%.5f\nM400' % (60. * run['motion']['feed']))
                if self.action.communication_get_buffer_state(addr) is not True:
                    raise StartRefused('buffer_ack_missing')
                self._thermal(run)
                buffer = self.action.box_state.get_Tn_inner_data(addr, None, uppart='buffer')
                if type(buffer) is not int or buffer not in (0, 1):
                    raise StartRefused('buffer_empty_or_unknown')
                consumed = consumed or buffer == 0
            if not consumed:
                raise StartRefused('buffer_consumption_unconfirmed')
            for _ in range(3):
                self._script(run, 'G1 Y291.5 F15000\nG1 Y305 F6000\nM400')
            self._script(run, 'G1 Y273 F15000\nM400')
            if self._status('kctrl_purge_guard').get('bin_latched') is not False:
                raise StartRefused('bin_exit_not_confirmed')
            self._thermal(run)
            # Same cache update as stock success, only after acknowledged
            # PRINT mode, consumed buffer and completed exit. No serial effect.
            self.action.update_filament_pos(run['slot'], run['slot'])
            self.action.box_save.last_cmd = run['slot']
            if self._route() != run['slot']:
                raise StartRefused('retained_bookkeeping_not_confirmed')
            self.change.last = {'tool': 'T%d' % run['index'], 'outcome': 'start',
                                'slot': run['slot'], 'temp': run['temp']}
            self.attempt = self.adopted = None
            logging.info('kctrl_start: retained purge complete slot=%s feed=%s',
                         run['slot'], run['motion']['feed'])
        finally:
            self.gcode.run_script_from_command('RESTORE_GCODE_STATE NAME=KCTRL_RETAINED_START MOVE=0')

    def get_status(self, eventtime=None):
        return {'enabled': self.enabled, 'installed': bool(self.originals),
                'phase': self.phase, 'failure': self.failure,
                'reference': self.reference, 'reference_valid': self.reference_valid,
                'branch': self.run.get('branch') if self.run else None,
                'slot': self.run.get('slot') if self.run else None,
                'revision': 'retained-start-v1', 'physical_validation': False}


def load_config(config):
    return KctrlStart(config)
