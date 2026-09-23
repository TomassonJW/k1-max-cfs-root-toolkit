import importlib.util
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / 'packages/k1-control-v1/retained-start-v1/kctrl_start_policy.py'
SPEC = importlib.util.spec_from_file_location('retained_start_policy', PATH)
policy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(policy)


def decide(**changes):
    args = dict(head=True, upstream=True, requested='T1B', engaged='T1B',
                attempted=None, homed='xyz', attempt_has_head=False,
                attempt_is_current=False)
    args.update(changes)
    return policy.decide_start(**args)


def test_present_identified_filament_is_kept():
    assert decide() == 'keep'


def test_current_failed_load_enters_provisional_recovery_not_reload():
    assert decide(engaged=None, attempted='T1B', attempt_has_head=True,
                  attempt_is_current=True) == 'recover'


@pytest.mark.parametrize('changes,reason', [
    ({'engaged': None}, 'retained_route_unproven'),
    ({'homed': ''}, 'retained_geometry_lost'),
    ({'homed': 'xy'}, 'retained_geometry_lost'),
    ({'upstream': False}, 'retained_cut_segment_not_continuous'),
    ({'head': None}, 'filament_sensor_unknown'),
    ({'head': 1}, 'filament_sensor_unknown'),
    ({'end_pending': True}, 'end_still_active'),
    ({'engaged': None, 'attempted': 'T1B', 'attempt_has_head': True}, 'retained_route_unproven'),
    ({'engaged': None, 'attempted': 'T1A', 'attempt_has_head': True, 'attempt_is_current': True}, 'retained_route_unproven'),
    ({'head': False, 'upstream': False}, 'partial_filament_requires_recovery'),
])
def test_no_unsafe_inference_from_presence_or_job_choice(changes, reason):
    with pytest.raises(policy.StartRefused, match=reason):
        decide(**changes)


def test_true_empty_head_can_be_referenced_then_loaded():
    assert decide(head=False, upstream=False, engaged=None, homed='') == 'empty'
    assert decide(head=False, upstream=True, engaged=None, homed='') == 'empty'


def test_different_known_spool_requires_change_without_reprobing():
    assert decide(requested='T2D') == 'change'


@pytest.mark.parametrize('start,end', [
    ([185.5, 280., 0.], [185.5, 305., 0.]),
    ([185.5, 305., 35.], [185.5, 305., 29.99]),
    ([150., 305., 20.], [250., 305., 20.]),
    ([185.5, 290., 35.], [185.5, 310., 20.]),
    ([175., 300., 29.99], [175., 300., 29.99]),
])
def test_guard_catches_entry_lowering_crossing_and_boundaries(start, end):
    guard = policy.PurgeEnvelope()
    with pytest.raises(policy.StartRefused, match='clearance'):
        guard.check(start, end)
    assert guard.latched is False


def test_cannot_raise_bed_during_diagonal_exit():
    guard = policy.PurgeEnvelope()
    guard.commit(guard.check([185.5, 273., 35.], [185.5, 305., 35.]))
    with pytest.raises(policy.StartRefused, match='clearance'):
        guard.check([185.5, 305., 35.], [210., 273., 0.3])
    assert guard.latched
    guard.commit(guard.check([185.5, 305., 35.], [210., 273., 35.]))
    assert not guard.latched
    assert guard.check([210., 273., 35.], [210., 273., 0.3]) is False


def test_small_backward_lateral_moves_do_not_release_latch():
    guard = policy.PurgeEnvelope()
    guard.latched = True
    assert guard.check([185.5, 305., 35.], [240., 291.5, 35.]) is True


def test_normal_printing_rear_rows_are_not_bin_entry():
    assert policy.PurgeEnvelope().check([170., 295., .3], [230., 295., .3]) is False


@pytest.mark.parametrize('bad', [None, float('nan'), float('inf')])
def test_unknown_position_never_passes(bad):
    with pytest.raises(policy.StartRefused, match='position_unknown'):
        policy.PurgeEnvelope().check([185.5, 273., 35.], [185.5, 305., bad])


def test_unknown_references_cannot_enter_bin():
    with pytest.raises(policy.StartRefused, match='geometry_unknown'):
        policy.PurgeEnvelope().check([185.5, 273., 35.], [185.5, 305., 35.], homed=False)


def test_current_restore_compares_to_config_with_driver_quantisation():
    assert policy.current_is_ready(.562, .55)
    assert not policy.current_is_ready(.281, .55)
    assert not policy.current_is_ready(.55, float('nan'))


@pytest.mark.parametrize('initial', [[296.5, 153.75, 50.11], [185.5, 305., 50.], [120., 90., 2.]])
def test_entire_retained_choreography_passes_envelope_without_raising_low_bed(initial):
    moves = policy.retained_purge_moves(initial)
    assert moves[0][2] == max(initial[2], 35.)
    moves += policy.release_moves(moves[-1][2])
    guard = policy.PurgeEnvelope()
    position = initial
    for target in moves:
        guard.commit(guard.check(position, target))
        position = target
    assert not guard.latched
    assert position[1] == 273.
