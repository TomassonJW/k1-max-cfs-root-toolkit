"""Frozen payloads and failure-injected two-file deployment, no K1 access."""
import base64
import importlib.util
import json
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
PACKAGE=ROOT/'packages/k1-control-v1/end-separated-v1'

def load(name):
    spec=importlib.util.spec_from_file_location(name,PACKAGE/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def test_manifest_is_reproducible_and_exactly_two_files():
    m=json.loads((PACKAGE/'manifest.json').read_text(encoding='utf-8'))
    assert m==load('build_manifest').build()
    assert len(m['files'])==2 and len(m['before'])==22
    assert m['enabled'] is True and m['physical_validation'] is False
    assert all(f['destination'] in m['before'] for f in m['files'])


def test_installer_has_only_software_gcode():
    source=(PACKAGE/'remote_install.py').read_text(encoding='utf-8-sig')
    assert "command = 'BED_MESH_CLEAR'" in source
    assert 'MOVE=0' in source
    for forbidden in ('G28','G1 ','G0 ','M104','M109','M140','M190','BOX_RETRUDE','/printer/print/start'):
        assert forbidden not in source


def fixture(tmp_path,monkeypatch):
    m=load('remote_install')
    paths=[tmp_path/'kctrl_end.py',tmp_path/'end.cfg']
    for p in paths:p.write_bytes(b'before:'+p.name.encode())
    before={str(p):m.digest(p) for p in paths}
    payloads={p.name:b'after:'+p.name.encode() for p in paths}
    files=[{'name':p.name,'destination':str(p),'sha256':m.hashlib.sha256(payloads[p.name]).hexdigest()} for p in paths]
    request={'mode':'install','manifest':{'name':'cfs-separated-end-v1','files':files,'before':before},'payloads':{n:base64.b64encode(v).decode() for n,v in payloads.items()}}
    monkeypatch.setattr(m,'DESTINATIONS',tuple(str(p) for p in paths))
    monkeypatch.setattr(m,'BACKUP',tmp_path/'backup')
    pid=tmp_path/'pid';pid.write_text('new')
    original_path=m.Path
    monkeypatch.setattr(m,'Path',lambda p:pid if p=='/var/run/klippy.pid' else original_path(p))
    state={'kctrl_end':{'enabled':False,'pending':False,'revision':'separated-end-v1'},'bed_mesh':{'profile_name':''},'gcode_move':{'homing_origin':[0,0,0,0]},'extruder':{'target':0},'heater_bed':{'target':0},'toolhead':{'homed_axes':''}}
    log=[]
    monkeypatch.setattr(m,'state',lambda:state)
    monkeypatch.setattr(m,'cold',lambda s:None)
    monkeypatch.setattr(m,'stop',lambda:log.append('stop') or 'old')
    monkeypatch.setattr(m,'service',lambda a:log.append(a))
    monkeypatch.setattr(m,'wait_ready',lambda enabled:state)
    monkeypatch.setattr(m,'restore_coordinates',lambda s:log.append('restore_MOVE_0'))
    return m,request,paths,log


def test_install_backups_exact_before_bytes_and_checks_after(tmp_path,monkeypatch):
    m,request,paths,log=fixture(tmp_path,monkeypatch)
    result=m.run(request)
    assert result['status']=='INSTALLED_COLD_OK'
    assert log==['stop','start','restore_MOVE_0']
    for p in paths:
        assert p.read_bytes().startswith(b'after:')
        assert (m.BACKUP/(p.name+'.before')).read_bytes()==b'before:'+p.name.encode()


@pytest.mark.parametrize('failure',['file_drift','payload_drift','busy','backup_exists'])
def test_preflight_failure_leaves_files_and_service_untouched(tmp_path,monkeypatch,failure):
    m,request,paths,log=fixture(tmp_path,monkeypatch)
    if failure=='file_drift':paths[0].write_bytes(b'foreign change')
    if failure=='payload_drift':request['payloads'][paths[0].name]=base64.b64encode(b'wrong').decode()
    if failure=='busy':monkeypatch.setattr(m,'cold',lambda s:(_ for _ in ()).throw(AssertionError('busy')))
    if failure=='backup_exists':m.BACKUP.mkdir()
    before=[p.read_bytes() for p in paths]
    with pytest.raises(AssertionError):m.run(request)
    assert [p.read_bytes() for p in paths]==before
    assert not log


def test_failed_cold_start_restores_both_originals(tmp_path,monkeypatch):
    m,request,paths,log=fixture(tmp_path,monkeypatch)
    before=[p.read_bytes() for p in paths]
    def ready(enabled):
        if enabled:raise RuntimeError('injected_start_failure')
        return m.state()
    monkeypatch.setattr(m,'wait_ready',ready)
    assert m.run(request)['status']=='INSTALL_FAILED_ROLLED_BACK'
    assert [p.read_bytes() for p in paths]==before
    assert log==['stop','start','stop','start','restore_MOVE_0']


def test_explicit_rollback_restores_exact_files(tmp_path,monkeypatch):
    m,request,paths,log=fixture(tmp_path,monkeypatch)
    before=[p.read_bytes() for p in paths]
    assert m.run(request)['status']=='INSTALLED_COLD_OK'
    request['mode']='rollback'
    assert m.run(request)['status']=='ROLLED_BACK'
    assert [p.read_bytes() for p in paths]==before
