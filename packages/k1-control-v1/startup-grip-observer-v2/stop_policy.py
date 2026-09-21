"""Local trial supervision. No printer transport or automatic recovery.

All participating observers must share one stop receipt directory. An
uncertain HTTP response consumes the request too: never repeat an effect.
"""
import json
import math
from pathlib import Path


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def settled_cold(status, objects):
    head = objects.get('toolhead', {})
    motion = objects.get('motion_report', {})
    times = (head.get('print_time'), head.get('estimated_print_time'))
    targets = (status.get('extruder', {}).get('target'),
               status.get('heater_bed', {}).get('target'))
    return (
        status.get('webhooks', {}).get('state') == 'ready'
        and all(_finite(value) and value == 0 for value in targets)
        and status.get('kctrl_end', {}).get('pending') is False
        and all(_finite(value) for value in times)
        and times[0] <= times[1]
        and _finite(motion.get('live_extruder_velocity'))
        and motion['live_extruder_velocity'] == 0
    )


def action(status, objects, *, fault=None, pause_expired=False):
    """Return a decision, never perform it. Caller verifies thermal-off results.

    A positive camera hazard is passed as fault='camera_hazard', including
    during a cold hold. Missing motion evidence never proves a settled state.
    """
    state = status.get('webhooks', {}).get('state')
    if state == 'shutdown':
        return 'already_shutdown'
    if fault == 'camera_hazard':
        return 'emergency_stop'
    end_failed = status.get('kctrl_end', {}).get('phase') == 'failed'
    paused = (status.get('print_stats', {}).get('state') == 'paused'
              and status.get('pause_resume', {}).get('is_paused') is True)
    if end_failed and settled_cold(status, objects):
        return 'controlled_failure'
    if fault or state != 'ready':
        return 'emergency_stop'
    if pause_expired and paused:
        return 'cold_hold' if settled_cold(status, objects) else 'turn_off_heaters'
    return 'observe'


class StopOnce:
    def __init__(self, directory):
        self.receipt = Path(directory) / 'emergency-stop-receipt.json'

    def request(self, send, reason):
        # Exclusive creation arbitrates independent manual and automatic
        # observers. The directory must already exist; fail closed otherwise.
        try:
            stream = self.receipt.open('x', encoding='utf-8')
        except FileExistsError:
            return 'already_requested'
        with stream:
            json.dump({'reason': reason, 'state': 'requested'}, stream)
            stream.flush()
        try:
            send()
        except Exception:
            # Retain the receipt even when delivery is uncertain.
            raise
        return 'sent'


class TrialSupervisor:
    """One owner for automatic checks and explicit camera stop requests.

    Adapters are supplied by the caller. read returns fresh (status, objects);
    turn_off_heaters sends only that command, and stop sends only M112.
    """
    def __init__(self, directory, *, read, turn_off_heaters, stop):
        self.stop_once = StopOnce(directory)
        self.read = read
        self.turn_off_heaters = turn_off_heaters
        self.stop = stop

    def poll(self, status, objects, *, fault=None, pause_expired=False):
        decision = action(status, objects, fault=fault, pause_expired=pause_expired)
        if decision == 'turn_off_heaters':
            try:
                self.turn_off_heaters()
                fresh_status, fresh_objects = self.read()
                decision = action(fresh_status, fresh_objects, pause_expired=True)
            except Exception:
                return self.stop_once.request(self.stop, 'cold_hold_delivery_or_read_uncertain')
            # One heater-off attempt. A response alone does not prove its effect.
            if decision != 'cold_hold':
                if decision == 'already_shutdown':
                    return decision
                return self.stop_once.request(self.stop, 'cold_hold_not_confirmed')
            return decision
        if decision == 'emergency_stop':
            return self.stop_once.request(self.stop, fault or 'unsafe_state')
        return decision
