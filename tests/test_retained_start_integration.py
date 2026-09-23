"""Complete candidate start with fake Klipper/CFS; no printer transport.

State changes, planned movements, cancellation, failed ACKs and the original
stock branch are exercised through the public commands, not by patching the
coordinator's checks out. This is software validation, not physical proof.
"""

import importlib
import ast
import math
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest
import jinja2

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'packages/k1-control-v1/retained-start-v1'
NAME = '_retained_integration'
package = ModuleType(NAME)
package.__path__ = [str(PACKAGE), str(ROOT / 'packages/k1-control-v1/end-rewind-confirm-v3')]
sys.modules[NAME] = package
module = importlib.import_module(NAME + '.kctrl_start')
policy = importlib.import_module(NAME + '.kctrl_start_policy')
context = importlib.import_module(NAME + '.kctrl_start_context')
integration = importlib.import_module(NAME + '.integration')
builder = importlib.import_module(NAME + '.build_candidate')

FOOTER = ('; filament_max_volumetric_speed = 23,24\n'
          '; filament_diameter = 1.75,1.75\n; travel_acceleration = 11000\n')


class Gcmd:
    def __init__(self, **params): self.params, self.messages = params, []
    def get(self, key, default=None): return self.params.get(key, default)
    def get_int(self, key, **bounds):
        value = int(self.params[key])
        assert bounds.get('minval', -math.inf) <= value <= bounds.get('maxval', math.inf)
        return value
    def get_float(self, key, **bounds):
        value = float(self.params[key])
        assert bounds.get('minval', -math.inf) <= value <= bounds.get('maxval', math.inf)
        return value
    def respond_info(self, text): self.messages.append(text)
    def error(self, text): return RuntimeError(text)


class State:
    def __init__(self, data): self.data = data
    def get_status(self, _): return dict(self.data)


class Machine:
    NEVER = float('inf')
    command_error = config_error = RuntimeError

    def __init__(self, tmp_path, head=True, route='T1B', enabled=True):
        self.now = 1.
        self.events, self.handlers, self.outputs, self.timers = [], {}, [], []
        self.position = [150., 150., .3, 0.]
        self.abs_xyz, self.abs_e = True, True
        self.saved = {}
        self.callback = lambda command: None
        self.buffer, self.ack = 0, True
        self.ref_success = True
        self.load_success = True
        self.current_success = True
        self.fail_register = None
        self.path = tmp_path / 'job.gcode'
        self.path.write_text('START_PRINT\nT0\n' + FOOTER, encoding='utf-8')
        self.envelope = policy.PurgeEnvelope()
        box = {'enable': 1, 'state': 'connect', 'T1': {'state': 'connect', 'mode': '0',
                'filament': 'None'},
               'T2': {'state': 'connect', 'mode': '0', 'filament': 'None'},
               'T3': {'state': 'None'}, 'T4': {'state': 'None'}}
        if route: box['T' + route[1]]['filament'] = route[2]
        self.data = {
            'toolhead': {'homed_axes': 'xyz'},
            'extruder': {'temperature': 100., 'target': 100., 'can_extrude': False},
            'heater_bed': {'target': 55.},
            'pause_resume': {'is_paused': False},
            'print_stats': {'filename': 'job.gcode', 'state': 'printing'},
            'kctrl_end': {'pending': False, 'job_epoch': 1},
            'filament_switch_sensor filament_sensor_2': {'filament_detected': head, 'enabled': False},
            'filament_switch_sensor filament_sensor': {'filament_detected': True},
            'tmc2209 extruder': {'run_current': .280763, 'hold_current': .280763},
            'configfile': {'settings': {'tmc2209 extruder': {'run_current': .55, 'hold_current': 2.},
                          'printer': {'max_velocity': 800., 'max_accel': 20000., 'max_accel_to_decel': 20000.}}},
            'box': box,
            'kctrl_bin_motion': {'installed': True},
        }
        self.objects = {name: State(value) for name, value in self.data.items()}
        self.objects['toolhead'].wait_moves = lambda: self.events.append(('wait_moves',))
        self.objects['toolhead'].get_position = lambda: self.position[:]
        self.objects['gcode'] = self
        self.objects['heaters'] = SimpleNamespace(turn_off_all_heaters=self.cool)
        self.objects['kctrl_purge_guard'] = SimpleNamespace(
            get_status=lambda _: {'installed': True, 'bin_latched': self.envelope.latched})
        self.objects['kctrl_slot_map'] = SimpleNamespace(printing_file=lambda: str(self.path))
        self.change = SimpleNamespace(run_stock=self.stock_wrapper, last={})
        self.objects['kctrl_tool_change'] = self.change
        self.action = SimpleNamespace(
            communication_set_box_mode=self.set_mode, send_data=self.send_data,
            communication_get_buffer_state=self.read_buffer,
            box_state=SimpleNamespace(get_Tn_inner_data=lambda *a, **k: self.buffer),
            update_filament_pos=self.commit, box_save=SimpleNamespace(last_cmd=route),
            extrude_tnn=None)
        self.objects['box'].box_action = self.action
        self.ready_gcode_handlers = {'ACCURATE_G28': self.reference,
                'BOX_QUIT_MATERIAL': lambda _: self.events.append(('official_unload',)),
                'BOX_EXTRUDE_MATERIAL': lambda _: self.events.append(('official_load',)),
                'BOX_CUT_MATERIAL': lambda _: self.events.append(('official_cut',)),
                'BOX_RETRUDE_MATERIAL': lambda _: self.events.append(('official_retract',))}
        self.enabled = enabled
        self.owner = module.KctrlStart(self)
        self.owner._ready()

    def get_printer(self): return self
    def get_reactor(self): return self
    def getboolean(self, key, default): return self.enabled
    def getint(self, key, default, **kwargs): return default
    def getfloat(self, key, default, **kwargs): return default
    def monotonic(self): return self.now
    def lookup_object(self, key): return self.objects[key]
    def register_event_handler(self, event, handler): self.handlers.setdefault(event, []).append(handler)
    def register_output_handler(self, handler): self.outputs.append(handler)
    def register_timer(self, fn, when):
        timer = (fn, when)
        self.timers.append(timer)
        return timer
    def unregister_timer(self, timer): self.timers.remove(timer)
    def register_command(self, name, handler):
        old = self.ready_gcode_handlers.pop(name, None)
        if handler is not None:
            if self.fail_register == name:
                self.fail_register = None
                raise RuntimeError('registration_failure')
            self.ready_gcode_handlers[name] = handler
        return old
    def fire(self, event):
        for handler in self.handlers.get(event, []): handler()
    def cool(self):
        self.events.append(('cool',))
        self.data['extruder']['target'] = self.data['heater_bed']['target'] = 0.
    def reference(self, _):
        self.events.append(('reference',))
        if not self.ref_success: raise RuntimeError('contact_failed')
        self.data['toolhead']['homed_axes'] = 'xyz'
        self.data['extruder'].update(temperature=100., target=100., can_extrude=False)
        self.callback('reference')
    def set_mode(self, addr, mode, slot):
        self.events.append(('mode', addr, mode, slot))
        if self.ack: self.data['box']['T%d' % addr]['mode'] = '2'
        self.callback('mode_ack')
        return self.ack
    def send_data(self, address, command, timeout):
        assert address in (b'\x01', b'\x02') and command == b'\x0a' and timeout == 2
        self.events.append(('box_read', address[0]))
        return self.ack
    def read_buffer(self, addr):
        self.events.append(('buffer', addr, self.buffer))
        self.callback('buffer_read')
        return self.ack
    def commit(self, slot, value):
        self.events.append(('commit', slot, value))
        self.data['box']['T' + slot[1]]['filament'] = value[2]
    def stock_wrapper(self, name, plan, stock, gcmd): return stock(gcmd)
    def stock(self, _):
        self.events.append(('stock_T',))
        self.action.extrude_tnn = 'T1B'
        self.data['filament_switch_sensor filament_sensor_2']['filament_detected'] = True
        if not self.load_success:
            self.data['pause_resume']['is_paused'] = True
        else:
            self.data['box']['T1']['filament'] = 'B'
            self.action.box_save.last_cmd = 'T1B'

    def run_script_from_command(self, text):
        for line in text.splitlines():
            self.events.append(('gcode', line))
            parts = line.split()
            command = parts[0]
            args = dict(part.split('=', 1) for part in parts[1:] if '=' in part)
            if command == 'SET_TMC_CURRENT' and self.current_success:
                self.data['tmc2209 extruder'].update(run_current=float(args['CURRENT']),
                                                    hold_current=float(args['HOLDCURRENT']))
            elif command == 'SAVE_GCODE_STATE': self.saved[args['NAME']] = (self.abs_xyz, self.abs_e)
            elif command == 'RESTORE_GCODE_STATE':
                assert args['MOVE'] == '0'
                self.abs_xyz, self.abs_e = self.saved[args['NAME']]
            elif command == 'G90': self.abs_xyz = True
            elif command == 'G91': self.abs_xyz = False
            elif command == 'M83': self.abs_e = False
            elif command == 'M109':
                temp = float(parts[1][1:])
                self.data['extruder'].update(temperature=temp, target=temp, can_extrude=True)
            elif command == 'G1':
                target = self.position[:]
                for part in parts[1:]:
                    if part[0] in 'XYZE':
                        i = 'XYZE'.index(part[0])
                        absolute = self.abs_e if i == 3 else self.abs_xyz
                        target[i] = float(part[1:]) + (0 if absolute else target[i])
                latch = self.envelope.check(self.position, target,
                    homed=self.data['toolhead']['homed_axes'] == 'xyz')
                self.position = target
                self.envelope.commit(latch)
                self.events.append(('move', tuple(target)))
            elif command == 'T0': self.change.run_stock('T0', {'physical': 'T1B'}, self.stock, Gcmd())
            self.callback(line)

    def plan(self): self.owner.plan(Gcmd(SLOT='T1B', INDEX=0, TEMP=195.))
    def referenced(self):
        self.plan()
        self.ready_gcode_handlers['ACCURATE_G28'](Gcmd())
        self.owner.reference_ready(Gcmd())
    def finish(self): self.owner.material(Gcmd())
    def commands(self): return [event[1] for event in self.events if event[0] == 'gcode']
    def commits(self): return [event for event in self.events if event[0] == 'commit']


def test_disabled_has_no_hooks_or_effects(tmp_path):
    m = Machine(tmp_path, enabled=False)
    assert m.events == [] and m.owner.originals == {}
    assert m.change.run_stock == m.stock_wrapper
    with pytest.raises(RuntimeError, match='disabled'): m.plan()
    assert m.events == []


def test_planning_without_xyz_is_read_only_but_material_requires_new_reference(tmp_path):
    m = Machine(tmp_path)
    m.data['toolhead']['homed_axes'] = ''
    m.plan()
    assert m.events == []
    with pytest.raises(RuntimeError, match='start_invalidated'): m.finish()
    assert m.commands() == []
    assert m.events == [('cool',)]


def test_old_xyz_never_substitutes_for_new_reference(tmp_path):
    m = Machine(tmp_path)
    m.plan()
    with pytest.raises(RuntimeError, match='fresh_reference_missing'): m.owner.reference_ready(Gcmd())
    assert 'G1' not in '\n'.join(m.commands())


def test_keep_purges_once_without_stock_and_exits_before_finalization(tmp_path):
    m = Machine(tmp_path)
    m.referenced()
    m.finish()
    assert m.owner.phase == 'complete' and m.owner.run['branch'] == 'keep'
    assert ('stock_T',) not in m.events
    assert m.commands().count('G1 E20 F360.00000') == 7
    assert m.commands().count('G1 Y291.5 F15000') == 3
    assert not any('X187' in line or 'X210' in line or 'M112' in line for line in m.commands())
    assert m.position[:3] == pytest.approx([185.5, 273., 35.1])
    assert m.commits() == [('commit', 'T1B', 'T1B')]
    assert m.events.index(('gcode', 'G1 Y273 F15000')) < m.events.index(m.commits()[0])
    assert m.events.index(('gcode', 'M400')) < m.events.index(('mode', 1, 'PRINT', 'B'))
    assert m.action.box_save.last_cmd == 'T1B' and m.timers == []
    assert m.abs_xyz and m.abs_e


def test_empty_and_other_known_slot_use_stock_once(tmp_path):
    for head, route, branch in ((False, None, 'empty'), (True, 'T1A', 'change')):
        m = Machine(tmp_path, head=head, route=route)
        m.referenced()
        m.finish()
        assert m.owner.run['branch'] == branch
        assert m.events.count(('stock_T',)) == 1
        assert not m.commits()
        assert not any(line.startswith('G1 E') for line in m.commands())
        restore = next(i for i, e in enumerate(m.events) if e[0]=='gcode' and e[1].startswith('SET_TMC'))
        assert restore < m.events.index(('stock_T',))


def test_unknown_loaded_route_refuses_even_if_next_job_selects_it(tmp_path):
    m = Machine(tmp_path, route=None)
    with pytest.raises(RuntimeError, match='identity'): m.plan()
    assert m.events == [] and not m.commits()


def test_explicit_adoption_is_no_effect_and_only_purge_can_commit(tmp_path):
    m = Machine(tmp_path, route=None)
    m.data['print_stats']['state'] = 'error'
    m.owner.adopt(Gcmd(SLOT='T1B'))
    assert not m.events and m.action.box_save.last_cmd is None
    m.data['print_stats']['state'] = 'printing'
    m.referenced()
    m.finish()
    assert m.owner.run['branch'] == 'recover'
    assert m.commands().count('BOX_ERROR_CLEAR') == 1
    assert m.commits() and m.owner.adopted is None


def test_second_cfs_and_second_filament_keep_their_own_route_and_profile(tmp_path):
    m = Machine(tmp_path, route='T2D')
    m.path.write_text(FOOTER.replace('23,24', '24,10'))
    m.owner.plan(Gcmd(SLOT='T2D', INDEX=1, TEMP=225.))
    m.ready_gcode_handlers['ACCURATE_G28'](Gcmd())
    m.owner.reference_ready(Gcmd())
    m.finish()
    assert ('mode', 2, 'PRINT', 'D') in m.events
    assert m.commits() == [('commit', 'T2D', 'T2D')]
    assert m.change.last['tool'] == 'T1'
    assert m.owner.run['motion']['volumetric_limit'] == 10.
    assert m.commands().count('G1 E20 F249.45101') == 7


def test_failed_empty_insertion_can_be_recovered_on_next_epoch(tmp_path):
    m = Machine(tmp_path, head=False, route=None)
    m.load_success = False
    m.referenced()
    with pytest.raises(RuntimeError, match='start_paused'): m.finish()
    assert m.owner.attempt == {'slot': 'T1B', 'has_head': True}
    m.data['pause_resume']['is_paused'] = False
    m.data['kctrl_end']['job_epoch'] += 1
    m.events.clear()
    m.referenced()
    m.finish()
    assert m.owner.run['branch'] == 'recover'
    assert ('stock_T',) not in m.events and m.commits()


def test_new_job_after_failed_probe_not_stuck_in_planned_phase(tmp_path):
    m = Machine(tmp_path)
    m.plan()
    m.ref_success = False
    with pytest.raises(RuntimeError): m.ready_gcode_handlers['ACCURATE_G28'](Gcmd())
    m.data['kctrl_end']['job_epoch'] += 1
    m.ref_success = True
    m.referenced()
    m.finish()
    assert m.owner.phase == 'complete'


def test_reported_probe_error_does_not_validate_old_xyz(tmp_path):
    m = Machine(tmp_path)
    m.plan()
    m.callback = lambda line: m.owner._output('!! contact failed') if line == 'reference' else None
    with pytest.raises(policy.StartRefused, match='firmware_reported_error'):
        m.ready_gcode_handlers['ACCURATE_G28'](Gcmd())
    assert not m.owner.reference_valid and m.owner.reference == 0
    with pytest.raises(RuntimeError): m.owner.reference_ready(Gcmd())
    assert not m.commands()


def test_manual_reference_outside_start_is_not_owned_or_counted(tmp_path):
    m = Machine(tmp_path)
    m.owner.command_error = 'old_failure'
    m.ready_gcode_handlers['ACCURATE_G28'](Gcmd())
    assert m.events == [('reference',)]
    assert m.owner.reference == 0 and not m.owner.reference_valid


@pytest.mark.parametrize('change,expected', [
    (lambda m: m.fire('stepper_enable:motor_off'), 'fresh_reference_missing'),
    (lambda m: m.data['toolhead'].update(homed_axes='xy'), 'axes_not_referenced'),
    (lambda m: m.data['pause_resume'].update(is_paused=True), 'start_paused'),
    (lambda m: m.data['kctrl_end'].update(pending=True), 'end_still_active'),
    (lambda m: m.data['kctrl_end'].update(job_epoch=2), 'job_epoch_changed'),
    (lambda m: m.data['print_stats'].update(filename='other.gcode'), 'job_changed'),
    (lambda m: m.path.write_text('changed'), 'job_changed'),
    (lambda m: m.data['filament_switch_sensor filament_sensor_2'].update(filament_detected=False), 'filament_changed'),
])
def test_changes_after_reference_refuse_before_material(tmp_path, change, expected):
    m = Machine(tmp_path)
    m.referenced()
    m.events.clear()
    change(m)
    with pytest.raises(RuntimeError, match=expected): m.finish()
    assert not m.commands() and not m.commits()


@pytest.mark.parametrize('trigger,effect,expected', [
    ('mode_ack', lambda m: m.fire('gcode:cancel'), 'start_cancelled'),
    ('G1 E20', lambda m: m.fire('stepper_enable:motor_off'), 'fresh_reference_missing'),
    ('G1 E20', lambda m: m.data['extruder'].update(target=0), 'purge_temperature_changed'),
    ('G1 E20', lambda m: m.data['box']['T1'].update(mode='0'), 'cfs_print_mode_lost'),
    ('G1 E20', lambda m: m.data['tmc2209 extruder'].update(run_current=.28), 'extruder_current_changed'),
    ('G1 E20', lambda m: m.data['pause_resume'].update(is_paused=True), 'start_paused'),
    ('G1 E20', lambda m: m.data['kctrl_end'].update(pending=True), 'end_still_active'),
    ('G1 E20', lambda m: m.data['print_stats'].update(state='cancelled'), 'print_no_longer_active'),
    ('G1 E20', lambda m: setattr(m, 'now', 1000.), 'material_timeout'),
    ('G1 E20', lambda m: m.owner._output('!! new failure'), 'firmware_reported_error'),
    ('buffer_read', lambda m: m.data['box']['T1'].update(filament='A'), 'retained_filament_changed'),
])
def test_inflight_faults_stop_without_retries_commits_or_emergency(tmp_path, trigger, effect, expected):
    m = Machine(tmp_path)
    m.referenced()
    m.callback = lambda line: effect(m) if line.startswith(trigger) else None
    with pytest.raises(RuntimeError, match=expected): m.finish()
    assert not m.commits() and ('stock_T',) not in m.events
    assert sum(line.startswith('G1 E20') for line in m.commands()) <= 1
    assert m.data['extruder']['target'] == m.data['heater_bed']['target'] == 0
    assert not any('M112' in line or 'G28' in line or 'MOVE=1' in line for line in m.commands())
    assert m.timers == [] and m.abs_e


@pytest.mark.parametrize('buffer', [1, 2, None, True, '0'])
def test_buffer_requires_real_consumption_not_a_boolean_or_unknown(tmp_path, buffer):
    m = Machine(tmp_path)
    m.buffer = buffer
    m.referenced()
    with pytest.raises(RuntimeError, match='buffer_'): m.finish()
    assert not m.commits()


def test_current_and_ack_failures_never_extrude(tmp_path):
    for failure in ('current_success', 'ack'):
        m = Machine(tmp_path)
        setattr(m, failure, False)
        m.referenced()
        with pytest.raises(RuntimeError): m.finish()
        assert not any(line.startswith('G1 E') for line in m.commands())
        assert not m.commits()


def test_already_lower_bed_is_not_raised_for_retained_purge(tmp_path):
    m = Machine(tmp_path)
    m.position[2] = 60.
    m.referenced()
    m.finish()
    assert m.position[2] == 60.
    assert not any(line.startswith('G1 Z') for line in m.commands())


def test_watchdog_turns_heaters_off_and_does_not_issue_a_motion(tmp_path):
    m = Machine(tmp_path)
    m.referenced()
    m.callback = lambda line: m.owner._watchdog(m.now) if line == 'mode_ack' else None
    with pytest.raises(RuntimeError, match='material_timeout'): m.finish()
    assert not any(line.startswith('G1 E') for line in m.commands())
    assert m.data['extruder']['target'] == m.data['heater_bed']['target'] == 0


def test_ready_can_run_twice_without_nested_wrapping(tmp_path):
    m = Machine(tmp_path)
    originals = dict(m.owner.originals)
    m.owner._ready()
    assert m.owner.originals == originals and m.events == []


def test_midprint_tool_change_still_uses_existing_wrapper_and_nominal_current(tmp_path):
    m = Machine(tmp_path, head=False, route=None)
    m.change.run_stock('T0', {'physical': 'T1B'}, m.stock, Gcmd())
    assert m.events.count(('stock_T',)) == 1
    assert m.data['tmc2209 extruder']['run_current'] == .55
    assert m.data['tmc2209 extruder']['hold_current'] == .55


def test_old_failed_file_cannot_be_used_as_a_new_console_print(tmp_path):
    m = Machine(tmp_path)
    m.data['print_stats']['state'] = 'error'
    with pytest.raises(RuntimeError, match='new_print_not_active'): m.plan()
    assert m.events == []


def test_manual_withdrawal_invalidates_previous_attribution(tmp_path):
    m = Machine(tmp_path, route=None)
    m.owner.attempt = {'slot': 'T1B', 'has_head': True}
    m.owner.adopted = m.action.extrude_tnn = 'T1B'
    m.ready_gcode_handlers['BOX_QUIT_MATERIAL'](Gcmd())
    with pytest.raises(RuntimeError, match='identity'): m.plan()


def test_temperature_contact_and_sensor_continuity_checked(tmp_path):
    for mutation in ('temperature', 'upstream'):
        m = Machine(tmp_path)
        m.plan()
        m.ready_gcode_handlers['ACCURATE_G28'](Gcmd())
        if mutation == 'temperature': m.data['extruder']['temperature'] = 150.
        else: m.data['filament_switch_sensor filament_sensor']['filament_detected'] = False
        with pytest.raises(RuntimeError): m.owner.reference_ready(Gcmd())
        assert ('stock_T',) not in m.events and not m.commits()


def test_ready_registration_failure_rolls_back_all_handlers(tmp_path):
    m = Machine(tmp_path, enabled=False)
    before = dict(m.ready_gcode_handlers)
    m.owner.enabled = True
    m.fail_register = 'BOX_QUIT_MATERIAL'
    with pytest.raises(RuntimeError, match='registration_failure'): m.owner._ready()
    assert m.ready_gcode_handlers == before and not m.owner.originals
    assert m.change.run_stock == m.stock_wrapper and m.events == []


def test_file_limits_follow_selected_filament_and_reject_bad_data(tmp_path):
    path = tmp_path / 'profile.gcode'
    path.write_text(FOOTER.replace('23,24', '10;24'))
    assert context.file_motion(str(path), 0)['feed'] == pytest.approx(10 / (math.pi * 1.75**2 / 4))
    assert context.file_motion(str(path), 1)['feed'] == 6.
    for text in (FOOTER.replace('23,24', 'nan,24'), FOOTER.replace('1.75,1.75', '0,1.75'),
                 FOOTER.replace('11000', 'inf'), '', FOOTER + FOOTER):
        path.write_text(text)
        with pytest.raises(policy.StartRefused): context.file_motion(str(path), 0)


def test_macro_integration_orders_decision_after_real_probe_before_any_tool(tmp_path):
    base = (ROOT / 'packages/k1-control-v1/owned-start-print-v2/k1-control-owned-start-print-v2.cfg').read_text()
    candidate = integration.render_start(base)
    start = candidate[candidate.index('[gcode_macro START_PRINT]'):]
    assert (start.index('KCTRL_START_PLAN') < start.index('\n  BOX_START_PRINT\n')
            < start.index('\n  ACCURATE_G28\n') < start.index('\n  BED_MESH_PROFILE LOAD={profile}')
            < start.index('KCTRL_START_REFERENCE_READY') < start.index('KCTRL_START_MATERIAL')
            < start.index('_KCTRL_ASSERT_CFS_OK STAGE=after_tool_change')
            < start.index('KCTRL_WAIT_FILAMENT SENSOR=filament_sensor_2'))
    assert '\n    T{position - 1}\n' not in candidate
    # No unrelated command in the huge existing start/end is rewritten.
    assert candidate.count('KCTRL_START_PLAN SLOT=') == 1
    assert candidate.count('KCTRL_START_REFERENCE_READY\n') == 1
    assert candidate.count('KCTRL_START_MATERIAL\n') == 1
    with pytest.raises(ValueError): integration.render_start(candidate)


def test_python38_grammar_and_every_integrated_macro_parse():
    for source in PACKAGE.glob('*.py'):
        ast.parse(source.read_text(encoding='utf-8'), feature_version=(3, 8))
    base = (ROOT / 'packages/k1-control-v1/owned-start-print-v2/k1-control-owned-start-print-v2.cfg').read_text()
    text = integration.render_start(base)
    env = jinja2.Environment('{%', '%}', '{', '}', extensions=['jinja2.ext.do'])
    parsed = 0
    for block in text.split('\n['):
        if '\ngcode:\n' in block:
            body = block.split('\ngcode:\n', 1)[1]
            env.parse(body)
            parsed += 1
    assert parsed >= 15


@pytest.mark.parametrize('head', [True, False])
def test_rendered_macro_defers_material_branch_to_execution(head):
    base = (ROOT / 'packages/k1-control-v1/owned-start-print-v2/k1-control-owned-start-print-v2.cfg').read_text()
    text = integration.render_start(base)
    block = text.split('[gcode_macro START_PRINT]\n', 1)[1].split('\n[', 1)[0]
    body = block.split('\ngcode:\n', 1)[1]
    profile = 'k1_p001_t055_r001_n11x11'
    printer = {
        'gcode_macro _KCTRL_START_CONF': dict(plate_id=1, probe_rev=1, x_count=11,
                    y_count=11, probe_contact_c=100., soak_seconds=20),
        'kctrl_slot_map': dict(initial_logical='T1A', map={'T1A':'T1B'}, job_count=0,
                              material_temp={'12345': 195.}),
        'save_variables': {'variables': {'z_' + profile: -.04}},
        'bed_mesh': {'profiles': [profile]},
        'toolhead': {'estimated_print_time': 1.},
        'box': {'enable': 1, 'T1': {'state': 'connect', 'material_type': ['-1','012345','-1','-1']}},
        'filament_switch_sensor filament_sensor_2': {'filament_detected': head},
    }
    env = jinja2.Environment('{%', '%}', '{', '}', extensions=['jinja2.ext.do'])
    def reject(message): raise AssertionError(message)
    rendered = env.from_string(body).render(printer=printer,
        params={'BED_TEMP':55, 'EXTRUDER_TEMP':195},
        action_respond_info=lambda _: '', action_raise_error=reject)
    commands = [line.strip() for line in rendered.splitlines()
                if line.strip() and not line.strip().startswith('#')]
    assert 'KCTRL_START_PLAN SLOT=T1B INDEX=0 TEMP=195.0' in commands
    assert commands.count('KCTRL_START_MATERIAL') == 1
    assert commands.index('ACCURATE_G28') < commands.index('KCTRL_START_REFERENCE_READY')
    assert commands.index('KCTRL_START_REFERENCE_READY') < commands.index('KCTRL_START_MATERIAL')
    assert 'T0' not in commands
    assert not any(line.startswith('_KCTRL_CFS_LOAD ') for line in commands)


def test_candidate_preserves_the_installed_end_include_and_its_exact_code():
    manifest, payloads = builder.build()
    text = payloads['k1-control-owned-start-print-v2.cfg'].decode('utf-8')
    assert text.count('[include k1-control-owned-end-candidate.cfg]') == 1
    assert text.index('[include k1-control-owned-end-candidate.cfg]') < text.index('[kctrl_start]')
    assert all(entry['destination'] != builder.END_DEST for entry in manifest['files'])
    assert manifest['before'][builder.END_DEST] == manifest['protected_end_sha256']
    assert sum(entry['before_sha256'] is None for entry in manifest['files']) == 5
    assert len(payloads) == len(manifest['files']) == 6
    assert manifest['installed'] is manifest['installer_ready'] is False


def test_generated_candidate_and_manifest_are_current():
    import json
    manifest, payloads = builder.build()
    assert json.loads((PACKAGE / 'manifest.json').read_text()) == manifest
    assert (PACKAGE / 'k1-control-owned-start-print-v2.cfg').read_bytes() == payloads['k1-control-owned-start-print-v2.cfg']
