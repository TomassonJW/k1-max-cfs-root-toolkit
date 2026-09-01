"""Block a print start until a filament switch sensor actually sees material.

This exists because the obvious version does not work. A macro that dwells and
waits blocks correctly when it is called from the gcode queue, and does nothing
at all when it is called from inside another macro - which is the only way it
would ever be used, since it belongs in START_PRINT. Measured on the machine on
2026-09-02:

    _KCTRL_WAIT_HEAD_FILAMENT          (direct)     0.84 s   the dwell happens
    ten of them, flat                  (direct)     8.14 s   ten dwells happen
    the same ten through one macro     (nested)     0.02 s   nothing happens
    the same, then M400 at top level   (nested)     0.02 s   nothing was queued

The last line is the one that settles it: the dwells were never queued, so no
later wait can recover them. A G4/M400 poll inside START_PRINT is a grace
period that does not exist, and it fails silently - the print simply carries on
purging into an empty melt zone, which is exactly the defect being chased.

A command implemented here pauses the reactor itself and does not depend on
where it was called from.
"""


class KctrlWait:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object("gcode")
        self.gcode.register_command(
            "KCTRL_WAIT_FILAMENT", self.cmd_KCTRL_WAIT_FILAMENT,
            desc=self.cmd_KCTRL_WAIT_FILAMENT_help)

    cmd_KCTRL_WAIT_FILAMENT_help = (
        "Hold until a filament switch sensor sees material, or fail")

    def cmd_KCTRL_WAIT_FILAMENT(self, gcmd):
        name = gcmd.get("SENSOR")
        timeout = gcmd.get_float("TIMEOUT", 15.0, minval=0.1, maxval=300.0)
        poll = gcmd.get_float("POLL", 0.2, minval=0.02, maxval=5.0)
        required = gcmd.get_int("REQUIRED", 1, minval=0, maxval=1)
        full = "filament_switch_sensor " + name
        sensor = self.printer.lookup_object(full, None)
        if sensor is None:
            raise gcmd.error("K1 Control: no filament sensor named %s" % name)
        reactor = self.printer.get_reactor()
        started = reactor.monotonic()
        deadline = started + timeout
        while True:
            now = reactor.monotonic()
            # The pin is read every pass, not once at the start: the whole
            # point is to see the CFS arrive, which happens while we wait.
            if sensor.get_status(now).get("filament_detected"):
                waited = now - started
                if waited > poll:
                    gcmd.respond_info(
                        "K1 Control: %s a vu le filament apres %.1f s"
                        % (name, waited))
                return
            if now >= deadline:
                break
            reactor.pause(min(now + poll, deadline))
        message = ("K1 Control: %s n'a toujours pas vu de filament apres %.0f s"
                   % (name, timeout))
        if required:
            # Failing here is the point. Carrying on would purge and then print
            # into an empty head, and the operator would find out on the plate.
            raise gcmd.error(message)
        gcmd.respond_info(message)


def load_config(config):
    return KctrlWait(config)
