"""Pure retained-start decisions. Presence never proves grip or spool identity."""

import math

SLOTS = tuple('T%d%s' % (unit, slot) for unit in range(1, 5) for slot in 'ABCD')


class StartRefused(ValueError):
    pass


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def decide_start(head, upstream, requested, engaged, attempted, homed,
                 attempt_has_head, attempt_is_current, end_pending=False):
    """Decide before clearing caches, heating, homing, cutting or selecting Tn.

    attempted is an attributable failed insert from this live process, never
    the next job's selection. Recovery remains provisional until feed proof.
    """
    if type(head) is not bool or type(upstream) is not bool:
        raise StartRefused('filament_sensor_unknown')
    if requested not in SLOTS:
        raise StartRefused('requested_route_invalid')
    if end_pending:
        raise StartRefused('end_still_active')
    if engaged is not None and engaged not in SLOTS:
        raise StartRefused('engaged_route_invalid')
    if not head:
        # The other switch was True on the qualified empty-head loading
        # capture of 21 September. It cannot alone forbid the empty branch.
        if engaged:
            raise StartRefused('partial_filament_requires_recovery')
        return 'empty'
    if not upstream:
        raise StartRefused('retained_cut_segment_not_continuous')
    if set(homed) != set('xyz'):
        raise StartRefused('retained_geometry_lost')
    if engaged:
        return 'keep' if engaged == requested else 'change'
    if (attempted == requested and attempt_has_head is True
            and attempt_is_current is True):
        return 'recover'
    raise StartRefused('retained_route_unproven')


def current_is_ready(actual, expected, tolerance=0.035):
    # Read-back against configured current, allowing TMC quantisation.
    return (finite(actual) and finite(expected) and 0.1 <= expected <= 1.5
            and abs(actual - expected) <= tolerance)


def _rectangle_interval(start, end, xmin, xmax, ymin):
    """Liang-Barsky clipping including diagonal crossings and boundary contact."""
    lower, upper = 0.0, 1.0
    for origin, delta, minimum, maximum in (
            (start[0], end[0] - start[0], xmin, xmax),
            (start[1], end[1] - start[1], ymin, float('inf'))):
        if delta == 0:
            if not minimum <= origin <= maximum:
                return None
            continue
        left, right = (minimum - origin) / delta, (maximum - origin) / delta
        if left > right:
            left, right = right, left
        lower, upper = max(lower, left), min(upper, right)
        if lower > upper:
            return None
    return lower, upper


class PurgeEnvelope:
    """Actual coordinates after mesh and offset; sticky until forward exit.

    The caller commits a latch only after the original move accepted it.
    A diagonal exit must keep clearance for its entire duration.
    """
    def __init__(self, minimum_z=30., xmin=175., xmax=220.,
                 rear_y=300., exit_y=280.):
        if (not all(finite(v) for v in (minimum_z, xmin, xmax, rear_y, exit_y))
                or not xmin < xmax or not exit_y < rear_y):
            raise ValueError('invalid_purge_envelope')
        if minimum_z < 30.:
            raise ValueError('purge_clearance_below_canonical_minimum')
        self.minimum_z = minimum_z
        self.xmin, self.xmax = xmin, xmax
        self.rear_y, self.exit_y = rear_y, exit_y
        self.latched = False

    def check(self, start, end, homed=True):
        if len(start) < 3 or len(end) < 3 or not all(finite(x) for x in (*start[:3], *end[:3])):
            raise StartRefused('purge_position_unknown')
        interval = _rectangle_interval(start, end, self.xmin, self.xmax, self.rear_y)
        if not self.latched and interval is None:
            return False
        if not homed:
            raise StartRefused('purge_geometry_unknown')
        a, b = (0., 1.) if self.latched else interval
        dz = end[2] - start[2]
        if min(start[2] + a * dz, start[2] + b * dz) < self.minimum_z:
            raise StartRefused('purge_bed_clearance_below_30mm')
        return end[1] > self.exit_y

    def commit(self, next_latch):
        self.latched = bool(next_latch)


def retained_purge_moves(position, purge_z=35.):
    """Physical coordinates, no homing/cutter, no raising an already low bed."""
    if len(position) < 3 or not all(finite(v) for v in position[:3]):
        raise StartRefused('position_unknown')
    if not finite(purge_z) or purge_z < 35.:
        raise StartRefused('purge_margin_too_small')
    x, y, z = position[:3]
    safe_z = max(z, purge_z)
    return [(x, y, safe_z), (x, 273., safe_z),
            (185.5, 273., safe_z), (185.5, 305., safe_z)]


def release_moves(safe_z):
    if not finite(safe_z) or safe_z < 35.:
        raise StartRefused('purge_margin_too_small')
    # Candidate only, not installed. Retain the XYZ execution guard above.
    # Observed stock axis (docs/79): Y305 <-> Y291.5 at constant purge X.
    # The former lateral brush path is excluded by Thomas, 23 September.
    moves = [(185.5, 291.5, safe_z), (185.5, 305., safe_z)] * 3
    return moves + [(185.5, 273., safe_z)]


def purge_feed(volumetric_limit, diameter=1.75):
    """Filament mm/s, bounded by the file and qualified stock rate of 6 mm/s."""
    if not finite(volumetric_limit) or not 0 < volumetric_limit <= 100:
        raise StartRefused('filament_flow_limit_missing_or_invalid')
    if not finite(diameter) or not 1.5 <= diameter <= 2.0:
        raise StartRefused('filament_diameter_invalid')
    return min(6., volumetric_limit / (math.pi * diameter**2 / 4))
