"""A repeated active tool must not turn a Z hop into a temperature change."""
import pytest

from test_retained_start_integration import Machine, Gcmd


def loaded(tmp_path):
    m = Machine(tmp_path)
    m.referenced()
    m.finish()
    m.position[2] = 2.36
    m.data['extruder']['target'] = 195.
    m.events.clear()
    return m


@pytest.mark.parametrize('target,z', [(195., 2.36), (200., 50.), (215., 12.)])
def test_completed_start_and_later_duplicate_preserve_explicit_target(tmp_path, target, z):
    m = loaded(tmp_path)
    m.now += 1000  # The completed material timeout must not expire a print.
    m.position[2] = z
    m.data['extruder']['target'] = target
    m.data['filament_switch_sensor filament_sensor_2']['enabled'] = True
    m.data['tmc2209 extruder']['run_current'] = .280763
    m.data['tmc2209 extruder']['hold_current'] = .280763
    command = Gcmd()
    m.change.change(0, m.stock, command)
    assert m.data['extruder']['target'] == target
    assert m.data['tmc2209 extruder']['run_current'] == .55
    assert m.data['filament_switch_sensor filament_sensor_2']['enabled'] is True
    assert not any(e[0] in ('selection', 'stock_T', 'mode', 'buffer', 'commit', 'move') for e in m.events)
    assert not any(line.startswith(('M104', 'M109', 'BOX_', 'SET_FILAMENT')) for line in m.commands())
    assert 'consigne du fichier conservee' in command.messages[0]


@pytest.mark.parametrize('case', [
    'different_tool', 'different_mapping', 'new_job', 'changed_file', 'new_epoch',
    'paused', 'end_pending', 'end_failed', 'no_head', 'no_upstream', 'different_route',
    'different_cache', 'different_last_slot', 'unsuccessful_last', 'different_mode',
    'lost_reference', 'lost_axes', 'cold', 'no_target', 'inactive_job', 'resolve_failure',
])
def test_no_shortcut_without_complete_same_tool_proof(tmp_path, case):
    m = loaded(tmp_path)
    index = 0
    if case == 'different_tool': index = 1
    elif case == 'different_mapping': m.change.resolve = lambda _: {'physical': 'T2A'}
    elif case == 'new_job': m.data['print_stats']['filename'] = 'other.gcode'
    elif case == 'changed_file': m.path.write_text('changed')
    elif case == 'new_epoch': m.data['kctrl_end']['job_epoch'] += 1
    elif case == 'paused': m.data['pause_resume']['is_paused'] = True
    elif case == 'end_pending': m.data['kctrl_end']['pending'] = True
    elif case == 'end_failed': m.data['kctrl_end']['phase'] = 'failed'
    elif case == 'no_head': m.data['filament_switch_sensor filament_sensor_2']['filament_detected'] = False
    elif case == 'no_upstream': m.data['filament_switch_sensor filament_sensor']['filament_detected'] = False
    elif case == 'different_route': m.data['box']['T1']['filament'] = 'A'
    elif case == 'different_cache': m.action.box_save.last_cmd = 'T1A'
    elif case == 'different_last_slot': m.change.last['slot'] = 'T1A'
    elif case == 'unsuccessful_last': m.change.last['outcome'] = 'empty'
    elif case == 'different_mode': m.data['box']['T1']['mode'] = '0'
    elif case == 'lost_reference': m.owner.reference_valid = False
    elif case == 'lost_axes': m.data['toolhead']['homed_axes'] = 'xy'
    elif case == 'cold': m.data['extruder']['can_extrude'] = False
    elif case == 'no_target': m.data['extruder']['target'] = 0.
    elif case == 'inactive_job': m.data['print_stats']['state'] = 'complete'
    elif case == 'resolve_failure':
        def fail(_): raise ValueError('mapping unreadable')
        m.change.resolve = fail
    assert m.change.change(index, m.stock, Gcmd()) == 'original-selection-result'
    assert m.events == [('selection', index)]


def test_true_change_and_its_later_repeat_use_current_active_tool(tmp_path):
    m = loaded(tmp_path)
    assert m.change.change(1, m.stock, Gcmd()) == 'original-selection-result'
    # Successful outcome of the existing change path, now on the second CFS.
    m.change.last = {'tool': 'T1', 'outcome': 'done', 'slot': 'T2A', 'temp': 225.}
    m.action.box_save.last_cmd = 'T2A'
    m.data['box']['T1']['filament'] = 'None'
    m.data['box']['T2'].update(filament='A', mode='2')
    m.data['extruder']['target'] = 223.  # An explicit G-code adjustment survives.
    m.events.clear()
    m.change.change(1, m.stock, Gcmd())
    assert not any(e[0] == 'selection' for e in m.events)
    assert m.data['extruder']['target'] == 223.


def test_current_failure_cools_without_a_stock_retry(tmp_path):
    m = loaded(tmp_path)
    m.current_success = False
    m.data['tmc2209 extruder']['run_current'] = .28
    with pytest.raises(RuntimeError, match='courant extrudeur non retabli'):
        m.change.change(0, m.stock, Gcmd())
    assert m.owner.phase == 'failed' and m.data['extruder']['target'] == 0
    assert not any(e[0] == 'selection' for e in m.events)


def test_failed_registration_restores_both_tool_methods(tmp_path):
    m = Machine(tmp_path, enabled=False)
    before = dict(m.ready_gcode_handlers)
    m.owner.enabled = True
    def fail(_): raise RuntimeError('output handler failed')
    m.register_output_handler = fail
    with pytest.raises(RuntimeError, match='output handler failed'):
        m.owner._ready()
    assert m.ready_gcode_handlers == before and not m.owner.originals
    assert m.change.change == m.selection_wrapper
    assert m.change.run_stock == m.stock_wrapper
