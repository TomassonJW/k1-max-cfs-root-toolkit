"""Local console observer; does not change firmware error handling or motors."""

# The exact unsupported request was received on a separate webhooks client.
# It remained queued during START and failed before the diagnostic PAUSE.
# Allow only this observed no-handler response; never install a firmware stub.
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

    def feed(self, entries):
        for event in sorted(entries, key=lambda e: e['time']):
            key = (event['time'], event['message'])
            if event['time'] <= self.after or key in self.seen:
                continue
            self.seen.add(key)
            line = event['message'].removeprefix('// ').strip()
            if line == 'full':
                self.full += 1
                if self.full >= self.limit:
                    return 'buffer_still_full_before_stock_retry'
            elif line in ('middle', 'empty'):
                self.full = 0
            if event['message'] == KNOWN_EXTERNAL_FAN_ERROR:
                self.known_fan_responses.append(event['time'])
            elif event['message'].startswith('!!'):
                return 'firmware_error'
        return None
