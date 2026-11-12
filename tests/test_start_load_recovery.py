"""start-load-recovery-v1 (ADR-079, document 108) on the fake Klipper/CFS.

The failure of 12 November 2026 at 17:11 is replayed from its reduced log:
key837 on T1B, the stock pause inside START_PRINT, the head moved into the
bin and our bin guard refusing the descent while cutting every heater. The
same start must finish with the retained purge; every unproven case must
still fail closed. Software validation only, no printer transport.
"""

import ast
import importlib
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

import test_retained_start_integration as base
from test_retained_start_integration import Gcmd
from test_retained_start_integration import (  # noqa: F401  rerun on the new module
    test_disabled_has_no_hooks_or_effects,
    test_planning_without_xyz_is_read_only_but_material_requires_new_reference,
    test_old_xyz_never_substitutes_for_new_reference,
    test_keep_purges_once_without_stock_and_exits_before_finalization,
    test_empty_and_other_known_slot_use_stock_once,
    test_unknown_loaded_route_refuses_even_if_next_job_selects_it,
    test_explicit_adoption_is_no_effect_and_only_purge_can_commit,
    test_second_cfs_and_second_filament_keep_their_own_route_and_profile,
    test_new_job_after_failed_probe_not_stuck_in_planned_phase,
    test_reported_probe_error_does_not_validate_old_xyz,
    test_manual_reference_outside_start_is_not_owned_or_counted,
    test_changes_after_reference_refuse_before_material,
    test_inflight_faults_stop_without_retries_commits_or_emergency,
    test_buffer_requires_real_consumption_not_a_boolean_or_unknown,
    test_current_and_ack_failures_never_extrude,
    test_already_lower_bed_is_not_raised_for_retained_purge,
    test_watchdog_turns_heaters_off_and_does_not_issue_a_motion,
    test_ready_can_run_twice_without_nested_wrapping,
    test_midprint_tool_change_still_uses_existing_wrapper_and_nominal_current,
    test_old_failed_file_cannot_be_used_as_a_new_console_print,
    test_manual_withdrawal_invalidates_previous_attribution,
    test_temperature_contact_and_sensor_continuity_checked,
    test_ready_registration_failure_rolls_back_all_handlers,
)

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'packages/k1-control-v1/start-load-recovery-v1'
NAME = '_start_load_recovery'
package = ModuleType(NAME)
package.__path__ = [str(PACKAGE), str(ROOT / 'packages/k1-control-v1/retained-start-v1'),
                    str(ROOT / 'packages/k1-control-v1/end-rewind-confirm-v3')]
sys.modules[NAME] = package
module = importlib.import_module(NAME + '.kctrl_start')
policy = importlib.import_module(NAME + '.kctrl_start_policy')
FIXTURE = ROOT / 'tests/fixtures/k1-control-v1/start-load-recovery-v1/12-novembre-1704-extrait.log'

# The vendor pause_resume module exposes reportInformation at module level.
VENDOR = ModuleType('_fake_vendor_pause_resume')
sys.modules[VENDOR.__name__] = VENDOR


@pytest.fixture(autouse=True)
def new_module(monkeypatch):
    """Every Machine, including the reran retained-start tests, uses the V1 candidate."""
    monkeypatch.setattr(base, 'module', module)
    monkeypatch.setattr(base, 'policy', policy)


class FakePause:
    def __init__(self, machine):
        self.machine = machine
        self.pause_command_sent = self.sd_paused = False

    @property
    def is_paused(self): return self.machine.data['pause_resume']['is_paused']

    @is_paused.setter
    def is_paused(self, value): self.machine.data['pause_resume']['is_paused'] = value

    def get_status(self, _): return dict(self.machine.data['pause_resume'])


FakePause.__module__ = VENDOR.__name__


def fixture_messages(until='17:11:14,483'):
    """Messages of the real start, in order, up to our guard refusal."""
    out = []
    for line in FIXTURE.read_text(encoding='utf-8').splitlines():
        stamp, _, message = line.partition(' ')
        if stamp > until:
            break
        out.append(message)
    return out


KEY837 = next(m for m in fixture_messages() if '"key837"' in m)
GUARD = next(m for m in fixture_messages() if m.startswith(module.GUARD_REFUSAL))


class Machine(base.Machine):
    """Retained-start harness plus the vendor objects the recovery touches."""

    def __init__(self, tmp_path, head=False, route=None, failure='real', **kwargs):
        self.failure = failure
        self.reports = []
        self.stale = False
        self.sd_active = True
        self.clears_error = True
        self.stock_ran = 0
        super().__init__(tmp_path, head=head, route=route, **kwargs)
        VENDOR.reportInformation = self.reports.append
        self.pause = self.objects['pause_resume'] = FakePause(self)
        self.sd = self.objects['virtual_sdcard'] = SimpleNamespace(
            must_pause_work=False, is_active=lambda: self.sd_active)
        self.objects['gcode_move'] = SimpleNamespace(reset_last_position=self.reset_position)
        box = self.objects['box']
        box.inside_error = False
        box.record_tn_move_z = lambda value: self.events.append(('record_z', value))
        self.action.box_save.move_z = None
        self.action.box_save.last_err = None
        self.load_success = failure is None

    def lookup_object(self, key, default=KeyError):
        if default is KeyError or key in self.objects:
            return self.objects[key]
        return default

    def register_timer(self, fn, when):
        timer = [fn, when]
        self.timers.append(timer)
        return timer

    def update_timer(self, timer, when):
        assert timer in self.timers
        timer[1] = when
        self.events.append(('timer', when))

    def reset_position(self):
        self.events.append(('reset_position',))
        self.stale = False

    def emit(self, text):
        for handler in self.outputs:
            handler(text)

    def stock(self, gcmd):
        self.stock_ran += 1
        if self.failure is None:
            return super().stock(gcmd)
        self.events.append(('stock_T',))
        self.action.extrude_tnn = 'T1B'
        self.data['filament_switch_sensor filament_sensor_2']['filament_detected'] = True
        # z_down accumulated 0.8 + 20 + 30.04 + 30.14 before the feed loops.
        self.action.box_save.move_z = 30.14
        self.now += 185.
        if self.failure == 'real':
            for message in fixture_messages():
                self.emit('!! ' + message if message.startswith(module.GUARD_REFUSAL) else message)
            self.stock_pause(refuse=True)
        elif self.failure == 'lines':
            for text in self.extra_lines:
                self.emit(text)
            self.stock_pause(refuse=False)
        elif self.failure == 'error_only':
            self.emit(KEY837)
            self.action.box_save.last_err = 'box_extrude_err'
        elif self.failure == 'pause_only':
            self.stock_pause(refuse=False)
        self.after_stock()

    def after_stock(self): pass

    def stock_pause(self, refuse):
        self.action.box_save.last_err = 'box_extrude_err'
        self.data['pause_resume']['is_paused'] = True
        self.pause.pause_command_sent = self.pause.sd_paused = True
        self.sd.must_pause_work = True
        # The stock feed loops ran at the bin (Y305); BOX_MOVE_TO_SAFE_POS
        # then left the head at Y291.5, still latched (17:11:14,482).
        for target in ((210., 273., 35.0133), (210., 305., 35.0133), (210., 291.5, 35.0133)):
            latch = self.envelope.check(self.position, list(target) + [self.position[3]])
            self.position[:3] = target
            self.envelope.commit(latch)
        self.stale = True
        if refuse:
            with pytest.raises(policy.StartRefused, match='below_30mm'):
                self.envelope.check(self.position, [210., 291.5, 4.7989, self.position[3]])
            self.cool()

    def run_script_from_command(self, text):
        for line in text.splitlines():
            parts = line.split()
            command = parts[0] if parts else ''
            if command == 'G1':
                assert not self.stale, 'move planned from a stale gcode position'
            if command == 'BOX_ERROR_CLEAR' and self.clears_error:
                self.action.box_save.last_err = None
            if command in ('M140', 'M190'):
                self.data['heater_bed']['target'] = float(parts[1][1:])
            super().run_script_from_command(line)

    def failed_start(self):
        self.referenced()
        self.events.clear()
        self.finish()


def e_moves(m): return [c for c in m.commands() if c.startswith('G1 E')]


def assert_closed(m, reason):
    assert m.owner.phase == 'failed' and reason in m.owner.failure
    assert e_moves(m) == [] and m.commits() == []
    assert m.data['extruder']['target'] == m.data['heater_bed']['target'] == 0
    assert m.timers == []


# --- the real failure ------------------------------------------------------

def test_fixture_lines_of_the_real_failure_are_the_tolerated_ones():
    lines = [m for m in fixture_messages() if m.startswith('!!')] + ['!! ' + GUARD]
    assert module.classify_stock_errors(lines, 'T1B') == (['key837', 'bin_guard'], [])
    codes, others = module.classify_stock_errors(lines, 'T1A')
    assert codes == ['bin_guard'] and others == [KEY837]
    assert module.classify_stock_errors(lines, 'T2B')[1] == [KEY837]


def test_real_failure_of_12_november_recovers_within_the_same_start(tmp_path):
    m = Machine(tmp_path)
    m.referenced()
    gcmd = Gcmd()
    m.owner.material(gcmd)
    assert m.owner.phase == 'complete' and m.owner.run['branch'] == 'empty'
    assert gcmd.messages[-1] == 'K1 Control: filament T1B pret (empty, repris)'
    assert 'en echec (bin_guard, key837)' in gcmd.messages[0]
    assert m.stock_ran == 1 and m.events.count(('stock_T',)) == 1
    # The stock pause is undone, never resumed, and the screen is told.
    assert m.data['pause_resume']['is_paused'] is False
    assert not (m.pause.pause_command_sent or m.pause.sd_paused or m.sd.must_pause_work)
    assert m.reports == ['key602']
    assert not any(c.startswith(('RESUME', 'PAUSE', 'M112', 'G28')) for c in m.commands())
    # Lift record cleared and position reset before the first purge move.
    assert m.action.box_save.move_z is None and ('record_z', 0) in m.events
    first_move = next(i for i, e in enumerate(m.events) if e[0] == 'gcode' and e[1].startswith('G1'))
    assert m.events.index(('reset_position',)) < first_move
    # Bin exit at constant height first, then the retained purge and release.
    assert m.events[first_move] == ('gcode', 'G1 Y273 F24000')
    assert not any(c.startswith('G1 Z') for c in m.commands())
    assert len(e_moves(m)) == 7 and m.commands().count('G1 Y291.5 F15000') == 3
    assert m.position[:3] == pytest.approx([185.5, 273., 35.0133])
    assert m.commits() == [('commit', 'T1B', 'T1B')] and m.action.box_save.last_err is None
    # Bed: cut by the guard, re-commanded before the purge, waited for after.
    commands = m.commands()
    assert commands.index('M140 S55.000') < commands.index('G1 E20 F360.00000')
    assert commands.index('G1 Y273 F15000') < commands.index('M190 S55.000')
    assert m.data['heater_bed']['target'] == 55. and m.data['extruder']['target'] == 200.
    status = m.owner.get_status()
    assert status['recovery'] == {'codes': ['bin_guard', 'key837'], 'paused': True,
                                  'lift': 30.14, 'bed': 55., 'slot': 'T1B', 'outcome': 'purged'}
    assert ('timer', 1. + 185. + 180.) in m.events and m.timers == []
    assert m.abs_xyz and m.abs_e


def test_clean_stock_load_keeps_the_usual_path(tmp_path):
    m = Machine(tmp_path, failure=None)
    m.referenced()
    gcmd = Gcmd()
    m.owner.material(gcmd)
    assert gcmd.messages == ['K1 Control: filament T1B pret (empty)']
    assert m.owner.get_status()['recovery'] is None
    assert e_moves(m) == [] and m.commits() == [] and m.reports == []
    assert not any(c.startswith(('M140', 'M190', 'BOX_ERROR_CLEAR')) for c in m.commands())
    assert ('record_z', 0) not in m.events and ('reset_position',) not in m.events


def test_error_without_pause_recovers_without_touching_pause_flags(tmp_path):
    m = Machine(tmp_path, failure='error_only')
    m.referenced()
    m.finish()
    assert m.owner.phase == 'complete'
    assert m.owner.recovery['codes'] == ['key837'] and m.owner.recovery['paused'] is False
    assert m.reports == [] and 'M140 S55.000' not in m.commands()
    assert 'M190 S55.000' in m.commands()


def test_pause_without_reported_line_is_also_evidence(tmp_path):
    m = Machine(tmp_path, failure='pause_only')
    m.referenced()
    gcmd = Gcmd()
    m.owner.material(gcmd)
    assert 'en echec (pause stock)' in gcmd.messages[0]
    assert m.owner.recovery['codes'] == [] and m.owner.phase == 'complete'


def test_bed_off_before_the_load_is_not_turned_on(tmp_path):
    m = Machine(tmp_path)
    m.data['heater_bed']['target'] = 0.
    m.referenced()
    m.finish()
    assert m.owner.phase == 'complete' and 'bed' not in m.owner.recovery
    assert not any(c.startswith(('M140', 'M190')) for c in m.commands())


# --- untolerated evidence ----------------------------------------------------

@pytest.mark.parametrize('lines', [
    [KEY837.replace('[1, "B"]', '[1, "A"]')],
    [KEY837.replace('[1, "B"]', '[2, "B"]')],
    [KEY837.replace('[1, "B"]', '["1", "B"]')],
    [KEY837.replace('key837', 'key845')],
    ['!! {"code": "key837"}'],
    ['!! not json'],
    [KEY837] * 33,
    [KEY837, '!! Move out of range'],
])
def test_any_other_reported_line_fails_closed_and_leaves_the_pause(tmp_path, lines):
    m = Machine(tmp_path, failure='lines')
    m.extra_lines = lines
    m.referenced()
    with pytest.raises(RuntimeError, match='firmware_reported_error'): m.finish()
    assert_closed(m, 'firmware_reported_error')
    assert m.data['pause_resume']['is_paused'] is True and m.sd.must_pause_work
    assert m.owner.recovery is None and m.reports == []
    assert ('record_z', 0) not in m.events


@pytest.mark.parametrize('change,reason', [
    (lambda m: m.data['filament_switch_sensor filament_sensor_2'].update(filament_detected=False),
     'stock_load_failed_head_not_loaded'),
    (lambda m: m.data['filament_switch_sensor filament_sensor'].update(filament_detected=False),
     'stock_load_failed_head_not_loaded'),
    (lambda m: m.data['filament_switch_sensor filament_sensor'].update(filament_detected=None),
     'filament_sensor_unknown'),
    (lambda m: setattr(m.action, 'extrude_tnn', 'T1A'), 'stock_load_failed_slot_unproven'),
    (lambda m: m.data['box']['T2'].update(filament='A'), 'stock_load_failed_other_route'),
    (lambda m: setattr(m.objects['box'], 'inside_error', True), 'cfs_error_still_processing'),
    (lambda m: delattr(m.action.box_save, 'move_z'), 'cfs_lift_record_unknown'),
    (lambda m: delattr(m.action.box_save, 'last_err'), 'cfs_lift_record_unknown'),
    (lambda m: delattr(m.objects['box'], 'record_tn_move_z'), 'cfs_lift_record_unknown'),
    (lambda m: m.objects.update(gcode_move=SimpleNamespace()), 'gcode_position_reset_missing'),
    (lambda m: setattr(m, 'sd_active', False), 'stock_pause_not_reversible'),
    (lambda m: m.objects.pop('virtual_sdcard'), 'stock_pause_not_reversible'),
    (lambda m: delattr(m.pause, 'sd_paused'), 'stock_pause_not_reversible'),
    (lambda m: m.data['print_stats'].update(state='cancelled'), 'print_no_longer_active'),
    (lambda m: m.data['kctrl_end'].update(pending=True), 'end_still_active'),
    (lambda m: m.data['kctrl_end'].update(job_epoch=2), 'job_epoch_changed'),
    (lambda m: m.fire('stepper_enable:motor_off'), 'fresh_reference_missing'),
    (lambda m: m.owner._watchdog(m.now), 'material_timeout'),
    (lambda m: setattr(m, 'now', 1000.), 'material_timeout'),
])
def test_each_unproven_condition_refuses_before_any_effect(tmp_path, change, reason):
    m = Machine(tmp_path)
    m.after_stock = lambda: change(m)
    m.referenced()
    with pytest.raises(RuntimeError, match=reason): m.finish()
    assert_closed(m, reason)
    assert m.owner.recovery is None and m.reports == []
    assert m.action.box_save.__dict__.get('move_z', 30.14) == 30.14
    assert ('record_z', 0) not in m.events and ('reset_position',) not in m.events
    assert not any(c.startswith(('M140', 'M190', 'BOX_ERROR_CLEAR')) for c in m.commands())


def test_unknown_bed_target_before_the_load_refuses(tmp_path):
    m = Machine(tmp_path)
    m.data['heater_bed']['target'] = None
    m.referenced()
    with pytest.raises(RuntimeError, match='bed_target_unknown'): m.finish()
    assert e_moves(m) == [] and m.owner.recovery is None


# --- faults during the recovery purge --------------------------------------

def test_cfs_error_record_not_cleared_stops_before_extruding(tmp_path):
    m = Machine(tmp_path)
    m.clears_error = False
    m.referenced()
    with pytest.raises(RuntimeError, match='cfs_error_not_cleared'): m.finish()
    assert_closed(m, 'cfs_error_not_cleared')
    assert m.owner.recovery['outcome'] == 'failed'


def test_real_blockage_still_fails_on_unconsumed_buffer(tmp_path):
    m = Machine(tmp_path)
    m.buffer = 1
    m.referenced()
    with pytest.raises(RuntimeError, match='buffer_consumption_unconfirmed'): m.finish()
    assert m.commits() == [] and m.owner.recovery['outcome'] == 'failed'
    assert m.data['extruder']['target'] == m.data['heater_bed']['target'] == 0
    assert len(e_moves(m)) == 7 and m.timers == []


@pytest.mark.parametrize('trigger,effect,reason', [
    ('G1 E20', lambda m: m.owner._output('!! new failure'), 'firmware_reported_error'),
    ('G1 E20', lambda m: m.data['pause_resume'].update(is_paused=True), 'start_paused'),
    ('mode_ack', lambda m: m.owner._watchdog(m.now), 'material_timeout'),
    ('G1 E20', lambda m: setattr(m, 'now', m.now + 181.), 'material_timeout'),
    ('M190 S55.000', lambda m: m.data['heater_bed'].update(target=0.), 'bed_target_not_restored'),
])
def test_faults_during_the_recovery_purge_fail_closed(tmp_path, trigger, effect, reason):
    m = Machine(tmp_path)
    m.referenced()
    m.callback = lambda line: effect(m) if line.startswith(trigger) else None
    with pytest.raises(RuntimeError, match=reason): m.finish()
    assert m.owner.phase == 'failed' and m.owner.recovery['outcome'] == 'failed'
    assert m.data['extruder']['target'] == m.data['heater_bed']['target'] == 0
    assert m.timers == [] and m.events.count(('stock_T',)) == 1


def test_recovery_runs_at_most_once_per_start(tmp_path):
    m = Machine(tmp_path)
    m.referenced()
    m.finish()
    with pytest.raises(module.StartRefused, match='stock_load_failed_again'):
        m.owner._recover(m.owner.run, ['key837'], False, Gcmd())


def test_next_plan_forgets_the_previous_recovery(tmp_path):
    m = Machine(tmp_path)
    m.referenced()
    m.finish()
    assert m.owner.get_status()['recovery']['outcome'] == 'purged'
    m.data['kctrl_end']['job_epoch'] += 1
    m.plan()
    assert m.owner.get_status()['recovery'] is None


def test_refused_recovery_keeps_the_next_start_recovery(tmp_path):
    """Former behaviour kept as fallback: a refused in-start recovery still
    lets the next start purge the attributed filament."""
    m = Machine(tmp_path)
    m.after_stock = lambda: delattr(m.objects['gcode_move'], 'reset_last_position')
    m.referenced()
    with pytest.raises(RuntimeError, match='gcode_position_reset_missing'): m.finish()
    assert m.owner.attempt == {'slot': 'T1B', 'has_head': True}


def test_python38_grammar():
    ast.parse((PACKAGE / 'kctrl_start.py').read_text(encoding='utf-8'), feature_version=(3, 8))


def test_status_exposes_revision_and_recovery_timeout(tmp_path):
    m = Machine(tmp_path)
    status = m.owner.get_status()
    assert status['revision'] == 'start-load-recovery-v1'
    assert status['recovery'] is None and status['recovery_timeout'] == 180.
