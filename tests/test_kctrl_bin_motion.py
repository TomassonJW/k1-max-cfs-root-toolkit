"""Exercise the complete stock entry/restore contract against the bin guard.

Fake hardware only. The stock call shapes come from the isolated exact-binary
trace; these tests do not qualify a deployment or a physical release.
"""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT/'packages/k1-control-v1/retained-start-v1'


def load(name):
    spec = importlib.util.spec_from_file_location(name, PACKAGE/(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


policy = load('kctrl_start_policy')
motion = load('kctrl_bin_motion')


class Machine:
    def __init__(self, z=.3, homed='xyz'):
        self.position = [150., 150., z, 0.]
        self.homed = homed
        self.events = []
        self.guard = SimpleNamespace(envelope=policy.PurgeEnvelope())
        self.objects = {'toolhead': self, 'kctrl_purge_guard': self.guard, 'gcode': self}
        self.action = SimpleNamespace(go_to_extrude_pos=self.stock_enter,
                                      z_down=self.stock_down, z_restore=self.stock_restore)
        self.objects['box'] = SimpleNamespace(box_action=self.action)
        self.delta = 0

    def get_printer(self): return self
    def get_reactor(self): return self
    def monotonic(self): return 1.
    def lookup_object(self, key): return self.objects[key]
    def register_event_handler(self, *args): pass
    def get_status(self, t): return {'homed_axes': self.homed}
    def get_position(self): return self.position[:]
    def command_error(self, text): return RuntimeError(text)
    config_error = command_error

    def move(self, *, x=None, y=None, z=None):
        after = self.position[:]
        for index, value in enumerate((x, y, z)):
            if value is not None: after[index] = value
        next_latch = self.guard.envelope.check(self.position, after, homed=self.homed=='xyz')
        self.events.append(('move', tuple(after)))
        self.position = after
        self.guard.envelope.commit(next_latch)

    def stock_down(self, distance=20., absolute=False, wait=False):
        self.events.append(('stock_down', distance, absolute, wait))
        target = max(self.position[2], distance) if absolute else self.position[2]+distance
        self.delta = target-self.position[2]
        self.move(z=target)

    def stock_enter(self):
        self.action.z_down(distance=25., absolute=True, wait=True)
        self.move(y=291.5)
        self.move(x=185.5)
        self.move(y=305.)

    def stock_restore(self):
        self.events.append(('stock_restore', self.position[:]))
        self.move(z=self.position[2]-self.delta)
        self.delta = 0.

    def run_script_from_command(self, script):
        self.events.append(('script', script))
        assert 'G1 Z' not in script and 'G1 E' not in script
        assert 'G28' not in script and 'M112' not in script
        assert 'RESTORE_GCODE_STATE NAME=KCTRL_BIN_EXIT MOVE=0' in script
        self.move(y=273.)


@pytest.mark.parametrize('initial_z', [.3, 12., 50., 300.])
def test_stock_return_height_preserved_and_restore_only_after_exit(initial_z):
    machine = Machine(z=initial_z)
    adapter = motion.KctrlBinMotion(machine)
    adapter._ready()
    machine.action.go_to_extrude_pos()
    assert machine.position[2] == max(35., initial_z)
    assert machine.guard.envelope.latched
    machine.move(y=291.5)
    machine.move(x=210.)
    machine.action.z_restore()
    assert machine.position[2] == pytest.approx(initial_z)
    assert machine.position[1] == 273.
    assert not machine.guard.envelope.latched
    restore = next(event for event in machine.events if event[0]=='stock_restore')
    assert restore[1][1] == 273.


@pytest.mark.parametrize('homed', ['', 'xy', 'z'])
def test_unknown_axes_refuse_before_any_stock_move(homed):
    machine = Machine(homed=homed)
    adapter = motion.KctrlBinMotion(machine)
    adapter._ready()
    with pytest.raises(RuntimeError, match='references XYZ'):
        machine.action.go_to_extrude_pos()
    assert machine.events == []


def test_different_stock_call_shape_stops_before_move():
    machine = Machine()
    machine.action.go_to_extrude_pos = lambda: machine.action.z_down(25.)
    adapter = motion.KctrlBinMotion(machine)
    adapter._ready()
    with pytest.raises(RuntimeError, match='non reconnue'):
        machine.action.go_to_extrude_pos()
    assert machine.events == []
    assert not adapter.entering


def test_non_bin_lowering_unchanged_and_ready_not_double_wrapped():
    machine = Machine(z=50.)
    adapter = motion.KctrlBinMotion(machine)
    adapter._ready()
    original = adapter.originals['z_down']
    adapter._ready()
    assert adapter.originals['z_down'] == original
    machine.action.z_down(distance=2.)
    assert machine.position[2] == 52.
