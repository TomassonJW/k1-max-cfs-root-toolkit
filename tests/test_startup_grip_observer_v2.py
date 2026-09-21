import importlib.util
from pathlib import Path
import pytest

PATH = Path(__file__).resolve().parents[1]/'packages/k1-control-v1/startup-grip-observer-v2/grip_guard.py'
spec = importlib.util.spec_from_file_location('grip_observer_v2', PATH)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def full(count=8):
    return [{'time': i+1, 'message': '// full'} for i in range(count)]


def test_failed_capture_shape_remains_bounded_after_head_arrival():
    guard = m.GripGuard(0)
    assert guard.feed(full(), head_detected=True, route_accepted=False) == 'loading_unconfirmed_buffer_full'
    assert guard.phase == 'head_present_route_unconfirmed'


def test_buffer_alarm_before_head_still_stops():
    assert m.GripGuard(0).feed(full(), head_detected=False, route_accepted=False) == 'buffer_full_before_head'


def test_accepted_route_and_head_do_not_count_as_failed_initial_grip():
    guard = m.GripGuard(0)
    assert guard.feed(full(30), head_detected=True, route_accepted=True) is None
    assert guard.full == 0 and guard.phase == 'accepted_route'


def test_route_alone_does_not_suppress_alarm():
    assert m.GripGuard(0).feed(full(), head_detected=False, route_accepted=True) == 'buffer_full_before_head'


@pytest.mark.parametrize('head,route', [(False,False),(True,False),(True,True)])
def test_firmware_errors_are_never_suppressed_by_phase(head, route):
    assert m.GripGuard(0).feed([{'time':1,'message':'!! key837'}], head_detected=head, route_accepted=route) == 'firmware_error'


def test_reset_on_middle_and_no_double_count():
    guard=m.GripGuard(0)
    events=full(7)
    for _ in range(3):
        assert guard.feed(events, head_detected=True, route_accepted=False) is None
    assert guard.full == 7
    events += [{'time':8,'message':'// middle'},{'time':9,'message':'// full'}]
    assert guard.feed(events, head_detected=True, route_accepted=False) is None
    assert guard.full == 1


def test_preexisting_events_ignored():
    assert m.GripGuard(10).feed(full(), head_detected=False, route_accepted=False) is None


@pytest.mark.parametrize('head,route', [(None,False),(True,None),(1,False),(False,'B')])
def test_incomplete_evidence_rejected(head,route):
    with pytest.raises(ValueError): m.GripGuard(0).feed([],head_detected=head,route_accepted=route)


def test_exact_known_external_fan_response_is_recorded_only():
    guard=m.GripGuard(0)
    assert guard.feed([{'time':1,'message':m.KNOWN_EXTERNAL_FAN_ERROR}],head_detected=True,route_accepted=False) is None
    assert guard.known_fan_responses == [1]
