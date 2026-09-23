"""Offline safety requirements for the candidate; no printer transport."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('retained_motion_policy', ROOT/'packages/k1-control-v1/retained-start-v1/kctrl_start_policy.py')
policy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(policy)


@pytest.mark.parametrize('homed', ['', 'xy', 'z'])
def test_retained_material_execution_requires_xyz(homed):
    with pytest.raises(policy.StartRefused, match='geometry_lost'):
        policy.decide_start(True, True, 'T1B', 'T1B', None, homed, False, False)


def test_release_stays_on_bin_axis_and_leaves_before_raise():
    envelope = policy.PurgeEnvelope()
    current = (185.5, 305., 60.)
    envelope.commit(envelope.check(current, current))
    for point in policy.release_moves(60.):
        assert point[0] == 185.5
        assert point[2] == 60.
        envelope.commit(envelope.check(current, point))
        current = point
    assert current == (185.5, 273., 60.)
    assert not envelope.latched
    assert envelope.check(current, (185.5, 273., 1.)) is False


def test_flow_uses_diameter_and_file_limit_without_exceeding_qualified_speed():
    assert policy.purge_feed(23., 1.75) == 6.
    assert policy.purge_feed(24., 1.75) == 6.
    assert policy.purge_feed(10., 1.75) == pytest.approx(4.15751688)
    for value in (0, -1, float('nan'), None):
        with pytest.raises(policy.StartRefused):
            policy.purge_feed(value, 1.75)
