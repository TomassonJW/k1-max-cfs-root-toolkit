"""Read-only inputs for retained start; no printer effects or network access."""

import os
import re

from .kctrl_start_policy import StartRefused, finite, purge_feed


def file_identity(path):
    info = os.stat(path)
    return (os.path.realpath(path), info.st_size, info.st_mtime_ns)


def file_motion(path, index):
    """Read the bounded Orca footer, selecting the actual filament index."""
    before = file_identity(path)
    with open(path, 'rb') as source:
        source.seek(max(0, before[1] - 262144))
        text = source.read(262144).decode('utf-8', errors='replace')
    if file_identity(path) != before:
        raise StartRefused('job_file_changed')
    values = {}
    required = ('filament_max_volumetric_speed', 'filament_diameter',
                'travel_acceleration')
    for line in text.splitlines():
        match = re.fullmatch(r';\s*([a-z_]+)\s*=\s*(.*?)\s*', line)
        if match and match[1] in required:
            if match[1] in values:
                raise StartRefused('duplicate_motion_metadata_' + match[1])
            values[match[1]] = match[2]
    try:
        flow = float(re.split(r'[,;]', values[required[0]])[index])
        diameter = float(re.split(r'[,;]', values[required[1]])[index])
        accel = float(values[required[2]])
    except (ValueError, KeyError, IndexError):
        raise StartRefused('file_motion_metadata_missing_or_invalid')
    if not finite(accel) or not 0 < accel <= 100000:
        raise StartRefused('file_travel_acceleration_invalid')
    feed = purge_feed(flow, diameter)
    # A complete purge must fit the bounded material-operation window.
    if feed < 1.:
        raise StartRefused('purge_flow_requires_separate_recipe')
    return {'identity': before, 'feed': feed, 'travel_acceleration': accel,
            'volumetric_limit': flow, 'diameter': diameter}
