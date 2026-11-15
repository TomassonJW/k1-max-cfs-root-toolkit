"""resilience-v1 start module (ADR-080, document 109) on the fake Klipper/CFS.

Two exits are proven here: the slot proven at the head survives a restart on
disk, and a start stopped inside the bin leaves it at constant height. Every
earlier start test, the recovery of ADR-079 included, is rerun on this module.
Software validation only, no printer transport.
"""

import ast
import importlib
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

import test_retained_start_integration as base
import test_start_load_recovery as rec
from test_retained_start_integration import Gcmd

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'packages/k1-control-v1/resilience-v1'
NAME = '_resilience_start'
package = ModuleType(NAME)
package.__path__ = [str(PACKAGE), str(ROOT / 'packages/k1-control-v1/retained-start-v1'),
                    str(ROOT / 'packages/k1-control-v1/end-rewind-confirm-v3')]
sys.modules[NAME] = package
module = importlib.import_module(NAME + '.kctrl_start')
policy = importlib.import_module(NAME + '.kctrl_start_policy')

# Rewritten below for this module: the revision, the package path, and the
# bin exit which now follows a refused recovery.
ADAPTED = ('test_status_exposes_revision_and_recovery_timeout', 'test_python38_grammar',
           'test_each_unproven_condition_refuses_before_any_effect')
RERUN = {name: value for name, value in vars(rec).items()
         if name.startswith('test_') and name not in ADAPTED}
globals().update(RERUN)

EXIT = ['SAVE_GCODE_STATE NAME=KCTRL_START_REST', 'G90', 'G1 Y273 F15000', 'M400',
        'RESTORE_GCODE_STATE NAME=KCTRL_START_REST MOVE=0']
MESSAGE = 'K1 Control: tete sortie du bac (Y273), plateau inchange'


def head_file(tmp_path):
    return tmp_path / 'state' / 'kctrl_head.json'


def _keep_watch_apart(monkeypatch, cls):
    """The head watch never ends: keep it out of the timers a start must clear."""
    original = cls.__dict__['register_timer']

    def register_timer(self, fn, when):
        if getattr(fn, '__func__', None) is module.KctrlStart._watch:
            self.watch = [fn, when]
            return self.watch
        return original(self, fn, when)
    monkeypatch.setattr(cls, 'register_timer', register_timer)


@pytest.fixture(autouse=True)
def new_module(monkeypatch):
    """Every Machine, the rerun tests included, drives the resilience candidate."""
    for harness in (base, rec):
        monkeypatch.setattr(harness, 'module', module)
        monkeypatch.setattr(harness, 'policy', policy)
    monkeypatch.setattr(base.Machine, 'get', lambda self, key, default=None: (
        str(head_file(self.path.parent)) if key == 'head_state_file' else default),
        raising=False)
    _keep_watch_apart(monkeypatch, base.Machine)
    _keep_watch_apart(monkeypatch, rec.Machine)


def machine(tmp_path, head=True, route='T1B', failure=None, **kwargs):
    return rec.Machine(tmp_path, head=head, route=route, failure=failure, **kwargs)


def watch(m, times=1):
    for _ in range(times):
        assert m.watch[0](m.now) == m.now + module.WATCH_PERIOD
        m.now += module.WATCH_PERIOD


def on_disk(tmp_path):
    path = head_file(tmp_path)
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None


def sensor(m, name, value):
    m.data['filament_switch_sensor ' + name]['filament_detected'] = value


def stopped_in_bin(tmp_path, change=lambda m: None):
    """A stock load reporting an unknown error, head left latched in the bin."""
    m = machine(tmp_path, head=False, route=None, failure='lines')
    m.extra_lines = ['!! not json']
    m.after_stock = lambda: change(m)
    m.referenced()
    m.events.clear()
    gcmd = Gcmd()
    with pytest.raises(RuntimeError) as caught:
        m.owner.material(gcmd)
    return m, gcmd, str(caught.value)


# --- the earlier tests ------------------------------------------------------

def test_every_earlier_start_test_is_rerun_on_this_module():
    earlier = {name for name in vars(rec) if name.startswith('test_')}
    assert earlier - set(RERUN) == set(ADAPTED) and len(RERUN) == 37
    assert all(globals()[name] is value for name, value in RERUN.items())
    assert base.module is module and rec.module is module and rec.policy is policy


@pytest.mark.parametrize(
    'change,reason', rec.test_each_unproven_condition_refuses_before_any_effect.pytestmark[0].args[1])
def test_each_unproven_condition_refuses_before_any_recovery_effect(tmp_path, change, reason):
    m = rec.Machine(tmp_path)
    m.after_stock = lambda: change(m)
    m.referenced()
    with pytest.raises(RuntimeError, match=reason): m.finish()
    rec.assert_closed(m, reason)
    assert m.owner.recovery is None and m.reports == []
    assert m.action.box_save.__dict__.get('move_z', 30.14) == 30.14
    assert ('record_z', 0) not in m.events
    assert not any(c.startswith(('M140', 'M190', 'BOX_ERROR_CLEAR')) for c in m.commands())
    # The only move left is the bin exit, and only when it was proven safe.
    moves = [c for c in m.commands() if c.startswith('G1')]
    left = m.owner.get_status()['rest'] == 'out_of_bin'
    assert moves == (['G1 Y273 F15000'] if left else [])
    assert m.events.count(('reset_position',)) == len(moves)
    assert m.envelope.latched is not left


def test_python38_grammar():
    ast.parse((PACKAGE / 'kctrl_start.py').read_text(encoding='utf-8'), feature_version=(3, 8))


def test_status_exposes_revision_recovery_head_and_rest(tmp_path):
    m = rec.Machine(tmp_path)
    status = m.owner.get_status()
    assert status['revision'] == 'resilience-v1' == module.REVISION
    assert status['recovery'] is None and status['recovery_timeout'] == 180.
    assert status['head'] is None and status['head_saved'] is True and status['rest'] is None
    assert module.HEAD_STATE_FILE == '/usr/data/k1-control-v1/state/kctrl_head.json'
    assert m.owner.head_file == str(head_file(tmp_path))


# --- the record on disk -----------------------------------------------------

def test_record_is_replaced_atomically_and_removed(tmp_path):
    path = head_file(tmp_path)
    module.write_head(str(path), {'slot': 'T1B', 'source': 'purge', 'saved': 12.5})
    assert json.loads(path.read_text(encoding='utf-8')) == {
        'schema': 1, 'slot': 'T1B', 'source': 'purge', 'saved': 12.5}
    assert module.read_head(str(path)) == {'slot': 'T1B', 'source': 'purge', 'saved': 12.5}
    module.write_head(str(path), {'slot': 'T2D', 'source': 'route', 'saved': 13.})
    assert module.read_head(str(path))['slot'] == 'T2D'
    assert [p.name for p in path.parent.iterdir()] == ['kctrl_head.json']
    module.write_head(str(path), None)
    module.write_head(str(path), None)
    assert not path.exists() and module.read_head(str(path)) is None


@pytest.mark.parametrize('content', [
    '', 'not json', '[]', '"T1B"', '{"schema": 1}', '{"schema": 2, "slot": "T1B"}',
    '{"slot": "T1B"}', '{"schema": 1, "slot": "T9Z"}', '{"schema": 1, "slot": ["T1B"]}',
    '{"schema": 1, "slot": {"T1B": 1}}', '{"schema": 1, "slot": "T1B"', '\x00\x00',
])
def test_unreadable_or_foreign_record_is_ignored_never_guessed(tmp_path, content):
    path = head_file(tmp_path)
    path.parent.mkdir()
    path.write_text(content, encoding='utf-8')
    assert module.read_head(str(path)) is None
    # Klipper still starts, and a live route still lets a start go.
    m = machine(tmp_path)
    assert m.owner.get_status()['head'] is None
    m.referenced()
    m.finish()
    assert m.owner.phase == 'complete' and on_disk(tmp_path)['slot'] == 'T1B'


def test_record_details_are_bounded_when_read(tmp_path):
    path = head_file(tmp_path)
    path.parent.mkdir()
    path.write_text(json.dumps({'schema': 1, 'slot': 'T1C', 'source': 'x' * 99,
                                'saved': 'yesterday', 'extra': [1]}), encoding='utf-8')
    assert module.read_head(str(path)) == {'slot': 'T1C', 'source': 'x' * 32, 'saved': None}
    path.unlink()
    path.mkdir()
    assert module.read_head(str(path)) is None


def test_completed_purge_records_the_slot(tmp_path):
    m = machine(tmp_path)
    assert on_disk(tmp_path) is None
    m.referenced()
    m.finish()
    status = m.owner.get_status()
    assert status['head']['slot'] == 'T1B' and status['head']['source'] == 'purge'
    assert status['head_saved'] is True
    assert on_disk(tmp_path) == dict(status['head'], schema=1)
    # Written after the bin exit and the CFS bookkeeping, never before.
    assert m.commits() == [('commit', 'T1B', 'T1B')]


def test_record_is_written_only_when_the_slot_changes(tmp_path, monkeypatch):
    writes = []
    real = module.write_head
    monkeypatch.setattr(module, 'write_head',
                        lambda path, record: (writes.append(record and record['slot']),
                                              real(path, record))[1])
    m = machine(tmp_path)
    watch(m, 3)
    assert writes == ['T1B'] and m.owner.head['source'] == 'route'
    m.referenced()
    m.finish()
    watch(m, 3)
    assert writes == ['T1B'] and m.owner.head['source'] == 'route'
    m.data['box']['T1']['filament'] = 'None'
    m.data['box']['T2']['filament'] = 'A'
    watch(m)
    assert writes == ['T1B', 'T2A'] and on_disk(tmp_path)['slot'] == 'T2A'


def test_restart_with_filament_in_the_head_starts_without_the_operator(tmp_path):
    first = machine(tmp_path)
    first.referenced()
    first.finish()
    first.fire('klippy:shutdown')
    # Klipper restarted: the CFS route and every attribution in memory are lost.
    m = machine(tmp_path, head=True, route=None)
    assert m.owner.adopted is None and m.owner.attempt is None
    assert m.owner.get_status()['head']['slot'] == 'T1B' and m.events == []
    gcmd = Gcmd()
    m.referenced()
    m.owner.material(gcmd)
    assert m.owner.phase == 'complete' and m.owner.run['branch'] == 'recover'
    assert gcmd.messages == ['K1 Control: filament T1B pret (recover)']
    assert ('stock_T',) not in m.events and len(rec.e_moves(m)) == 7
    assert m.commits() == [('commit', 'T1B', 'T1B')]
    assert 'KCTRL_RETAINED_ADOPT' not in '\n'.join(m.commands())
    assert m.owner.get_status()['retained_attribution'] is None


def test_record_never_replaces_the_buffer_proof(tmp_path):
    first = machine(tmp_path)
    first.referenced()
    first.finish()
    m = machine(tmp_path, head=True, route=None)
    m.buffer = 1        # another filament, or a blockage: the CFS buffer stays full
    m.referenced()
    with pytest.raises(RuntimeError, match='buffer_consumption_unconfirmed'): m.finish()
    assert m.commits() == [] and m.owner.phase == 'failed'
    assert m.data['extruder']['target'] == m.data['heater_bed']['target'] == 0


def test_restart_without_a_record_still_refuses(tmp_path):
    m = machine(tmp_path, head=True, route=None)
    with pytest.raises(RuntimeError, match='retained_identity_or_continuity_unproven'): m.plan()
    assert m.events == [] and on_disk(tmp_path) is None


def test_record_of_another_slot_refuses_and_names_both(tmp_path):
    module.write_head(str(head_file(tmp_path)), {'slot': 'T1A', 'source': 'purge', 'saved': 1.})
    m = machine(tmp_path, head=True, route=None)
    with pytest.raises(RuntimeError, match='retained_head_holds_T1A_not_T1B'): m.plan()
    assert m.owner.phase == 'failed' and m.events == []
    assert on_disk(tmp_path)['slot'] == 'T1A'


def test_cut_segment_is_never_attributed_by_the_record(tmp_path):
    module.write_head(str(head_file(tmp_path)), {'slot': 'T1B', 'source': 'purge', 'saved': 1.})
    m = machine(tmp_path, head=True, route=None)
    sensor(m, 'filament_sensor', False)
    with pytest.raises(RuntimeError, match='retained_identity_or_continuity_unproven'): m.plan()
    assert m.events == []


def test_live_route_outranks_the_record(tmp_path):
    module.write_head(str(head_file(tmp_path)), {'slot': 'T1A', 'source': 'purge', 'saved': 1.})
    m = machine(tmp_path, head=True, route='T1B')
    m.referenced()
    assert m.owner.run['branch'] == 'keep'
    watch(m)
    assert on_disk(tmp_path)['slot'] == 'T1B' and m.owner.head['source'] == 'route'


def test_empty_head_drops_the_record_only_when_seen_twice(tmp_path):
    module.write_head(str(head_file(tmp_path)), {'slot': 'T1B', 'source': 'purge', 'saved': 1.})
    m = machine(tmp_path, head=False, route=None)
    watch(m)
    assert on_disk(tmp_path)['slot'] == 'T1B'
    sensor(m, 'filament_sensor_2', True)        # one false reading, not two
    watch(m)
    sensor(m, 'filament_sensor_2', False)
    watch(m)
    assert on_disk(tmp_path)['slot'] == 'T1B' and m.owner.head_empty == 1
    watch(m)
    assert on_disk(tmp_path) is None and m.owner.get_status()['head'] is None
    watch(m, 3)
    assert m.events == []       # the watch reads, it never commands


def test_unreadable_sensors_or_cfs_keep_what_is_known(tmp_path):
    m = machine(tmp_path)
    watch(m)
    sensor(m, 'filament_sensor_2', None)
    watch(m, 3)
    sensor(m, 'filament_sensor_2', True)
    m.data['box']['state'] = 'disconnect'
    watch(m, 3)
    m.data['box'].update(state='connect')
    m.data['box']['T2']['filament'] = 'A'       # two routes: ambiguous
    watch(m, 3)
    assert on_disk(tmp_path)['slot'] == 'T1B' and m.owner.head_saved is True


@pytest.mark.parametrize('name,event', [
    ('BOX_CUT_MATERIAL', 'official_cut'), ('BOX_RETRUDE_MATERIAL', 'official_retract'),
    ('BOX_QUIT_MATERIAL', 'official_unload')])
def test_cut_or_rewind_drops_the_record_before_the_stock_runs(tmp_path, name, event):
    m = machine(tmp_path)
    watch(m)
    seen = []
    stock = m.owner.originals[name]
    m.owner.originals[name] = lambda gcmd: (seen.append(on_disk(tmp_path)), watch(m), stock(gcmd))
    m.ready_gcode_handlers[name](Gcmd())
    assert seen == [None] and m.events == [(event,)]
    # The CFS still shows the old route, the head its cut segment: no proof.
    watch(m, 3)
    assert on_disk(tmp_path) is None and m.owner.severed is True and m.owner.moving == 0
    # Seen empty, then loaded again on a live route: proven anew.
    sensor(m, 'filament_sensor_2', False)
    watch(m, 2)
    sensor(m, 'filament_sensor_2', True)
    watch(m)
    assert on_disk(tmp_path)['slot'] == 'T1B' and m.owner.severed is False


def test_manual_load_records_only_a_continuous_filament_on_a_live_route(tmp_path):
    m = machine(tmp_path, head=False, route=None)

    def load(result_head, result_route):
        def stock(gcmd):
            watch(m)        # a read during the load never concludes
            sensor(m, 'filament_sensor_2', result_head)
            if result_route:
                m.data['box']['T1']['filament'] = result_route[2]
        m.owner.originals['BOX_EXTRUDE_MATERIAL'] = stock
        m.ready_gcode_handlers['BOX_EXTRUDE_MATERIAL'](Gcmd())

    load(False, None)
    assert on_disk(tmp_path) is None and m.owner.severed is True
    load(True, None)
    assert on_disk(tmp_path) is None
    load(True, 'T1C')
    assert on_disk(tmp_path)['slot'] == 'T1C' and m.owner.head['source'] == 'load'
    assert m.owner.severed is False and m.owner.moving == 0


def test_stock_change_drops_the_record_first_and_records_what_it_engaged(tmp_path):
    m = machine(tmp_path, head=True, route='T1A')
    watch(m)
    assert on_disk(tmp_path)['slot'] == 'T1A'
    seen = []

    def stock(gcmd):
        seen.append(on_disk(tmp_path))
        watch(m)
        m.data['box']['T1']['filament'] = 'B'

    m.change.run_stock('T0', {'physical': 'T1B'}, stock, Gcmd())
    assert seen == [None]
    assert on_disk(tmp_path)['slot'] == 'T1B' and m.owner.head['source'] == 'stock'
    assert m.owner.attempt is None and m.owner.moving == 0


def test_failed_stock_change_still_showing_the_old_route_records_nothing(tmp_path):
    m = machine(tmp_path, head=True, route='T1A')
    watch(m)

    def stock(gcmd):
        raise RuntimeError('stock change failed')

    with pytest.raises(RuntimeError, match='stock change failed'):
        m.change.run_stock('T0', {'physical': 'T1B'}, stock, Gcmd())
    watch(m, 3)
    assert on_disk(tmp_path) is None and m.owner.get_status()['head'] is None
    assert m.owner.severed is True and m.owner.moving == 0


def test_failed_first_insertion_survives_the_restart(tmp_path):
    """15 November: stopped start, Klipper restarted, the next start was refused."""
    first, _, error = stopped_in_bin(tmp_path)
    assert 'firmware_reported_error' in error
    assert first.owner.attempt == {'slot': 'T1B', 'has_head': True}
    assert on_disk(tmp_path)['slot'] == 'T1B' and on_disk(tmp_path)['source'] == 'attempt'
    m = machine(tmp_path, head=True, route=None)
    m.referenced()
    m.finish()
    assert m.owner.phase == 'complete' and m.owner.run['branch'] == 'recover'
    assert ('stock_T',) not in m.events and m.commits() == [('commit', 'T1B', 'T1B')]


def test_insertion_attributed_to_another_slot_is_not_recorded(tmp_path):
    m = machine(tmp_path, head=False, route=None, failure='lines')
    m.extra_lines = ['!! not json']
    m.after_stock = lambda: setattr(m.action, 'extrude_tnn', 'T1A')
    m.referenced()
    with pytest.raises(RuntimeError): m.finish()
    assert m.owner.attempt is None and on_disk(tmp_path) is None


def test_operator_attribution_survives_the_restart(tmp_path):
    first = machine(tmp_path, head=True, route=None)
    first.data['print_stats']['state'] = 'error'
    first.owner.adopt(Gcmd(SLOT='T1B'))
    assert first.events == [] and on_disk(tmp_path)['source'] == 'operator'
    m = machine(tmp_path, head=True, route=None)
    m.referenced()
    assert m.owner.run['branch'] == 'recover' and m.owner.adopted is None


def test_disk_failure_never_stops_a_start_and_is_retried(tmp_path, monkeypatch):
    real = module.write_head

    def broken(path, record):
        raise OSError('read-only file system')

    monkeypatch.setattr(module, 'write_head', broken)
    m = machine(tmp_path)
    m.referenced()
    m.finish()
    status = m.owner.get_status()
    assert m.owner.phase == 'complete' and status['head']['slot'] == 'T1B'
    assert status['head_saved'] is False and on_disk(tmp_path) is None
    watch(m)
    assert m.owner.head_saved is False
    monkeypatch.setattr(module, 'write_head', real)
    watch(m)
    assert m.owner.head_saved is True and on_disk(tmp_path)['slot'] == 'T1B'


def test_failed_removal_is_retried_too(tmp_path, monkeypatch):
    m = machine(tmp_path)
    watch(m)
    real = module.write_head
    monkeypatch.setattr(module, 'write_head',
                        lambda path, record: (_ for _ in ()).throw(OSError('busy')))
    m.ready_gcode_handlers['BOX_CUT_MATERIAL'](Gcmd())
    assert m.owner.head is None and m.owner.head_saved is False
    assert on_disk(tmp_path)['slot'] == 'T1B'
    monkeypatch.setattr(module, 'write_head', real)
    watch(m)
    assert m.owner.head_saved is True and on_disk(tmp_path) is None


def test_watch_survives_any_failure_and_keeps_its_period(tmp_path, monkeypatch):
    m = machine(tmp_path)
    monkeypatch.setattr(m.owner, '_observe', lambda: 1 / 0)
    watch(m, 2)
    assert m.watch[1] == 1. + module.WATCH_FIRST and m.timers == []


def test_shutdown_keeps_the_record_and_forgets_the_rest(tmp_path):
    m = machine(tmp_path, head=True, route=None)
    m.data['print_stats']['state'] = 'error'
    m.owner.adopt(Gcmd(SLOT='T1B'))
    m.fire('klippy:shutdown')
    assert m.owner.adopted is None and m.owner.down is True
    assert m.owner.get_status()['head']['slot'] == 'T1B' and on_disk(tmp_path)['slot'] == 'T1B'


def test_disabled_module_never_reads_or_watches(tmp_path):
    module.write_head(str(head_file(tmp_path)), {'slot': 'T1B', 'source': 'purge', 'saved': 1.})
    m = base.Machine(tmp_path, enabled=False)
    assert m.owner.get_status()['head'] is None and not hasattr(m, 'watch')
    assert m.timers == [] and m.events == []


def test_ready_twice_registers_one_watch(tmp_path):
    m = machine(tmp_path)
    first = m.watch
    m.owner._ready()
    assert m.watch is first and m.timers == []


def test_watch_concludes_nothing_while_an_operation_runs(tmp_path):
    m = machine(tmp_path)
    watch(m)

    def stock(gcmd):
        # Mid-operation readings: empty twice, then present on the shown route.
        sensor(m, 'filament_sensor_2', False)
        watch(m, 2)
        assert m.owner.severed is True and m.owner.head_empty == 0
        sensor(m, 'filament_sensor_2', True)
        watch(m, 2)
        assert on_disk(tmp_path) is None

    m.owner.originals['BOX_RETRUDE_MATERIAL'] = stock
    m.ready_gcode_handlers['BOX_RETRUDE_MATERIAL'](Gcmd())
    watch(m, 2)
    assert on_disk(tmp_path) is None and m.owner.severed is True and m.owner.moving == 0


# --- the exit from the bin --------------------------------------------------

def test_start_stopped_in_the_bin_leaves_it_at_constant_height(tmp_path):
    m, gcmd, error = stopped_in_bin(tmp_path)
    assert error == 'K1 Control: depart interrompu (firmware_reported_error)'
    assert gcmd.messages == [MESSAGE]
    assert m.owner.get_status()['rest'] == 'out_of_bin' and m.owner.phase == 'failed'
    assert m.commands()[-5:] == EXIT
    assert [c for c in m.commands() if c.startswith('G1')] == ['G1 Y273 F15000']
    assert m.position[:3] == pytest.approx([210., 273., 35.0133])
    assert m.envelope.latched is False and m.abs_xyz and m.abs_e
    # Planned from the real position, after the heaters were cut.
    reset = m.events.index(('reset_position',))
    assert m.events.index(('cool',)) < reset < m.events.index(('gcode', 'G1 Y273 F15000'))
    assert m.data['extruder']['target'] == m.data['heater_bed']['target'] == 0
    # The stock pause and the kept CFS error are left exactly as they were.
    assert m.data['pause_resume']['is_paused'] is True and m.sd.must_pause_work is True
    assert m.pause.pause_command_sent is True and m.pause.sd_paused is True
    assert m.action.box_save.last_err == 'box_extrude_err' and m.action.box_save.move_z == 30.14
    assert m.reports == [] and ('record_z', 0) not in m.events and m.timers == []
    assert not any(c.startswith(('G28', 'M112', 'RESUME', 'CLEAR_PAUSE', 'M84'))
                   for c in m.commands())


def test_real_failure_refused_then_exit_keeps_the_bed_where_the_guard_left_it(tmp_path):
    """17:11:14 replayed with an unprovable recovery: bed never raised, head out."""
    m = rec.Machine(tmp_path)
    m.after_stock = lambda: setattr(m.objects['box'], 'inside_error', True)
    m.referenced()
    with pytest.raises(RuntimeError, match='cfs_error_still_processing'): m.finish()
    assert m.owner.get_status()['rest'] == 'out_of_bin'
    assert m.position[:3] == pytest.approx([210., 273., 35.0133])
    assert not any(c.startswith('G1 Z') for c in m.commands()) and rec.e_moves(m) == []


def test_failed_purge_restores_its_state_then_exits_once(tmp_path):
    m = machine(tmp_path)
    m.buffer = 1
    m.referenced()
    with pytest.raises(RuntimeError, match='buffer_consumption_unconfirmed'): m.finish()
    commands = m.commands()
    assert commands[-6:] == ['RESTORE_GCODE_STATE NAME=KCTRL_RETAINED_START MOVE=0'] + EXIT
    assert commands.count('G1 Y273 F15000') == 1 and len(rec.e_moves(m)) == 7
    assert m.position[:3] == pytest.approx([185.5, 273., 35.1])
    assert m.owner.get_status()['rest'] == 'out_of_bin' and m.abs_xyz and m.abs_e
    assert m.data['extruder']['target'] == 0 and m.commits() == []


@pytest.mark.parametrize('change,rest', [
    (lambda m: m.data['toolhead'].update(homed_axes=''), 'not_referenced'),
    (lambda m: m.data['toolhead'].update(homed_axes='xy'), 'not_referenced'),
    (lambda m: m.position.__setitem__(2, 29.99), 'bed_too_high'),
    (lambda m: m.position.__setitem__(2, float('nan')), 'bed_too_high'),
    (lambda m: m.position.__setitem__(2, None), 'bed_too_high'),
    (lambda m: m.envelope.commit(False), 'not_in_bin'),
    (lambda m: m.objects.pop('gcode_move'), 'unavailable'),
    (lambda m: m.objects.update(gcode_move=SimpleNamespace()), 'unavailable'),
    (lambda m: m.objects.pop('kctrl_purge_guard'), 'unavailable'),
    (lambda m: m.fire('klippy:shutdown'), 'skipped'),
    (lambda m: m.fire('klippy:disconnect'), 'skipped'),
])
def test_exit_is_skipped_whenever_it_is_not_proven_harmless(tmp_path, change, rest):
    m, gcmd, error = stopped_in_bin(tmp_path, change)
    assert error.startswith('K1 Control: depart interrompu (') and m.owner.phase == 'failed'
    assert m.owner.get_status()['rest'] == rest and gcmd.messages == []
    assert not any(c.startswith(('G1', 'G0', 'G28', 'SAVE_GCODE_STATE NAME=KCTRL_START_REST'))
                   for c in m.commands())
    assert ('reset_position',) not in m.events
    assert m.data['extruder']['target'] == m.data['heater_bed']['target'] == 0


def test_bed_at_exactly_thirty_millimetres_may_leave(tmp_path):
    m, _, _ = stopped_in_bin(tmp_path, lambda m: m.position.__setitem__(2, 30.))
    assert m.owner.get_status()['rest'] == 'out_of_bin' and m.position[2] == 30.


def test_exit_refused_by_the_bin_guard_never_hides_the_cause(tmp_path):
    def refuse(m):
        def check(start, end, homed=True):
            raise policy.StartRefused('purge_bed_clearance_below_30mm')
        m.envelope.check = check

    m, gcmd, error = stopped_in_bin(tmp_path, refuse)
    assert error == 'K1 Control: depart interrompu (firmware_reported_error)'
    assert m.owner.failure == 'firmware_reported_error'
    assert m.owner.get_status()['rest'] == 'refused' and gcmd.messages == []
    assert m.commands()[-1] == EXIT[-1] and m.abs_xyz and m.abs_e
    assert m.position[:3] == pytest.approx([210., 291.5, 35.0133]) and m.envelope.latched is True


def test_exit_is_not_announced_while_the_guard_still_holds_the_latch(tmp_path):
    m, gcmd, _ = stopped_in_bin(tmp_path, lambda m: setattr(m.envelope, 'commit', lambda latch: None))
    assert m.owner.get_status()['rest'] == 'exit_not_confirmed' and gcmd.messages == []
    assert m.commands().count('G1 Y273 F15000') == 1


def test_start_stopped_outside_the_bin_does_not_move(tmp_path):
    m = machine(tmp_path)
    m.current_success = False
    m.referenced()
    m.events.clear()
    with pytest.raises(RuntimeError, match='extruder_current_readback_failed'): m.finish()
    assert m.owner.get_status()['rest'] == 'not_in_bin'
    assert not any(c.startswith('G1') for c in m.commands())
    assert ('reset_position',) not in m.events


def test_watchdog_alone_never_moves(tmp_path):
    m, _, _ = stopped_in_bin(tmp_path, lambda m: m.envelope.commit(False))
    m.envelope.commit(True)
    m.owner.phase = 'material'
    m.events.clear()
    assert m.owner._watchdog(m.now) == m.NEVER
    assert m.events == [('cool',)] and m.owner.get_status()['rest'] == 'not_in_bin'


def test_refusal_before_material_does_not_move(tmp_path):
    m = machine(tmp_path)
    m.envelope.commit(True)
    m.position[:3] = [210., 291.5, 40.]
    m.plan()
    with pytest.raises(RuntimeError, match='fresh_reference_missing'):
        m.owner.reference_ready(Gcmd())
    assert m.owner.get_status()['rest'] is None and m.commands() == []


def test_next_plan_and_a_good_start_clear_the_exit_status(tmp_path):
    m, _, _ = stopped_in_bin(tmp_path)
    assert m.owner.get_status()['rest'] == 'out_of_bin'
    m.data['pause_resume']['is_paused'] = False
    m.data['kctrl_end']['job_epoch'] += 1
    m.plan()
    assert m.owner.get_status()['rest'] is None
    m.ready_gcode_handlers['ACCURATE_G28'](Gcmd())
    m.owner.reference_ready(Gcmd())
    m.finish()
    assert m.owner.phase == 'complete' and m.owner.run['branch'] == 'recover'
    assert m.owner.get_status()['rest'] is None
