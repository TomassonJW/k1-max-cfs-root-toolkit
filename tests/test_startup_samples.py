import importlib.util
import json
from pathlib import Path
import pytest

PATH = Path(__file__).resolve().parents[1] / 'scripts/audit-en-direct/startup_samples.py'
spec = importlib.util.spec_from_file_location('startup_samples', PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def payload():
    objects = {name: {field: 0 for field in fields} for name, fields in mod.OBJECTS.items() if fields}
    objects['filament_switch_sensor filament_sensor_2'] = {'filament_detected': False, 'enabled': False}
    objects['box'] = {'enable': 1, 'state': 'connect', 't_command': '', 'sn': 'SECRET',
                      'T1': {'state': 'connect', 'filament': 'B', 'uuid': 'SECRET'},
                      'T2': {'state': 'connect', 'filament': 'None'}}
    return {'result': {'eventtime': 12.5, 'status': objects}}


def test_recorder_keeps_false_sensor_and_excludes_box_identifiers():
    result = mod.clean_response(payload())
    assert result['objects']['filament_switch_sensor filament_sensor_2'] == {'filament_detected': False, 'enabled': False}
    assert result['objects']['box']['T1']['filament'] == 'B'
    assert 'SECRET' not in json.dumps(result)


@pytest.mark.parametrize('missing_object', list(mod.OBJECTS))
def test_absent_object_is_not_silently_treated_as_zero(missing_object):
    data = payload()
    del data['result']['status'][missing_object]
    with pytest.raises(ValueError, match='missing objects'):
        mod.clean_response(data)


def test_missing_current_cannot_be_interpreted_as_disabled_driver():
    data = payload()
    del data['result']['status']['tmc2209 extruder']['run_current']
    with pytest.raises(ValueError, match='missing fields'):
        mod.clean_response(data)


@pytest.mark.parametrize('url', ['http://user:password@printer', 'http://printer/printer/gcode/script', 'file:///tmp/state', 'http://printer?script=M112'])
def test_only_plain_api_base_url_accepted(url, tmp_path):
    with pytest.raises(ValueError, match='base URL'):
        mod.collect(url, tmp_path / 'samples.jsonl', 1)
    assert not list(tmp_path.iterdir())


def test_existing_capture_is_never_overwritten(tmp_path):
    target = tmp_path / 'samples.jsonl'
    target.write_text('proof')
    with pytest.raises(FileExistsError):
        mod.collect('http://printer', target, 1)
    assert target.read_text() == 'proof'


def test_one_sample_is_get_only(monkeypatch, tmp_path):
    seen = []
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, limit): return json.dumps(payload()).encode()
    def get(request, timeout):
        seen.append((request.get_method(), request.full_url, request.data, timeout))
        return Response()
    clock = iter([0, 0, 0, 0.1, 0.1, 0.1, 2])
    monkeypatch.setattr(mod.time, 'monotonic', lambda: next(clock))
    monkeypatch.setattr(mod.time, 'sleep', lambda seconds: None)
    monkeypatch.setattr(mod.urllib.request, 'urlopen', get)
    assert mod.collect('http://printer:4409', tmp_path / 'samples.jsonl', 1) == 1
    assert seen == [('GET', 'http://printer:4409' + mod.QUERY, None, 5)]


def test_unsupported_enable_field_is_explicitly_unknown():
    data = payload()
    data['result']['status']['stepper_enable']['steppers'] = None
    result = mod.clean_response(data)
    assert result['objects']['stepper_enable']['steppers'] is None
    assert result['unavailable_fields'] == ['stepper_enable.steppers']
