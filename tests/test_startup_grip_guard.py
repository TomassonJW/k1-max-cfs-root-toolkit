import importlib.util
from pathlib import Path
P=Path(__file__).resolve().parents[1]/'packages/k1-control-v1/startup-grip-diagnostic-v1/grip_guard.py'
s=importlib.util.spec_from_file_location('grip_guard',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def event(t,line):return {'time':t,'message':'// '+line}
def test_stop_before_replay_and_ignore_old_events():
 g=m.GripGuard(100)
 assert g.feed([event(i,'full') for i in range(100)]) is None
 assert g.feed([event(101+i,'full') for i in range(7)]) is None
 assert g.feed([event(101+i,'full') for i in range(7)]) is None
 assert g.feed([event(108,'full')])=='buffer_still_full_before_stock_retry'
def test_middle_resets_full_streak():
 g=m.GripGuard(0)
 assert g.feed([event(i+1,'full') for i in range(7)]+[event(8,'middle')]) is None
 assert g.full==0
 assert g.feed([event(9,'full')]) is None
 assert g.full==1
def test_firmware_error_is_not_a_successful_grip():
 assert m.GripGuard(0).feed([{'time':1,'message':'!! key837'}])=='firmware_error'


def test_exact_known_external_fan_response_is_recorded_once():
 g=m.GripGuard(0)
 response={'time':1,'message':m.KNOWN_EXTERNAL_FAN_ERROR}
 assert g.feed([response]) is None
 assert g.feed([response]) is None
 assert g.known_fan_responses==[1]

def test_fan_response_does_not_reset_full_streak_or_hide_error():
 g=m.GripGuard(0)
 assert g.feed([event(i+1,'full') for i in range(7)]) is None
 assert g.feed([{'time':8,'message':m.KNOWN_EXTERNAL_FAN_ERROR}]) is None
 assert g.feed([event(9,'full')])=='buffer_still_full_before_stock_retry'
 assert m.GripGuard(0).feed([
  {'time':1,'message':m.KNOWN_EXTERNAL_FAN_ERROR},
  {'time':2,'message':'!! key837'},
 ])=='firmware_error'

def test_different_fan_errors_and_extra_commands_still_stop():
 for message in (
  m.KNOWN_EXTERNAL_FAN_ERROR.replace('VALUE=1','VALUE=0'),
  m.KNOWN_EXTERNAL_FAN_ERROR+'\nG1 E5',
  '!! hotend fan failure',
  '!! Unknown command:ANYTHING_ELSE',
 ):
  assert m.GripGuard(0).feed([{'time':1,'message':message}])=='firmware_error'
