import importlib.util
from pathlib import Path
import pytest

PATH = Path(__file__).resolve().parents[1] / 'packages/k1-control-v1/startup-grip-observer-v2/stop_policy.py'
SPEC = importlib.util.spec_from_file_location('stop_policy', PATH)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def state():
    return {
        'webhooks': {'state': 'ready'},
        'extruder': {'target': 0}, 'heater_bed': {'target': 0},
        'kctrl_end': {'phase': 'idle', 'pending': False},
        'print_stats': {'state': 'paused'}, 'pause_resume': {'is_paused': True},
    }


def motion():
    return {'toolhead': {'print_time': 20., 'estimated_print_time': 21.},
            'motion_report': {'live_extruder_velocity': 0.}}


def test_v3_manual_shutdown_does_not_request_second_emergency():
    s = state(); s['webhooks']['state'] = 'shutdown'
    assert m.action(s, motion(), fault='printer_error') == 'already_shutdown'


def test_human_wait_at_hot_pause_only_requests_heaters_off():
    s = state(); s['extruder']['target'] = 200
    assert m.action(s, motion(), pause_expired=True) == 'turn_off_heaters'


def test_cold_settled_human_wait_does_not_emergency_stop():
    assert m.action(state(), motion(), pause_expired=True) == 'cold_hold'


def test_real_camera_hazard_is_not_masked_by_cold_pause():
    assert m.action(state(), motion(), fault='camera_hazard', pause_expired=True) == 'emergency_stop'


def test_end_already_failed_and_stopped_does_not_get_m112():
    s = state(); s['kctrl_end']['phase'] = 'failed'
    assert m.action(s, motion(), fault='firmware_error') == 'controlled_failure'


@pytest.mark.parametrize('case', ['missing_motion', 'queue_pending', 'extruding', 'heat_active', 'owner_pending', 'nan'])
def test_unsettled_fault_still_requires_stop(case):
    s = state(); s['kctrl_end']['phase'] = 'failed'; o = motion()
    if case == 'missing_motion': o = {}
    if case == 'queue_pending': o['toolhead']['print_time'] = 30
    if case == 'extruding': o['motion_report']['live_extruder_velocity'] = 2
    if case == 'heat_active': s['extruder']['target'] = 200
    if case == 'owner_pending': s['kctrl_end']['pending'] = True
    if case == 'nan': o['toolhead']['print_time'] = float('nan')
    assert m.action(s, o, fault='firmware_error') == 'emergency_stop'


def test_independent_observers_share_one_stop_receipt(tmp_path):
    calls = []
    assert m.StopOnce(tmp_path).request(lambda: calls.append(1), 'camera') == 'sent'
    assert m.StopOnce(tmp_path).request(lambda: calls.append(2), 'shutdown_seen') == 'already_requested'
    assert calls == [1]


def test_timeout_does_not_allow_repeating_uncertain_stop(tmp_path):
    def timeout(): raise TimeoutError('response uncertain')
    with pytest.raises(TimeoutError): m.StopOnce(tmp_path).request(timeout, 'fault')
    assert m.StopOnce(tmp_path).request(lambda: pytest.fail('duplicate effect'), 'retry') == 'already_requested'


def test_integrated_hot_human_wait_cools_and_verifies_without_m112(tmp_path):
    calls=[]; s=state(); s['extruder']['target']=200
    owner=m.TrialSupervisor(tmp_path, read=lambda:(state(),motion()),
        turn_off_heaters=lambda:calls.append('heaters_off'), stop=lambda:calls.append('M112'))
    assert owner.poll(s,motion(),pause_expired=True)=='cold_hold'
    assert calls==['heaters_off']


def test_integrated_camera_stop_followed_by_shutdown_only_sends_once(tmp_path):
    calls=[]; s=state()
    owner=m.TrialSupervisor(tmp_path, read=lambda:(s,motion()),
        turn_off_heaters=lambda:pytest.fail('unexpected heat command'), stop=lambda:calls.append('M112'))
    assert owner.poll(s,motion(),fault='camera_hazard')=='sent'
    s['webhooks']['state']='shutdown'
    assert owner.poll(s,motion(),fault='printer_error')=='already_shutdown'
    assert calls==['M112']


def test_heater_http_success_without_effect_is_not_cold_hold(tmp_path):
    calls=[]; s=state(); s['extruder']['target']=200
    owner=m.TrialSupervisor(tmp_path, read=lambda:(s,motion()),
        turn_off_heaters=lambda:calls.append('heaters_off'), stop=lambda:calls.append('M112'))
    assert owner.poll(s,motion(),pause_expired=True)=='sent'
    assert calls==['heaters_off','M112']


def test_uncertain_heater_off_does_not_repeat_it(tmp_path):
    calls=[]; s=state(); s['extruder']['target']=200
    def off():
        calls.append('heaters_off')
        raise TimeoutError('uncertain')
    owner=m.TrialSupervisor(tmp_path,read=lambda:pytest.fail('unreachable'),
        turn_off_heaters=off,stop=lambda:calls.append('M112'))
    assert owner.poll(s,motion(),pause_expired=True)=='sent'
    assert calls==['heaters_off','M112']
