"""External observer; a buffer limit is not proof of a mechanical jam.

No transport. Caller retains thermal, camera and overall time guards.
"""
KNOWN_EXTERNAL_FAN_ERROR = (
    '!! {"code":"key61, "msg":"Unknown command:SET_HOTEND_FAN", '
    '"values": ["SET_HOTEND_FAN VALUE=1"]}'
)


class GripGuard:
    def __init__(self, after, limit=8):
        self.after = after
        self.limit = limit
        self.full = 0
        self.seen = set()
        self.known_fan_responses = []
        self.phase = 'before_head'

    def feed(self, entries, *, head_detected, route_accepted):
        if type(head_detected) is not bool or type(route_accepted) is not bool:
            raise ValueError('missing_load_phase_evidence')
        accepted = head_detected and route_accepted
        self.phase = ('accepted_route' if accepted else
                      'head_present_route_unconfirmed' if head_detected else 'before_head')
        if accepted:
            self.full = 0
        for event in sorted(entries, key=lambda e: e['time']):
            key = (event['time'], event['message'])
            if event['time'] <= self.after or key in self.seen:
                continue
            self.seen.add(key)
            if event['message'] == KNOWN_EXTERNAL_FAN_ERROR:
                self.known_fan_responses.append(event['time'])
            elif event['message'].startswith('!!'):
                return 'firmware_error'
            line = event['message'].removeprefix('// ').strip()
            if line in ('middle', 'empty'):
                self.full = 0
            elif line == 'full' and not accepted:
                self.full += 1
                if self.full >= self.limit:
                    return ('loading_unconfirmed_buffer_full' if head_detected
                            else 'buffer_full_before_head')
        return None
