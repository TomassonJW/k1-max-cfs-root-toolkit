"""Selection and sign contract of KCTRL_MESH_EDIT.

The operator judges the bed on a printed square and reports corrections by
zone - "the front edge sits 0.01 too far", "the back right corner is 0.025 too
close". These tests pin the two things that turn such a sentence into the right
cells: which points a zone selects, and which way a correction moves the nozzle.

A sign error here does not fail loudly; it doubles the defect it was meant to
remove, on the next print. That is why the direction is tested explicitly.
"""

import importlib.util
import os

import pytest

MODULE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "packages", "k1-control-v1", "mesh-acquisition-v2", "kctrl_mesh.py")


def _load():
    spec = importlib.util.spec_from_file_location("kctrl_mesh_under_test", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Error(Exception):
    pass


class _FakeGcode:
    error = _Error


class _FakeCmd:
    """Minimal stand-in for Klipper's GCodeCommand accessors."""

    _REQUIRED = object()

    def __init__(self, **kwargs):
        self.params = {key.upper(): value for key, value in kwargs.items()}

    def _fetch(self, key, default):
        value = self.params.get(key, default)
        if value is self._REQUIRED:
            raise _Error("missing %s" % key)
        return value

    def get(self, key, default=_REQUIRED):
        return self._fetch(key, default)

    def get_int(self, key, default=_REQUIRED, minval=None, maxval=None):
        value = self._fetch(key, default)
        if value is None:
            return None
        value = int(value)
        if minval is not None and value < minval:
            raise _Error("%s below %s" % (key, minval))
        if maxval is not None and value > maxval:
            raise _Error("%s above %s" % (key, maxval))
        return value

    def get_float(self, key, default=_REQUIRED, minval=None, maxval=None):
        value = self._fetch(key, default)
        return None if value is None else float(value)


@pytest.fixture(scope="module")
def module():
    return _load()


@pytest.fixture(scope="module")
def grid(module):
    """The production grid: 11x11 spanning 5..295 mm on both axes."""
    axis = module.KctrlMesh._axis(5.0, 295.0, 11)
    return axis, axis


@pytest.fixture(scope="module")
def selector(module):
    instance = object.__new__(module.KctrlMesh)
    instance.gcode = _FakeGcode()

    def select(**kwargs):
        xs = module.KctrlMesh._axis(5.0, 295.0, 11)
        ys = module.KctrlMesh._axis(5.0, 295.0, 11)
        cells, label = instance._select(_FakeCmd(**kwargs), 11, 11, xs, ys)
        return [(xs[i], ys[j]) for i, j in cells], label

    return select


@pytest.mark.parametrize("kwargs,count,first", [
    (dict(edge="avant"), 9, (34.0, 5.0)),
    (dict(edge="front"), 9, (34.0, 5.0)),
    (dict(edge="fond"), 9, (34.0, 295.0)),
    (dict(edge="gauche"), 9, (5.0, 34.0)),
    (dict(edge="droite"), 9, (295.0, 34.0)),
    (dict(edge="avant", ring=1), 7, (63.0, 34.0)),
    (dict(edge="droit", ring=1), 7, (266.0, 63.0)),
])
def test_an_edge_selects_its_side_without_the_corners(
        selector, kwargs, count, first):
    cells, _ = selector(**kwargs)
    assert len(cells) == count
    assert cells[0] == first


def test_an_edge_can_include_its_corners_on_request(selector):
    cells, _ = selector(edge="front", with_corners=1)
    assert len(cells) == 11
    assert cells[0] == (5.0, 5.0)
    assert cells[-1] == (295.0, 5.0)


@pytest.mark.parametrize("name,expected", [
    ("avant_gauche", (5.0, 5.0)),
    ("avant_droit", (295.0, 5.0)),
    ("arriere_gauche", (5.0, 295.0)),
    ("arriere_droit", (295.0, 295.0)),
    ("front_left", (5.0, 5.0)),
    ("back_right", (295.0, 295.0)),
])
def test_a_corner_selects_exactly_one_point(selector, name, expected):
    cells, _ = selector(corner=name)
    assert cells == [expected]


def test_a_corner_of_the_inner_ring_moves_inwards(selector):
    assert selector(corner="avant_droit", ring=1)[0] == [(266.0, 34.0)]


def test_a_point_can_be_named_by_index_or_by_position(selector):
    assert selector(col=3, row=4)[0] == [(92.0, 121.0)]
    assert selector(x=270, y=262)[0] == [(266.0, 266.0)]


@pytest.mark.parametrize("kwargs", [
    dict(ring=0),                              # no selection at all
    dict(edge="avant", corner="avant_droit"),  # two selections at once
    dict(edge="nord"),                         # not a side of this bed
    dict(edge="avant", ring=6),                # ring outside an 11x11 grid
    dict(col=11, row=0),                       # index past the last column
    dict(col=3),                               # half a coordinate
    dict(x=400, y=150),                        # position off the plate
    dict(x=150),                               # half a position
])
def test_an_ambiguous_or_impossible_selection_is_refused(selector, kwargs):
    with pytest.raises(_Error):
        selector(**kwargs)


@pytest.mark.parametrize("kwargs,expected", [
    (dict(closer=0.02), -0.02),
    (dict(further=0.025), 0.025),
    (dict(delta=-0.01), -0.01),
    (dict(delta=0.03), 0.03),
    (dict(closer=-0.02), -0.02),   # a sign typed into CLOSER cannot invert it
    (dict(further=-0.02), 0.02),
])
def test_closer_lowers_the_nozzle_and_further_lifts_it(module, kwargs, expected):
    # A positive mesh value lifts the toolhead, so it takes the nozzle away
    # from the plate. CLOSER must therefore be negative, always.
    assert module.KctrlMesh._delta(_FakeCmd(**kwargs)) == pytest.approx(expected)


@pytest.mark.parametrize("kwargs", [
    dict(),
    dict(closer=0.01, further=0.01),
    dict(delta=0.01, closer=0.01),
])
def test_the_correction_must_be_stated_exactly_once(module, kwargs):
    with pytest.raises(ValueError):
        module.KctrlMesh._delta(_FakeCmd(**kwargs))


@pytest.mark.parametrize("ring,expected", [(0, 40), (1, 32)])
def test_eight_commands_cover_a_whole_ring_without_overlap(
        selector, ring, expected):
    # Perimeter of an NxN grid is 4N-4: 40 points on the outer ring of an
    # 11x11, 32 on the first inner one. Edges exclude their corners, so the
    # four edges and the four corners of a ring tile it exactly once.
    covered = []
    for side in ("avant", "fond", "gauche", "droit"):
        covered.extend(selector(edge=side, ring=ring)[0])
    for corner in ("avant_gauche", "avant_droit",
                   "arriere_gauche", "arriere_droit"):
        covered.extend(selector(corner=corner, ring=ring)[0])
    assert len(covered) == expected
    assert len(set(covered)) == expected


def test_one_edit_cannot_exceed_a_tenth_and_a_half(module):
    assert module.MAX_EDIT_DELTA == pytest.approx(0.15)


def test_the_reference_point_is_the_centre_of_the_bed(module):
    # The whole profile is zero at this point (ADR-046) and the editor refuses
    # to touch it; if this moves, that guard has to move with it.
    assert module.REFERENCE_XY == (150.0, 150.0)
