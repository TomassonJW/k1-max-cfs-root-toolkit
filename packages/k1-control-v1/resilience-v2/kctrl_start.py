"""Start coordinator, enabled explicitly by the reviewed configuration.

PLAN only records identity. REFERENCE_READY requires an observed successful
ACCURATE_G28 after that plan. MATERIAL then owns the one conditional step:
normal stock T for an empty/different filament, or a retained purge without T.
The installed end-of-job owner and the existing prime sequence are unchanged.

start-load-recovery-v1 (ADR-079): when that stock T fails with only its
known "extrude error" (key837 on this very slot) and/or the stock pause it
triggers, while the filament is proven at the head and attributed to the
requested slot, the same start undoes that pause, clears the stock lift
record and finishes with the retained purge. At most once per start; any
other evidence still fails closed with heaters off.

resilience-v1 (ADR-080, document 109), two exits from states which used to
need a console or a Klipper restart:

- The slot proven at the head is kept on disk. A Klipper restart, a power cut
  or an emergency stop loses the CFS route and every in-memory attribution;
  the record then attributes the retained filament to its slot, and the
  retained purge still has to prove that the CFS buffer is consumed. The
  record follows a live CFS route, a completed purge, an attributable failed
  insertion or the operator. It is dropped as soon as a stock cut, rewind or
  load begins, and when the head is seen empty twice in a row.
- A start stopped with the head inside the bin leaves it by the purge's own
  exit, Y273 at constant height, only with referenced axes and a bed at least
  30 mm down. Stock pause flags and the kept CFS error are not touched.

resilience-v2 (ADR-081, documents 106 and 110): a paused print whose filament
is proven at the head resumes by the retained purge instead of the stock
reload. Two states used to need a console:

- a spool relay whose stock load failed with its filament at the head (15
  November: CFS at rest, pause current, stale route, runout alarm off, head
  latched at the bin park);
- a CFS left at rest by a stock error routine while the filament never left
  the head (12 November): the stock resume then prints with nothing fed.

The relay first gets the extruder run current back, read back. Once every
stock step of a failed relay has returned, and again each time RESUME is
asked, the same decision runs: head out of the bin at constant height, proofs
before any effect, PRINT mode acknowledged, 20 mm pushes with the CFS buffer
read consumed, route written, then the stock RESUME without its flush or its
reload. Unproven, the print stays paused, head out of the bin, targets and
pause current put back, with one sentence. Anything this module cannot
decide is left to the stock RESUME, untouched. Nothing here raises inside the
reload envelope (ADR-072). `RESUME STOCK=1` is the console way round it.
"""

import json
import logging
import os
import re
import sys
import time

from .kctrl_end import EndRefused, live_route
from .kctrl_start_context import file_identity, file_motion
from .kctrl_start_policy import SLOTS, StartRefused, current_is_ready, decide_start, finite

REVISION = 'resilience-v2'
# K1 Control state directory, outside /tmp: survives reboots and restarts.
HEAD_STATE_FILE = '/usr/data/k1-control-v1/state/kctrl_head.json'
HEAD_SCHEMA = 1
# The sensors settle after klippy:ready; an empty head counts only when seen
# twice, one period apart.
WATCH_FIRST, WATCH_PERIOD, EMPTY_READS = 10., 5., 2
# Canonical bin clearance (ADR-071): never move in the bin above it.
REST_MINIMUM_Z = 30.
# The stock T of 12 November 2026 at 17:11:13 reported exactly this code with
# [address, slot letter] before pausing (document 108).
TOLERATED_CODES = ('key837',)
# Our own bin guard refusing the stock pause's descent into the bin.
GUARD_REFUSAL = 'K1 Control: mouvement refuse pour proteger le bac'
MAX_STOCK_LINES = 32
# A failed relay names its slot with one of these (key836 on 15 November 2026
# at 13:42:27 with [1, "B"], key837 on 12 November), document 110.
RELAY_CODES = ('key836', 'key837')
# The 20 mm pushes of 15 November were sent at F150.
RESUME_FEED = 2.5
# Pulled back before the wipes, primed again at the stop point (same day).
RESUME_PRIME = 0.8
# Bounded waits of the automatic attempt: the CFS error routine, then quiet
# for longer than the 4 s period of the error repeated on 15 November.
ERROR_WAIT, SETTLE = 60., 5.
RESUME_TIMEOUT = 300.
# The bin guard cuts the bed with the nozzle: its way back is waited for.
BED_WAIT = 900.
# Backward search of the file for its last fan commands.
FAN_CHUNK, FAN_SCAN = 1 << 18, 1 << 24
FAN_LINE = re.compile(br'^[ \t]*(M10[67]\b[^\r\n;]*)', re.M | re.I)
STOCK_NAMES = ('RESUME', 'BOX_CHECK_MATERIAL_REFILL', 'BOX_RESUME_EXTRUDE')
# Status field -> command word, for what a stock routine may leave changed.
LIMIT_WORDS = {'max_velocity': 'VELOCITY', 'max_accel': 'ACCEL',
               'max_accel_to_decel': 'ACCEL_TO_DECEL',
               'square_corner_velocity': 'SQUARE_CORNER_VELOCITY'}
ADVANCE_WORDS = {'pressure_advance': 'ADVANCE', 'smooth_time': 'SMOOTH_TIME'}
# What the refusal of a resume means for the person in front of the printer.
RESUME_HINTS = {
    'buffer_consumption_unconfirmed': 'le filament ne vient pas de la bobine',
    'buffer_empty_or_unknown': 'le filament ne vient pas de la bobine',
    'buffer_ack_missing': 'le CFS ne repond pas',
    'cfs_print_ack_missing': 'le CFS ne repond pas',
    'cfs_state_ack_missing': 'le CFS ne repond pas',
    'cfs_unit_disconnected': 'le CFS ne repond pas',
    'cfs_print_mode_lost': 'le CFS ne reste pas en mode impression',
    'cfs_error_still_processing': 'le CFS signale encore une erreur',
    'cfs_error_not_cleared': 'le CFS signale encore une erreur',
    'firmware_reported_error': 'la machine a signale une erreur',
    'purge_temperature_changed': 'la buse ne tient pas sa temperature',
    'head_not_loaded': 'le filament a quitte la tete',
    'retained_filament_changed': 'le filament a bouge pendant la purge',
    'bin_exit_bed_too_high': 'plateau trop haut pour sortir du bac',
    'bin_exit_not_confirmed': 'sortie du bac non confirmee',
    'purge_margin_missing': 'plateau trop haut pour le bac',
    'axes_not_referenced': 'axes non references',
    'resume_timeout': 'purge trop longue',
    'resume_temperature_unknown': 'temperature de reprise inconnue',
    'print_no_longer_paused': 'impression plus en pause',
    'resume_invalidated': 'reprise interrompue',
    'resume_command_failed': 'une commande a echoue',
    'stock_resume_not_effective': 'la machine est restee en pause',
    'end_still_active': 'fin de tache en cours',
    'print_cancelled': 'impression annulee',
    'printer_disconnected': 'machine arretee',
    'retained_bookkeeping_not_confirmed': 'route du CFS non confirmee',
    'cfs_route_unknown': 'route du CFS illisible',
    'cfs_routes_ambiguous': 'deux routes au CFS',
    'cfs_not_ready': 'le CFS ne repond pas',
    'cfs_unit_missing': 'le CFS ne repond pas',
    'cfs_record_unknown': 'memoire du CFS illisible',
    'extruder_current_readback_failed': 'courant extrudeur non retabli',
    'extruder_current_changed': 'courant extrudeur modifie',
    'filament_sensor_unknown': 'capteur de filament illisible',
}


def classify_stock_errors(lines, slot):
    """Split the '!!' lines of one stock load into tolerated codes and others.

    A line is tolerated only if it is a parseable key837 naming the requested
    CFS address and slot letter, or our bin guard refusal. Anything else,
    unparseable or naming another slot, is returned in `others`.
    """
    codes, others = [], []
    for raw in lines:
        text = str(raw).strip()
        body = text[2:].strip() if text.startswith('!!') else text
        if body.startswith(GUARD_REFUSAL):
            codes.append('bin_guard')
            continue
        try:
            data = json.loads(body)
        except ValueError:
            others.append(text)
            continue
        values = data.get('values') if isinstance(data, dict) else None
        if (isinstance(data, dict) and data.get('code') in TOLERATED_CODES
                and isinstance(values, list) and len(values) == 2
                and type(values[0]) is int and values[0] == int(slot[1])
                and values[1] == slot[2]):
            codes.append(data['code'])
        else:
            others.append(text)
    return codes, others


def read_head(path):
    """The head record kept on disk, or None. Never raises, never guesses."""
    try:
        with open(path, 'r') as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as error:
        logging.warning('kctrl_start: head record unreadable (%s)', error)
        return None
    if (not isinstance(data, dict) or data.get('schema') != HEAD_SCHEMA
            or data.get('slot') not in SLOTS):
        logging.warning('kctrl_start: head record ignored, unknown content')
        return None
    saved = data.get('saved')
    return {'slot': data['slot'], 'source': str(data.get('source', ''))[:32],
            'saved': saved if finite(saved) else None}


def write_head(path, record):
    """Replace the record atomically; None removes it. Raises OSError."""
    if record is None:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        return
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    temporary = path + '.tmp'
    with open(temporary, 'w') as handle:
        json.dump(dict(record, schema=HEAD_SCHEMA), handle, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    try:
        # Make the rename itself survive a power cut where the platform can.
        descriptor = os.open(folder or '.', os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError:
        pass


def relay_slot(lines, target, head_before, head, extrude_tnn):
    """The slot a failed relay left at the head, or None when not provable.

    Only a head seen empty when the relay began and loaded when it ended can
    be attributed: nothing but the relay's own load reached it. The slot is
    the relay's target and/or the one its key836/key837 lines name; two
    different names, or a firmware load record naming another slot, prove
    nothing.
    """
    if head is not True or head_before is not False or lines is None:
        return None
    candidates = set()
    for raw in lines:
        text = str(raw).strip()
        body = text[2:].strip() if text.startswith('!!') else text
        try:
            data = json.loads(body)
        except ValueError:
            continue
        values = data.get('values') if isinstance(data, dict) else None
        if (isinstance(data, dict) and data.get('code') in RELAY_CODES
                and isinstance(values, list) and len(values) == 2
                and type(values[0]) is int and isinstance(values[1], str)):
            candidates.add('T%d%s' % (values[0], values[1]))
    if target in SLOTS:
        candidates.add(target)
    if len(candidates) != 1:
        return None
    slot = candidates.pop()
    if slot not in SLOTS or (extrude_tnn in SLOTS and extrude_tnn != slot):
        return None
    return slot


def fan_command(line, fans):
    """One file line as {fan index: 0..255}, the way the stock macros read it.

    M106: fan P when it exists, else fan 0; S defaults to 255. M107: fan P
    when it exists, fan 0 for an unknown P, fans 0 and 2 without P. None for
    any other line. ValueError when a fan line cannot be followed.
    """
    words = line.split(';', 1)[0].upper().split()
    if not words or words[0] not in ('M106', 'M107'):
        return None
    params = {word[0]: float(word[1:]) for word in words[1:]}
    index = params.get('P')
    if index is not None:
        if index != int(index) or index < 0:
            raise ValueError(line)
        index = int(index)
    if words[0] == 'M107':
        if index is None:
            return {fan: 0 for fan in (0, 2) if fan < fans}
        return {index if index < fans else 0: 0}
    speed = params.get('S', 255.)
    if speed != speed:
        raise ValueError(line)
    fan = index if index is not None and index < fans else 0
    return {fan: int(round(min(255., max(0., speed))))}


def file_fans(path, position, fans=3, pause=None, chunk=FAN_CHUNK, limit=FAN_SCAN):
    """Fan speeds the file had asked for at `position`: {fan index: 0..255}.

    Read backwards from the stop point, the latest command of each fan wins.
    A fan the file never commanded within `limit` bytes is left out. None
    when the file or one of its fan lines cannot be read: the caller then
    leaves the fans as they are. `pause` is called between chunks.
    """
    found = {}
    try:
        with open(path, 'rb') as handle:
            end = int(position)
            floor = max(0, end - limit)
            tail = b''
            while end > floor and len(found) < fans:
                start = max(floor, end - chunk)
                handle.seek(start)
                data = handle.read(end - start) + tail
                tail = b''
                if start > 0:
                    # The first piece may be a line cut by this chunk.
                    cut = data.find(b'\n')
                    tail, data = (data, b'') if cut < 0 else (data[:cut], data[cut + 1:])
                for raw in reversed(FAN_LINE.findall(data)):
                    command = fan_command(raw.decode('ascii', 'replace'), fans)
                    for index, value in (command or {}).items():
                        found.setdefault(index, value)
                end = start
                if pause is not None:
                    pause()
    except (OSError, ValueError, TypeError, IndexError, OverflowError) as error:
        logging.warning('kctrl_start: fans of the file not read (%s)', error)
        return None
    return found


class KctrlStart:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object('gcode')
        self.enabled = config.getboolean('enabled', False)
        self.boxes = config.getint('boxes', 2, minval=1, maxval=4)
        self.timeout = config.getfloat('material_timeout', 240., minval=60., maxval=300.)
        self.recovery_timeout = config.getfloat('recovery_timeout', 180., minval=60., maxval=300.)
        self.head_file = config.get('head_state_file', HEAD_STATE_FILE)
        # What is proven at the head: {'slot', 'source', 'saved'} or None.
        # Memory is the truth of this process; the disk copy follows it.
        self.head = None
        self.head_saved = True
        self.head_empty = 0
        self.head_timer = None
        # A stock cut, rewind or load began: a route still shown by the CFS
        # no longer proves a continuous filament until a load proves it.
        self.severed = False
        self.moving = 0
        self.down = False
        self.rest = None
        self.stock_running = False
        self.stock_lines = []
        self.watchdog = None
        self.recovery = None
        self.originals = {}
        self.run = None
        self.attempt = None
        self.adopted = None
        self.reference = 0
        self.reference_valid = False
        self.reference_running = False
        self.phase = 'idle' if self.enabled else 'disabled'
        self.failure = ''
        self.command_error = ''
        # resilience-v2. relay: what a failed stock reload left, or None.
        # resume_run: the purge of a resume while it runs. resume_hooks: the
        # stock handlers this module stands in front of, empty when that part
        # is not installed. printing: limits and pressure advance last seen
        # while the file was really printing.
        self.relay = None
        self.in_reload = 0
        self.in_refill = 0
        # envelope: inside any T1A..T4D reload. in_resume: inside a stock
        # RESUME this module let through.
        self.envelope = 0
        self.in_resume = 0
        self.reload_lines = []
        self.errors_seen = 0
        self.resume_hooks = {}
        self.resume_failure = ''
        self.resume_run = None
        self.resume_last = None
        self.resuming = False
        self.flushed = False
        self.printing = None
        for name, handler in (
                ('KCTRL_START_PLAN', self.plan),
                ('KCTRL_START_REFERENCE_READY', self.reference_ready),
                ('KCTRL_START_MATERIAL', self.material),
                ('KCTRL_RETAINED_ADOPT', self.adopt)):
            self.gcode.register_command(name, handler)
        self.printer.register_event_handler('klippy:ready', self._ready)
        self.printer.register_event_handler('stepper_enable:motor_off', self._lose_reference)
        self.printer.register_event_handler('klippy:shutdown', self._disconnect)
        self.printer.register_event_handler('klippy:disconnect', self._disconnect)
        self.printer.register_event_handler('gcode:cancel', self._cancel)

    def _status(self, name):
        value = self.printer.lookup_object(name).get_status(self.reactor.monotonic())
        if not isinstance(value, dict):
            raise StartRefused('status_unknown_' + name)
        return value

    def _ready(self):
        if not self.enabled or self.originals:
            return
        for name in ('toolhead', 'heaters', 'extruder', 'heater_bed', 'pause_resume',
                     'print_stats', 'configfile', 'tmc2209 extruder', 'kctrl_end',
                     'kctrl_tool_change', 'kctrl_slot_map', 'kctrl_purge_guard',
                     'kctrl_bin_motion', 'filament_switch_sensor filament_sensor',
                     'filament_switch_sensor filament_sensor_2'):
            self.printer.lookup_object(name)
        self.toolhead = self.printer.lookup_object('toolhead')
        self.action = self.printer.lookup_object('box').box_action
        self.change = self.printer.lookup_object('kctrl_tool_change')
        for name in ('communication_set_box_mode', 'communication_get_buffer_state',
                     'send_data', 'update_filament_pos'):
            if not callable(getattr(self.action, name, None)):
                raise self.printer.config_error('kctrl_start: missing ' + name)
        handlers = self.gcode.ready_gcode_handlers
        names = ('ACCURATE_G28', 'BOX_QUIT_MATERIAL', 'BOX_EXTRUDE_MATERIAL',
                 'BOX_CUT_MATERIAL', 'BOX_RETRUDE_MATERIAL')
        if not all(callable(handlers.get(name)) for name in names):
            raise self.printer.config_error('kctrl_start: stock handlers missing')
        originals = {name: handlers[name] for name in names}
        originals['run_stock'] = self.change.run_stock
        originals['change'] = self.change.change
        replaced = []
        try:
            for name in names:
                self.gcode.register_command(name, None)
                replaced.append(name)
                handler = self._reference if name == 'ACCURATE_G28' else self._manual_effect(name)
                self.gcode.register_command(name, handler)
            self.change.run_stock = self._stock
            self.change.change = self._selection
            self.originals = originals
            self.gcode.register_output_handler(self._output)
        except Exception:
            for name in replaced:
                self.gcode.register_command(name, None)
                self.gcode.register_command(name, originals[name])
            self.change.run_stock = originals['run_stock']
            self.change.change = originals['change']
            self.originals = {}
            raise
        self.head = read_head(self.head_file)
        self.head_saved = True
        if self.head:
            logging.info('kctrl_start: head record %s (%s) read from disk',
                         self.head['slot'], self.head['source'])
        if self.head_timer is None:
            self.head_timer = self.reactor.register_timer(
                self._watch, self.reactor.monotonic() + WATCH_FIRST)
        try:
            self._ready_resume()
        except Exception as error:
            # The start and the head record stay installed without it.
            self.resume_failure = str(error) or type(error).__name__
            logging.exception('kctrl_start: relay and resume part not installed')

    # --- head record (ADR-080) ----------------------------------------------

    def _save(self):
        try:
            write_head(self.head_file, self.head)
            self.head_saved = True
        except Exception:
            # Never a reason to stop a start: the watch retries.
            self.head_saved = False
            logging.exception('kctrl_start: head record not saved')

    def _remember(self, slot, source):
        if slot not in SLOTS:
            return
        self.severed = False
        self.head_empty = 0
        if self.head and self.head['slot'] == slot:
            return
        self.head = {'slot': slot, 'source': source, 'saved': time.time()}
        logging.info('kctrl_start: head record %s (%s)', slot, source)
        self._save()

    def _forget(self, reason):
        if self.head is None:
            return
        logging.info('kctrl_start: head record %s dropped (%s)', self.head['slot'], reason)
        self.head = None
        self._save()

    def _sever(self, reason):
        self.severed = True
        self._forget(reason)

    def _quiet_route(self):
        try:
            return self._route()
        except Exception:
            return None

    def _loaded(self, source):
        """After a load: remember only a continuous filament on a live route."""
        try:
            head, upstream = self._sensors()
        except Exception:
            return
        route = self._quiet_route()
        if head and upstream and route:
            self._remember(route, source)

    def _observe(self):
        try:
            head, upstream = self._sensors()
            route = self._route()
        except Exception:
            return      # unreadable now: keep what is known
        if not head:
            self.head_empty += 1
            if self.head_empty >= EMPTY_READS:
                self.severed = False
                self._forget('head_empty')
            return
        self.head_empty = 0
        if upstream and route and not self.severed:
            self._remember(route, 'route')

    def _watch(self, eventtime):
        try:
            if not self.head_saved:
                self._save()
            if not self.moving:
                self._observe()
                self._notice()
        except Exception:
            logging.exception('kctrl_start: head watch')
        return eventtime + WATCH_PERIOD

    def _notice(self):
        """Limits, pressure advance and bed target of the file while it prints.

        A stock load or error routine may leave its own values behind; a
        resume by purge puts these back. Never read during a pause, a start,
        a stock command or a resume.
        """
        try:
            job = self._status('print_stats')
            if (job.get('state') != 'printing' or not job.get('filename')
                    or self.phase in ('planned', 'referenced', 'material')
                    or self.in_reload or self.in_refill or self.envelope
                    or self.stock_running or self.resume_run is not None
                    or self._status('pause_resume').get('is_paused') is not False):
                return
            self.relay = None        # really printing again: a relay note is over
            limits, nozzle = self._status('toolhead'), self._status('extruder')
            self.printing = {
                'filename': job['filename'],
                'limits': {key: limits.get(key) for key in LIMIT_WORDS},
                'advance': {key: nozzle.get(key) for key in ADVANCE_WORDS},
                'bed': self._status('heater_bed').get('target')}
        except Exception:
            return      # unreadable now: keep what is known

    def _manual_effect(self, name):
        def call(gcmd):
            # A manual removal/insertion breaks the provenance of a failed
            # insertion even if it later leaves the same sensor levels.
            self.attempt = self.adopted = None
            self.relay = None
            self._sever(name.lower())
            self.moving += 1
            try:
                return self.originals[name](gcmd)
            finally:
                self.moving -= 1
                if name == 'BOX_EXTRUDE_MATERIAL':
                    self._loaded('load')
        return call

    def _reference(self, gcmd):
        self.reference_valid = False
        if self.phase != 'planned':
            # A manual calibration outside this start keeps its own behavior.
            # It cannot satisfy a later start's required fresh reference.
            return self.originals['ACCURATE_G28'](gcmd)
        self.reference_running = True
        try:
            self.originals['ACCURATE_G28'](gcmd)
            self.toolhead.wait_moves()
            if self.command_error:
                raise StartRefused(self.command_error)
            self._xyz()
            self.reference += 1
            self.reference_valid = True
        finally:
            self.reference_running = False

    def _lose_reference(self, *args):
        self.reference_valid = False

    def _disconnect(self, *args):
        self._lose_reference()
        # In-memory evidence dies here; the head record on disk does not.
        self.down = True
        self.attempt = self.adopted = None
        self.relay = self.printing = None
        if self.resume_run is not None:
            self.resume_run['error'] = 'printer_disconnected'
        if self.run:
            self.phase, self.failure = 'failed', 'printer_disconnected'

    def _cancel(self, *args):
        self.relay = None
        if self.resume_run is not None:
            self.resume_run['error'] = 'print_cancelled'
        if self.phase in ('planned', 'referenced', 'material'):
            self.phase, self.failure = 'failed', 'start_cancelled'
            self._cool()

    def _output(self, text):
        lines = [line.strip() for line in str(text).splitlines()
                 if line.lstrip().startswith('!!')]
        if not lines:
            return
        self.errors_seen += len(lines)
        if self.stock_running:
            # Judged once the stock T returns, never silently dropped: an
            # overflow is itself an untolerated line.
            for line in lines:
                if len(self.stock_lines) < MAX_STOCK_LINES:
                    self.stock_lines.append(line[:400])
                else:
                    self.stock_lines[-1] = '!! too many stock errors'
            return
        if self.in_reload:
            # Judged once the stock reload returns. Too many lines prove
            # nothing: the relay is then left unattributed.
            for line in lines:
                if self.reload_lines is None or len(self.reload_lines) >= MAX_STOCK_LINES:
                    self.reload_lines = None
                else:
                    self.reload_lines.append(line[:400])
            return
        if self.resume_run is not None and not self.resume_run['error']:
            # Never over a cancel or a disconnect already noted.
            self.resume_run['error'] = 'firmware_reported_error'
        if self.phase == 'material' or self.reference_running:
            self.command_error = 'firmware_reported_error'

    def _cool(self):
        self.printer.lookup_object('heaters').turn_off_all_heaters()

    def _enabled(self):
        if not self.enabled or not self.originals:
            raise StartRefused('retained_start_disabled_or_not_ready')
        if (not self._status('kctrl_purge_guard').get('installed')
                or not self._status('kctrl_bin_motion').get('installed')):
            raise StartRefused('bin_guards_not_installed')

    def _xyz(self):
        if set(self._status('toolhead').get('homed_axes', '')) != set('xyz'):
            raise StartRefused('axes_not_referenced')

    def _sensors(self):
        values = tuple(self._status('filament_switch_sensor ' + name).get('filament_detected')
                       for name in ('filament_sensor_2', 'filament_sensor'))
        if not all(type(value) is bool for value in values):
            raise StartRefused('filament_sensor_unknown')
        return values

    def _route(self):
        return live_route(self._status('box'), self.boxes)

    def _current(self):
        settings = self._status('configfile')['settings']['tmc2209 extruder']
        expected = settings['run_current']
        # Creality records 2 A as the default hold request; its TMC driver
        # clamps that request to run_current. Never command more than run.
        hold = min(settings.get('hold_current', expected), expected)
        if not current_is_ready(expected, expected) or not current_is_ready(hold, hold):
            raise StartRefused('extruder_current_configuration_invalid')
        self.gcode.run_script_from_command('M400')
        actual = self._status('tmc2209 extruder')
        if not (current_is_ready(actual.get('run_current'), expected)
                and current_is_ready(actual.get('hold_current'), hold)):
            self.gcode.run_script_from_command(
                'SET_TMC_CURRENT STEPPER=extruder CURRENT=%.6f HOLDCURRENT=%.6f\nM400'
                % (expected, hold))
        actual = self._status('tmc2209 extruder')
        if not (current_is_ready(actual.get('run_current'), expected)
                and current_is_ready(actual.get('hold_current'), hold)):
            raise StartRefused('extruder_current_readback_failed')

    def _stock(self, name, plan, stock, gcmd):
        self.attempt = self.adopted = None
        head, upstream = self._sensors()
        self._current()
        # A stock T cuts, rewinds and loads. Until it proves what it left at
        # the head, no earlier record may survive a power cut.
        self._sever('stock_t')
        self.moving += 1
        try:
            return self.originals['run_stock'](name, plan, stock, gcmd)
        finally:
            self.moving -= 1
            # Only an insertion which began with an empty head can attribute
            # a newly occupied head to this slot after a failed stock command.
            now_head, now_upstream = self._sensors()
            if (not head and now_head and now_upstream
                    and getattr(self.action, 'extrude_tnn', None) == plan['physical']):
                self.attempt = {'slot': plan['physical'], 'has_head': True}
                self._remember(plan['physical'], 'attempt')
            elif now_head and now_upstream and self._quiet_route() == plan['physical']:
                # The route this very T engaged, never one left by an earlier
                # filament: a failed change may still show the old slot.
                self._remember(plan['physical'], 'stock')

    def _same_loaded_selection(self, index):
        """Read-only proof that this T only repeats the active tool of this job.

        Z after priming or a hop is not a layer number. A redundant selection
        must preserve the target already commanded by the file, without
        realigning a material record or entering the stock change sequence.
        A different tool, missing proof, or inactive job uses the usual path.
        """
        if not self.enabled or self.phase != 'complete' or not self.run:
            return False
        try:
            run = self.run
            job, end = self._status('print_stats'), self._status('kctrl_end')
            if (job.get('state') != 'printing' or job.get('filename') != run['filename']
                    or end.get('pending') is not False or end.get('phase') != 'idle'
                    or end.get('job_epoch') != run['epoch']
                    or self._status('pause_resume').get('is_paused') is not False
                    or not self.reference_valid):
                return False
            self._xyz()
            if (self.printer.lookup_object('kctrl_slot_map').printing_file() != run['path']
                    or file_identity(run['path']) != run['motion']['identity']):
                return False
            plan = self.change.resolve(index)
            last = self.change.last
            if (not plan or last.get('tool') != 'T%d' % index
                    or last.get('outcome') not in ('start', 'done')
                    or last.get('slot') != plan['physical']
                    or self._route() != plan['physical']
                    or self.action.box_save.last_cmd != plan['physical']
                    or self._sensors() != (True, True)):
                return False
            nozzle = self._status('extruder')
            return (str(self._status('box')['T' + plan['physical'][1]].get('mode')) == '2'
                    and nozzle.get('can_extrude') is True
                    and finite(nozzle.get('target')) and 150. <= nozzle['target'] <= 300.)
        except Exception:
            # This probe performed no effect. The existing wrapper remains
            # responsible for reporting an invalid mapping or doing a change.
            return False

    def _selection(self, index, stock, gcmd):
        if not self._same_loaded_selection(index):
            return self.originals['change'](index, stock, gcmd)
        try:
            self._current()
        except Exception as error:
            self._fail(error)
            raise gcmd.error('K1 Control: courant extrudeur non retabli (%s)' % error)
        gcmd.respond_info('K1 Control: T%d deja actif sur %s, consigne du fichier conservee (%g C)'
                         % (index, self.change.last['slot'], self._status('extruder')['target']))

    def adopt(self, gcmd):
        """Explicit operator attribution only; never commits a CFS cache."""
        self._enabled()
        slot = gcmd.get('SLOT', '').upper()
        if slot not in SLOTS or self._sensors() != (True, True):
            raise gcmd.error('K1 Control: attribution impossible, filament continu requis')
        if (self._status('print_stats').get('state') not in ('standby', 'error', 'cancelled', 'complete')
                or self._status('kctrl_end').get('pending') is not False
                or self.phase in ('planned', 'referenced', 'material')):
            raise gcmd.error('K1 Control: attribution refusee pendant une operation')
        if self._route() not in (None, slot):
            raise gcmd.error('K1 Control: une autre route est engagee')
        unit = self._status('box').get('T' + slot[1], {})
        if unit.get('state') != 'connect':
            raise gcmd.error('K1 Control: unite deconnectee')
        self.adopted = slot
        self._remember(slot, 'operator')
        gcmd.respond_info('K1 Control: %s attribue par operateur, purge encore requise' % slot)

    def plan(self, gcmd):
        try:
            self._enabled()
            epoch = self._status('kctrl_end').get('job_epoch')
            if type(epoch) is not int or epoch <= 0:
                raise StartRefused('job_epoch_missing')
            if (self.phase in ('planned', 'referenced', 'material') and self.run
                    and self.run['epoch'] == epoch):
                raise StartRefused('start_already_active')
            self.run = None
            self.recovery = None
            self.rest = None
            self.relay = self.resume_last = self.printing = None
            self.failure = self.command_error = ''
            slot = gcmd.get('SLOT', '').upper()
            index = gcmd.get_int('INDEX', minval=0, maxval=15)
            temp = gcmd.get_float('TEMP', minval=150., maxval=300.)
            if slot not in SLOTS:
                raise StartRefused('requested_route_invalid')
            if self._status('kctrl_end').get('pending') is not False:
                raise StartRefused('end_still_active')
            job = self._status('print_stats')
            if job.get('state') != 'printing' or not job.get('filename'):
                raise StartRefused('new_print_not_active')
            head, upstream = self._sensors()
            route = self._route()
            attempt = self.attempt or {}
            # The record on disk is what a restart leaves of the attribution.
            # It only matters without a live route, which stays the stronger
            # evidence, and the retained purge must still prove consumption.
            recorded = self.head['slot'] if self.head else None
            attributable = (self.adopted == slot or recorded == slot or
                            (attempt.get('slot') == slot and attempt.get('has_head') is True
                             and getattr(self.action, 'extrude_tnn', None) == slot))
            # Identity only. Do not invent XYZ or call the movement policy
            # with pretend homing. The actual decision is made after probing.
            if head and upstream and route is None and not attributable and recorded:
                # Changing it without a CFS route is not qualified: refused,
                # naming what the head holds.
                raise StartRefused('retained_head_holds_%s_not_%s' % (recorded, slot))
            if head and (not upstream or (route is None and not attributable)):
                raise StartRefused('retained_identity_or_continuity_unproven')
            if not head and route:
                raise StartRefused('partial_filament_requires_recovery')
            path = self.printer.lookup_object('kctrl_slot_map').printing_file()
            if not path:
                raise StartRefused('job_file_missing')
            motion = file_motion(path, index)
            self.run = {'slot': slot, 'index': index, 'temp': temp, 'head': head,
                        'upstream': upstream, 'route': route, 'attributable': attributable,
                        'reference_before': self.reference, 'path': path, 'motion': motion,
                        'filename': job['filename'], 'epoch': epoch}
            self.phase = 'planned'
        except Exception as error:
            self.phase, self.failure = 'failed', str(error)
            raise gcmd.error('K1 Control: preparation refusee (%s)' % error)

    def _check(self, run, phases, geometry=True, paused_ok=False):
        if run is not None and run.get('resume'):
            # The purge of a paused print has its own proofs.
            return self._resume_check(run)
        self._enabled()
        if run is None or run is not self.run or self.phase not in phases:
            raise StartRefused(self.failure or 'start_invalidated')
        if (self._status('print_stats').get('filename') != run['filename']
                or self.printer.lookup_object('kctrl_slot_map').printing_file() != run['path']
                or file_identity(run['path']) != run['motion']['identity']):
            raise StartRefused('job_changed')
        if self._status('kctrl_end').get('pending') is not False:
            raise StartRefused('end_still_active')
        if self._status('kctrl_end').get('job_epoch') != run['epoch']:
            raise StartRefused('job_epoch_changed')
        if not paused_ok and self._status('pause_resume').get('is_paused') is not False:
            raise StartRefused('start_paused')
        if self._status('print_stats').get('state') != 'printing':
            raise StartRefused('print_no_longer_active')
        if self.command_error:
            raise StartRefused(self.command_error)
        if 'deadline' in run and self.reactor.monotonic() >= run['deadline']:
            raise StartRefused('material_timeout')
        if geometry:
            self._xyz()
            if not self.reference_valid or self.reference <= run['reference_before']:
                raise StartRefused('fresh_reference_missing')

    def reference_ready(self, gcmd):
        try:
            run = self.run
            self._check(run, ('planned',))
            if self._sensors() != (run['head'], run['upstream']) or self._route() != run['route']:
                raise StartRefused('filament_changed_during_reference')
            nozzle = self._status('extruder')
            if (not finite(nozzle.get('temperature')) or nozzle['temperature'] > 103.
                    or not finite(nozzle.get('target')) or nozzle['target'] > 100.):
                raise StartRefused('contact_temperature_not_confirmed')
            run['branch'] = decide_start(
                run['head'], run['upstream'], run['slot'], run['route'], run['slot'],
                self._status('toolhead')['homed_axes'], run['attributable'], run['attributable'])
            self.phase = 'referenced'
        except Exception as error:
            self._fail(error)
            raise gcmd.error('K1 Control: reference de depart refusee (%s)' % error)

    def _fail(self, error):
        self.phase, self.failure = 'failed', str(error)
        self._cool()

    def _watchdog(self, eventtime):
        if self.phase == 'material':
            self._fail('material_timeout')
        return self.reactor.NEVER

    def _script(self, run, command):
        self._check(run, ('material',))
        self.gcode.run_script_from_command(command)
        self._check(run, ('material',))

    def material(self, gcmd):
        self.watchdog = None
        try:
            run = self.run
            self._check(run, ('referenced',))
            if self._sensors() != (run['head'], run['upstream']) or self._route() != run['route']:
                raise StartRefused('filament_changed_before_material')
            self.phase = 'material'
            run['deadline'] = self.reactor.monotonic() + self.timeout
            self.watchdog = self.reactor.register_timer(self._watchdog, run['deadline'])
            self._current()
            self._check(run, ('material',))
            self._motion(run)
            if run['branch'] in ('keep', 'recover'):
                self._purge(run)
            else:
                self._stock_load(run, gcmd)
            self._check(run, ('material',))
            if self._sensors()[0] is not True:
                raise StartRefused('stock_load_left_head_empty')
            self.phase = 'complete'
            gcmd.respond_info('K1 Control: filament %s pret (%s%s)' % (
                run['slot'], run['branch'], ', repris' if run.get('recovered') else ''))
        except Exception as error:
            self._fail(error)
            if self._rest() == 'out_of_bin':
                gcmd.respond_info('K1 Control: tete sortie du bac (Y273), plateau inchange')
            raise gcmd.error('K1 Control: depart interrompu (%s)' % error)
        finally:
            if self.watchdog is not None:
                self.reactor.unregister_timer(self.watchdog)
                self.watchdog = None

    def _rest(self):
        """Leave the bin after a stopped start, when that is proven harmless.

        A head left latched in the bin refuses every later move once the
        motors are released, homing included, until Klipper restarts. The
        exit is the purge's own: Y273 at constant height, under the bin
        guard. No homing, no Z move, no extrusion, never from a timer. The
        start has already failed: nothing here may hide why.
        """
        self.rest = 'skipped'
        try:
            if self.down:
                return self.rest
            if self._status('kctrl_purge_guard').get('bin_latched') is not True:
                self.rest = 'not_in_bin'
                return self.rest
            if set(self._status('toolhead').get('homed_axes', '')) != set('xyz'):
                self.rest = 'not_referenced'
                return self.rest
            z = self.toolhead.get_position()[2]
            if not finite(z) or z < REST_MINIMUM_Z:
                self.rest = 'bed_too_high'
                return self.rest
            # A stock pause moves the head outside gcode_move, or leaves a
            # refused target in it: plan from the real position.
            self.printer.lookup_object('gcode_move').reset_last_position()
            self.rest = 'refused'
            self.gcode.run_script_from_command('SAVE_GCODE_STATE NAME=KCTRL_START_REST')
            try:
                self.gcode.run_script_from_command('G90\nG1 Y273 F15000\nM400')
            finally:
                self.gcode.run_script_from_command(
                    'RESTORE_GCODE_STATE NAME=KCTRL_START_REST MOVE=0')
            if self._status('kctrl_purge_guard').get('bin_latched') is not False:
                self.rest = 'exit_not_confirmed'
                return self.rest
            self.rest = 'out_of_bin'
            logging.info('kctrl_start: head left the bin after a stopped start, z=%.3f', z)
        except Exception:
            if self.rest == 'skipped':
                self.rest = 'unavailable'
            logging.exception('kctrl_start: bin exit after a stopped start (%s)', self.rest)
        return self.rest

    def _stock_load(self, run, gcmd):
        """The stock T, judged as a whole once it returns.

        While it runs, '!!' lines are collected instead of failing at the
        first one: the stock reports key837 then pauses inside this very
        START_PRINT. A clean stock load keeps the usual path untouched.
        """
        self._check(run, ('material',))
        # Our bin guard cuts every heater, bed included, when it refuses the
        # stock pause's descent (17:11:14). A recovery restores this target.
        run['bed_target'] = self._status('heater_bed').get('target')
        self.gcode.run_script_from_command('SAVE_GCODE_STATE NAME=KCTRL_STOCK_LOAD')
        self.stock_lines = []
        self.stock_running = True
        try:
            self.gcode.run_script_from_command('T%d\nM400' % run['index'])
        finally:
            self.stock_running = False
        lines, self.stock_lines = self.stock_lines, []
        codes, others = classify_stock_errors(lines, run['slot'])
        if others:
            logging.error('kctrl_start: stock load reported %s', ' | '.join(others))
            self.command_error = 'firmware_reported_error'
            raise StartRefused('firmware_reported_error')
        paused = self._status('pause_resume').get('is_paused') is not False
        if not codes and not paused:
            self._check(run, ('material',))
            return
        self._recover(run, codes, paused, gcmd)

    def _recover(self, run, codes, paused, gcmd):
        """Undo the stock failure of this start, proven harmless, then purge.

        Every proof is read before the first effect. The effects mirror what
        the firmware itself does: its PAUSE only sets flags while START_PRINT
        runs inline (cmd_from_sd), and its work handler clears the CFS lift
        record before each print. The purge then proves real consumption.
        """
        if run.get('recovered'):
            raise StartRefused('stock_load_failed_again')
        if self.phase != 'material':
            raise StartRefused(self.failure or 'material_timeout')
        self._check(run, ('material',), paused_ok=True)
        box = self.printer.lookup_object('box')
        if getattr(box, 'inside_error', None):
            raise StartRefused('cfs_error_still_processing')
        if self._sensors() != (True, True):
            raise StartRefused('stock_load_failed_head_not_loaded')
        if getattr(self.action, 'extrude_tnn', None) != run['slot']:
            raise StartRefused('stock_load_failed_slot_unproven')
        if self._route() not in (None, run['slot']):
            raise StartRefused('stock_load_failed_other_route')
        save = getattr(self.action, 'box_save', None)
        record = getattr(box, 'record_tn_move_z', None)
        if (save is None or not hasattr(save, 'move_z') or not hasattr(save, 'last_err')
                or not callable(record)):
            raise StartRefused('cfs_lift_record_unknown')
        position = self.printer.lookup_object('gcode_move')
        if not callable(getattr(position, 'reset_last_position', None)):
            raise StartRefused('gcode_position_reset_missing')
        bed = run.get('bed_target')
        if not finite(bed) or not 0. <= bed <= 130.:
            raise StartRefused('bed_target_unknown')
        pause = self.printer.lookup_object('pause_resume')
        sd = self.printer.lookup_object('virtual_sdcard', None)
        if paused:
            if (sd is None or not hasattr(sd, 'must_pause_work')
                    or not callable(getattr(sd, 'is_active', None)) or sd.is_active() is not True
                    or not all(hasattr(pause, name) for name in
                               ('is_paused', 'pause_command_sent', 'sd_paused'))):
                raise StartRefused('stock_pause_not_reversible')
        # Effects. The deadline first: the purge below is a new bounded step.
        run['deadline'] = self.reactor.monotonic() + self.recovery_timeout
        if self.watchdog is not None:
            self.reactor.update_timer(self.watchdog, run['deadline'])
        lifted = save.move_z
        reheat = bed > 0. and self._status('heater_bed').get('target') != bed
        run['recovered'] = {'codes': sorted(set(codes)), 'paused': paused,
                            'lift': lifted if finite(lifted) else None}
        if reheat:
            run['recovered']['bed'] = bed
        self.recovery = dict(run['recovered'], slot=run['slot'], outcome='purging')
        if paused:
            # PAUSE ran inside this START_PRINT: virtual_sdcard has not left
            # its loop, so print_stats is still printing. Clearing the flags
            # it set lets the loop continue with the next file line.
            pause.is_paused = pause.pause_command_sent = pause.sd_paused = False
            sd.must_pause_work = False
        self.gcode.run_script_from_command('RESTORE_GCODE_STATE NAME=KCTRL_STOCK_LOAD MOVE=0')
        if reheat:
            # Heats during the purge; waited for after it, before priming.
            self.gcode.run_script_from_command('M140 S%.3f' % bed)
        # The failed T lowered the bed and recorded that lift; its restore
        # never ran. A later tool change would subtract it again (document 70).
        save.move_z = None
        record(0)
        # The stock pause moved the head outside gcode_move, or left a
        # refused target in it: start the purge from the real position.
        position.reset_last_position()
        self.command_error = ''
        if paused:
            self._report('key602')
        logging.info('kctrl_start: stock load recovery slot=%s codes=%s paused=%s lift=%s',
                     run['slot'], codes, paused, lifted)
        gcmd.respond_info(
            'K1 Control: chargement stock de %s en echec (%s), filament en tete : '
            'reprise automatique par purge au bac'
            % (run['slot'], ', '.join(sorted(set(codes))) or 'pause stock'))
        try:
            self._purge(run)
            if bed > 0.:
                self._script(run, 'M190 S%.3f' % bed)
                if self._status('heater_bed').get('target') != bed:
                    raise StartRefused('bed_target_not_restored')
        except Exception:
            self.recovery['outcome'] = 'failed'
            raise
        self.recovery['outcome'] = 'purged'

    def _report(self, key):
        pause = self.printer.lookup_object('pause_resume')
        report = getattr(sys.modules.get(type(pause).__module__), 'reportInformation', None)
        if not callable(report):
            logging.warning('kctrl_start: screen not told %s, no reportInformation', key)
            return
        try:
            report(key)
        except Exception:
            logging.exception('kctrl_start: screen not told %s', key)

    def _temperature(self, run):
        self._check(run, ('material',))
        nozzle = self._status('extruder')
        target = max(200., run['temp'])
        if (nozzle.get('can_extrude') is not True or nozzle.get('target') != target
                or not finite(nozzle.get('temperature'))
                or abs(nozzle['temperature'] - target) > 5.):
            raise StartRefused('purge_temperature_changed')
        if run.get('resume'):
            # A resume may begin with the stale route of the spool which ran
            # out: what the CFS shows must stay as it began, or already name
            # the proven slot alone.
            same = self._routes() in (run['route'], (run['slot'],))
        else:
            same = self._route() == run['route']
        if self._sensors() != (True, True) or not same:
            raise StartRefused('retained_filament_changed')

    def _thermal(self, run):
        self._temperature(run)
        if str(self._status('box')['T' + run['slot'][1]].get('mode')) != '2':
            raise StartRefused('cfs_print_mode_lost')
        if not current_is_ready(self._status('tmc2209 extruder').get('run_current'),
                                self._status('configfile')['settings']['tmc2209 extruder']['run_current']):
            raise StartRefused('extruder_current_changed')

    def _motion(self, run):
        cfg = self._status('configfile')['settings']['printer']
        accel = min(float(cfg['max_accel']), run['motion']['travel_acceleration'])
        decel = min(accel, float(cfg['max_accel_to_decel']))
        velocity = float(cfg['max_velocity'])
        if not all(finite(v) and v > 0 for v in (accel, decel, velocity)):
            raise StartRefused('motion_configuration_invalid')
        self._script(run, 'SET_VELOCITY_LIMIT VELOCITY=%.3f ACCEL=%.3f ACCEL_TO_DECEL=%.3f'
                     % (velocity, accel, decel))

    def _purge(self, run):
        self._script(run, 'SAVE_GCODE_STATE NAME=KCTRL_RETAINED_START')
        try:
            self._script(run, 'M220 S100\nM221 S100\nG90')
            z = self.toolhead.get_position()[2]
            if not finite(z):
                raise StartRefused('position_unknown')
            if z < 35.:
                self._script(run, 'G91\nG1 Z%.5f F1200\nG90\nM400' % (35.1 - z))
            if self.toolhead.get_position()[2] < 35.:
                raise StartRefused('purge_margin_missing')
            self._script(run, 'G1 Y273 F24000\nG1 X185.5 F24000\n'
                         'G1 Y305 F6000\nM400')
            self._script(run, 'M109 S%.3f' % max(200., run['temp']))
            self._temperature(run)
            # Clear old failure flags for this new, attributed retained start.
            # This is not a new feed request and never performs a retry.
            self._script(run, 'BOX_ERROR_CLEAR')
            if run.get('recovered') and self.action.box_save.last_err is not None:
                # The firmware would pause the next print on this record.
                raise StartRefused('cfs_error_not_cleared')
            addr, slot = int(run['slot'][1]), run['slot'][2]
            self._check(run, ('material',))
            result = self.action.communication_set_box_mode(addr, 'PRINT', slot)
            self._check(run, ('material',))
            if result is not True:
                raise StartRefused('cfs_print_ack_missing')
            # Exact isolated binary trace: GET_BOX_STATE sends [addr], [0x0a]
            # with a 3600-second timeout. Keep its read-only frame but bound
            # the wait to 2 seconds, like GET_BUFFER_STATE, with no retry.
            result = self.action.send_data(bytes([addr]), bytes([0x0a]), 2)
            self._check(run, ('material',))
            if result is not True:
                raise StartRefused('cfs_state_ack_missing')
            self._thermal(run)
            self._script(run, 'M83')
            consumed = False
            for _ in range(7):
                self._thermal(run)
                self._script(run, 'G1 E20 F%.5f\nM400' % (60. * run['motion']['feed']))
                if self.action.communication_get_buffer_state(addr) is not True:
                    raise StartRefused('buffer_ack_missing')
                self._thermal(run)
                buffer = self.action.box_state.get_Tn_inner_data(addr, None, uppart='buffer')
                if type(buffer) is not int or buffer not in (0, 1):
                    raise StartRefused('buffer_empty_or_unknown')
                consumed = consumed or buffer == 0
            if not consumed:
                raise StartRefused('buffer_consumption_unconfirmed')
            if run.get('resume'):
                # The head travels back over the part: the recipe of 15
                # November, 0.8 mm back here, primed again at the stop point.
                self._script(run, 'G1 E-%.3f F1800\nM400' % RESUME_PRIME)
            for _ in range(3):
                self._script(run, 'G1 Y291.5 F15000\nG1 Y305 F6000\nM400')
            self._script(run, 'G1 Y273 F15000\nM400')
            if self._status('kctrl_purge_guard').get('bin_latched') is not False:
                raise StartRefused('bin_exit_not_confirmed')
            self._thermal(run)
            # Same cache update as stock success, only after acknowledged
            # PRINT mode, consumed buffer and completed exit. No serial effect.
            for stale in run.get('stale', ()):
                if stale[1] != run['slot'][1]:
                    # The spool which ran out sat on another unit: its route
                    # is cleared in memory, as the end of a print does.
                    self.action.update_filament_pos(stale, None)
            self.action.update_filament_pos(run['slot'], run['slot'])
            self.action.box_save.last_cmd = run['slot']
            if run.get('resume') and self._routes() != (run['slot'],):
                # A stale route on the same unit: the write proven by hand on
                # 15 November, memory only, no frame and no motor (document 96).
                self._script(run, 'BOX_MODIFY_TN_DATA ADDR=%d PART=filament DATA=%s'
                             % (addr, slot))
            if self._route() != run['slot']:
                raise StartRefused('retained_bookkeeping_not_confirmed')
            if run.get('resume'):
                run['route'] = self._routes()
            else:
                self.change.last = {'tool': 'T%d' % run['index'], 'outcome': 'start',
                                    'slot': run['slot'], 'temp': run['temp']}
            self.attempt = self.adopted = None
            # Acknowledged PRINT mode and a consumed buffer: the strongest
            # proof this module has of what the head holds.
            self._remember(run['slot'], 'purge')
            logging.info('kctrl_start: retained purge complete slot=%s feed=%s',
                         run['slot'], run['motion']['feed'])
        finally:
            self.gcode.run_script_from_command('RESTORE_GCODE_STATE NAME=KCTRL_RETAINED_START MOVE=0')

    # --- relay and resume of a paused print (ADR-081) -----------------------

    def _ready_resume(self):
        """Stand in front of the stock RESUME, refill relay, flush and reload.

        Fail-soft: anything missing leaves the start and the head record
        installed and every stock path untouched (relay.installed false).
        """
        if self.resume_hooks:
            return
        sd = self.printer.lookup_object('virtual_sdcard', None)
        if sd is None or not hasattr(sd, 'resume_tnn') or not hasattr(sd, 'file_position'):
            raise StartRefused('virtual_sdcard_resume_fields_missing')
        if not callable(getattr(self.printer.lookup_object('gcode_move'),
                                'reset_last_position', None)):
            raise StartRefused('gcode_position_reset_missing')
        handlers = self.gcode.ready_gcode_handlers
        if not all(callable(handlers.get(name)) for name in STOCK_NAMES):
            raise StartRefused('stock_resume_handlers_missing')
        if not all(callable(getattr(self.change, name, None)) for name in
                   ('reload', 'in_start', 'runout_armed', 'rearm_runout')):
            raise StartRefused('tool_change_reload_missing')
        hooks = {name: handlers[name] for name in STOCK_NAMES}
        hooks['reload'] = self.change.reload
        ours = {'RESUME': self._resume, 'BOX_CHECK_MATERIAL_REFILL': self._refill,
                'BOX_RESUME_EXTRUDE': self._flush}
        replaced = []
        self.resume_hooks = hooks        # set first: a handler always finds its stock
        try:
            for name in STOCK_NAMES:
                self.gcode.register_command(name, None)
                replaced.append(name)
                self.gcode.register_command(name, ours[name])
            self.change.reload = self._reload
        except Exception:
            for name in replaced:
                self.gcode.register_command(name, None)
                self.gcode.register_command(name, hooks[name])
            self.change.reload = hooks['reload']
            self.resume_hooks = {}
            raise

    def _quiet(self, call, *args):
        """One step which must never raise (ADR-072); None when it did."""
        try:
            return call(*args)
        except Exception:
            logging.exception('kctrl_start: %s', getattr(call, '__name__', call))
            return None

    def _relay_ready(self):
        try:
            return bool(self.enabled and self.resume_hooks and not self.down
                        and self.phase not in ('planned', 'referenced', 'material')
                        and not self.change.in_start())
        except Exception:
            return False

    def _running(self):
        return (self._status('pause_resume').get('is_paused') is False
                and self._status('print_stats').get('state') == 'printing')

    def _tmc(self):
        status = self._status('tmc2209 extruder')
        run, hold = status.get('run_current'), status.get('hold_current')
        if not all(finite(value) and 0. < value <= 2. for value in (run, hold)):
            return None
        return run, hold

    def _run_current(self):
        # Document 110, item 1: a relay never runs on the pause current.
        if self._status('pause_resume').get('is_paused') is True:
            self._current()

    def _pause_current(self, before):
        """Back to the pause current this module raised, while still paused."""
        if not before or self.down:
            return
        if self._status('pause_resume').get('is_paused') is not True:
            return
        expected = self._status('configfile')['settings']['tmc2209 extruder']['run_current']
        now = self._tmc()
        if (not finite(expected) or before[0] >= expected - 0.035
                or (now is not None and abs(now[0] - before[0]) < 0.0005)):
            return
        self.gcode.run_script_from_command(
            'SET_TMC_CURRENT STEPPER=extruder CURRENT=%.6f HOLDCURRENT=%.6f\nM400'
            % (before[0], min(before[1], before[0])))

    def _kept_paused(self, before):
        # A relay which keeps its pause: head out of the bin (document 110,
        # item 4), pause current back.
        if self.down or self._status('pause_resume').get('is_paused') is not True:
            return
        self._quiet(self._leave_latched)
        self._pause_current(before)

    def _routes(self):
        """Every route the CFS memory shows, stale ones included."""
        box = self._status('box')
        found = []
        for unit in range(1, self.boxes + 1):
            data = box.get('T%d' % unit)
            letter = data.get('filament') if isinstance(data, dict) else None
            if isinstance(letter, str) and len(letter) == 1 and letter in 'ABCD':
                found.append('T%d%s' % (unit, letter))
        return tuple(found)

    def _align(self, slot):
        """Make the CFS route memory name the slot proven at the head.

        Memory only, no frame and no motor: the end-of-print call for a stale
        route on another unit, the start purge's call for the slot, then the
        write proven by hand on 15 November (document 96). Without it, a
        cancel after a failed relay would rewind the empty slot and leave the
        loaded one for the next start to trip on.
        """
        if self._routes() != (slot,):
            for stale in self._routes():
                if stale != slot and stale[1] != slot[1]:
                    self.action.update_filament_pos(stale, None)
            self.action.update_filament_pos(slot, slot)
            if self._routes() != (slot,):
                self.gcode.run_script_from_command(
                    'BOX_MODIFY_TN_DATA ADDR=%d PART=filament DATA=%s'
                    % (int(slot[1]), slot[2]))
            if self._routes() != (slot,):
                return False
            logging.info('kctrl_start: CFS route aligned on %s', slot)
        self.severed = False
        return True

    def _resume_temp(self):
        """The print temperature: the stock pause record, else what is known."""
        sources = (
            lambda: self._status('gcode_macro PRINTER_PARAM').get('hotend_temp'),
            lambda: self.change.last.get('temp'),
            lambda: self._status('extruder').get('target'))
        for read in sources:
            try:
                value = read()
            except Exception:
                continue
            if finite(value) and 150. <= value <= 300.:
                return float(value)
        return None

    def _resume_sentence(self, reason):
        return ('K1 Control: reprise refusee (%s), impression gardee en pause'
                % (RESUME_HINTS.get(reason) or reason))

    def _relay_sentence(self, note):
        if note.get('slot'):
            return ('K1 Control: chargement de %s en echec, filament en tete : appuyer '
                    'sur Reprendre, la reprise se fera par purge au bac' % note['slot'])
        if note.get('head') is not True:
            return ('K1 Control: chargement en echec, tete vide : verifier la bobine '
                    'puis appuyer sur Reprendre')
        return ('K1 Control: chargement en echec, filament en tete non attribue : '
                'Reprendre relancera le chargement stock')

    def _reload(self, name, stock, gcmd):
        """Around every T1A..T4D reload; only the stock exception goes out."""
        original = self.resume_hooks['reload']
        note = self._quiet(self._reload_before, name) if self._relay_ready() else None
        self.envelope += 1
        if note is not None:
            self.in_reload += 1
            self.moving += 1
        try:
            return original(name, stock, gcmd)
        finally:
            self.envelope -= 1
            if note is not None:
                self.in_reload -= 1
                self.moving -= 1
                self._quiet(self._reload_after, name, note, gcmd)

    def _reload_before(self, name):
        self._sever('reload')            # a stock reload cuts, rewinds and loads
        self.reload_lines = []
        currents = self._quiet(self._tmc)
        self._quiet(self._run_current)
        target = None
        try:
            target = self.action.box_state.Tnn_map.get(name)
        except Exception:
            logging.exception('kctrl_start: relay target of %s not read', name)
        limits, nozzle = self._status('toolhead'), self._status('extruder')
        note = {'tool': name, 'target': target if target in SLOTS else None,
                'head_before': self._sensors()[0], 'currents': currents,
                'limits': {key: limits.get(key) for key in LIMIT_WORDS},
                'advance': {key: nozzle.get(key) for key in ADVANCE_WORDS},
                'bed': self._status('heater_bed').get('target'),
                'filename': self._status('print_stats').get('filename')}
        previous = self.relay
        if (previous is not None and previous.get('paused') is True
                and previous.get('filename') == note['filename']):
            # Same incident: what the first failed load left is not the file's.
            for key in ('limits', 'advance', 'bed'):
                note[key] = previous.get(key)
        return note

    def _reload_after(self, name, note, gcmd):
        lines, self.reload_lines = self.reload_lines, []
        head, upstream = self._sensors()
        paused = self._status('pause_resume').get('is_paused') is True
        if not paused or (note['head_before'] is True and lines == []):
            # Success, or a reload asked during a pause with a loaded head and
            # no error line: nothing to recover.
            if not paused:
                self.relay = None
            route = self._quiet_route()
            if (head and upstream and route
                    and route == getattr(self.action.box_save, 'last_cmd', None)
                    and note['target'] in (None, route)):
                self._remember(route, 'reload')
            else:
                self._sever('reload_unproven')
            return
        slot = relay_slot(lines, note['target'], note['head_before'], head,
                          getattr(self.action, 'extrude_tnn', None))
        self.relay = dict(note, head=head, paused=True, lines=lines, slot=slot, tried=False)
        if slot and upstream:
            self._remember(slot, 'relay')
            self.severed = True          # the CFS may still show the stale route
        else:
            self._sever('relay_unattributed')
        logging.info('kctrl_start: reload %s ended paused, target=%s slot=%s head=%s lines=%s',
                     name, note['target'], slot, head, lines)
        if not self.in_refill:
            # No refill relay around this reload: nothing automatic, the
            # machine is left as a real pause which Reprendre can resume.
            if slot and upstream:
                self._quiet(self._align, slot)
            self._quiet(self._pause_current, note['currents'])
            gcmd.respond_info(self._relay_sentence(self.relay))

    def _refill(self, gcmd):
        """The stock spool relay, then the recovery of what it left paused."""
        stock = self.resume_hooks['BOX_CHECK_MATERIAL_REFILL']
        if not self._relay_ready():
            return stock(gcmd)
        # self.relay is kept: an old note has tried=True, a new one tried=False.
        before = self._quiet(self._tmc)
        self._quiet(self._run_current)
        self.in_refill += 1
        try:
            stock(gcmd)
        except Exception:
            self.in_refill -= 1
            if self._quiet(self._relay_recover, gcmd) is True:
                return
            self._quiet(self._kept_paused, before)
            raise
        self.in_refill -= 1
        if self._quiet(self._relay_recover, gcmd) is not True:
            self._quiet(self._kept_paused, before)
            self._quiet(self._refill_hint, gcmd)

    def _refill_hint(self, gcmd):
        if self.relay is not None or self._status('pause_resume').get('is_paused') is not True:
            return
        if self._resume_plan() is not None:
            gcmd.respond_info('K1 Control: CFS au repos, filament en tete : appuyer sur '
                              'Reprendre, la reprise se fera par purge au bac')

    def _relay_recover(self, gcmd):
        """Once every stock step of a failed relay has returned. True: printing."""
        note = self.relay
        if note is None or note.get('paused') is not True or note.get('tried'):
            return False
        note['tried'] = True
        if self._status('pause_resume').get('is_paused') is not True:
            self.relay = None
            return False
        if note['slot'] is None:
            gcmd.respond_info(self._relay_sentence(note))
            return False
        self._quiet(self._align, note['slot'])
        box = self.printer.lookup_object('box')
        deadline = self.reactor.monotonic() + ERROR_WAIT
        while getattr(box, 'inside_error', None):
            if self.reactor.monotonic() >= deadline:
                gcmd.respond_info('K1 Control: le CFS traite encore son erreur, '
                                  'appuyer sur Reprendre quand il a fini')
                return False
            self.reactor.pause(self.reactor.monotonic() + 1.)
        try:
            self.gcode.run_script_from_command('BOX_ERROR_CLEAR')
        except Exception:
            logging.exception('kctrl_start: CFS error not cleared after a relay')
            gcmd.respond_info(self._relay_sentence(note))
            return False
        seen = self.errors_seen
        self.reactor.pause(self.reactor.monotonic() + SETTLE)
        if self.relay is not note or self.errors_seen != seen or self.down:
            # Still reporting, cancelled or stopped meanwhile: nothing automatic.
            gcmd.respond_info(self._relay_sentence(note))
            return False
        try:
            run = self._resume_decide()
        except StartRefused as error:
            gcmd.respond_info(self._resume_sentence(str(error)))
            return False
        if run is None:
            gcmd.respond_info('K1 Control: reprise automatique non prouvee, la pause est gardee')
            return False
        reason = self._resume_recover(run, gcmd)
        if reason:
            gcmd.respond_info(self._resume_sentence(reason))
            return False
        return True

    def _pass_resume(self, gcmd):
        # The stock RESUME, untouched; _flush leaves the bin after its flush.
        self.in_resume += 1
        try:
            return self.resume_hooks['RESUME'](gcmd)
        finally:
            self.in_resume -= 1

    def _resume(self, gcmd):
        """RESUME: by the retained purge when proven, else the stock macro."""
        if self.resuming or gcmd.get('STOCK', '0') == '1' or not self._relay_ready():
            return self._pass_resume(gcmd)
        if self.envelope or self.in_refill:
            # The stock relay calling RESUME inside its own flow: never raise
            # here (ADR-072), only leave the bin before the bed comes up.
            self._quiet(self._leave_latched)
            return self._pass_resume(gcmd)
        if self._quiet(self._running) is True:
            # The stock macro has no such guard and would raise the bed by
            # the lift of the last pause, into the part.
            gcmd.respond_info('K1 Control: impression deja en cours, reprise ignoree')
            return
        try:
            run = self._resume_decide()
        except StartRefused as error:
            raise gcmd.error(self._resume_sentence(str(error)))
        if run is None:
            return self._pass_resume(gcmd)
        reason = self._resume_recover(run, gcmd)
        if reason:
            raise gcmd.error(self._resume_sentence(reason))

    def _resume_decide(self):
        """The purge plan of this resume, None for the stock path.

        A head latched in the bin leaves it first, at constant height
        (document 110, item 5): StartRefused when that exit is not proven,
        because the stock macro would raise the bed next.
        """
        try:
            if self._status('pause_resume').get('is_paused') is not True:
                return None
            self._enabled()
            latched = self._status('kctrl_purge_guard').get('bin_latched') is True
        except Exception:
            logging.exception('kctrl_start: resume left to the stock path')
            return None
        if latched:
            try:
                self._leave_bin()
            except StartRefused:
                raise
            except Exception:
                logging.exception('kctrl_start: bin exit before a resume')
                raise StartRefused('bin_exit_not_confirmed')
        try:
            run = self._resume_plan()
        except Exception:
            logging.exception('kctrl_start: resume left to the stock path')
            return None
        if run is not None and run['temp'] is None:
            raise StartRefused('resume_temperature_unknown')
        return run

    def _resume_plan(self):
        """Read-only. A plan only when the filament at the head is attributed."""
        head, upstream = self._sensors()
        job = self._status('print_stats')
        filename = job.get('filename')
        if (head is not True or upstream is not True or job.get('state') != 'paused'
                or not filename):
            return None
        record = self.head['slot'] if self.head else None
        if record not in SLOTS:
            return None
        routes = self._routes()
        note = self.relay
        if note is not None:
            if (note.get('paused') is not True or note.get('filename') != filename
                    or note.get('slot') != record):
                return None
            reason = 'relay_failed'
        else:
            # No relay: only a CFS left at rest under an unchanged filament.
            if any(route != record for route in routes):
                return None
            unit = self._status('box').get('T' + record[1])
            mode = unit.get('mode') if isinstance(unit, dict) else None
            if mode is None or str(mode) in ('2', 'None'):
                return None
            reason = 'cfs_at_rest'
        return {'resume': True, 'slot': record, 'temp': self._resume_temp(),
                'route': routes, 'stale': tuple(r for r in routes if r != record),
                'reason': reason, 'recovered': {'reason': reason},
                'motion': {'feed': RESUME_FEED}, 'filename': filename, 'error': '',
                'note': note, 'bed': self._resume_bed(filename, note)}

    def _resume_bed(self, filename, note):
        """The bed target to put back, when a guard refusal cut it."""
        wanted = None
        if self.printing and self.printing.get('filename') == filename:
            wanted = self.printing.get('bed')
        if not finite(wanted) and note:
            wanted = note.get('bed')
        now = self._status('heater_bed').get('target')
        if finite(wanted) and 0. < wanted <= 130. and finite(now) and now < wanted:
            return float(wanted)
        return None

    def _leave_bin(self):
        """Y273 at constant height, under the bin guard; raises when unproven."""
        self._xyz()
        z = self.toolhead.get_position()[2]
        if not finite(z) or z < REST_MINIMUM_Z:
            raise StartRefused('bin_exit_bed_too_high')
        # A stock routine moves the head outside gcode_move, or leaves a
        # refused target in it: plan from the real position.
        self.printer.lookup_object('gcode_move').reset_last_position()
        self.gcode.run_script_from_command('SAVE_GCODE_STATE NAME=KCTRL_RESUME_EXIT')
        try:
            self.gcode.run_script_from_command('G90\nG1 Y273 F15000\nM400')
        finally:
            self.gcode.run_script_from_command(
                'RESTORE_GCODE_STATE NAME=KCTRL_RESUME_EXIT MOVE=0')
        if self._status('kctrl_purge_guard').get('bin_latched') is not False:
            raise StartRefused('bin_exit_not_confirmed')
        logging.info('kctrl_start: head left the bin before a resume, z=%.3f', z)

    def _leave_latched(self):
        if self.down or self._status('kctrl_purge_guard').get('bin_latched') is not True:
            return
        self._leave_bin()

    def _resume_check(self, run):
        self._enabled()
        if run is not self.resume_run or self.down:
            raise StartRefused('resume_invalidated')
        if run['error']:
            raise StartRefused(run['error'])
        job = self._status('print_stats')
        if (job.get('state') != 'paused' or job.get('filename') != run['filename']
                or self._status('pause_resume').get('is_paused') is not True):
            raise StartRefused('print_no_longer_paused')
        if self._status('kctrl_end').get('pending') is not False:
            raise StartRefused('end_still_active')
        if self.reactor.monotonic() >= run['deadline']:
            raise StartRefused('resume_timeout')
        self._xyz()

    def _still_paused(self, run):
        job = self._status('print_stats')
        return (job.get('state') == 'paused' and job.get('filename') == run['filename']
                and self._status('pause_resume').get('is_paused') is True)

    def _resume_recover(self, run, gcmd):
        """The purge, then the stock RESUME. '' when printing, else the reason.

        Every proof is read before the first effect. Refused, the print stays
        a real pause: head out of the bin, targets and pause current back.
        """
        try:
            self.resume_run = run
            run['deadline'] = self.reactor.monotonic() + RESUME_TIMEOUT
            self._resume_check(run)
            if self._sensors() != (True, True):
                raise StartRefused('head_not_loaded')
            box = self.printer.lookup_object('box')
            unit = self._status('box').get('T' + run['slot'][1])
            if not isinstance(unit, dict) or unit.get('state') != 'connect':
                raise StartRefused('cfs_unit_disconnected')
            if getattr(box, 'inside_error', None):
                raise StartRefused('cfs_error_still_processing')
            save = getattr(self.action, 'box_save', None)
            if save is None or not hasattr(save, 'last_err') or not hasattr(save, 'last_cmd'):
                raise StartRefused('cfs_record_unknown')
            if self._status('kctrl_purge_guard').get('bin_latched') is not False:
                raise StartRefused('bin_exit_not_confirmed')
            run['nozzle_before'] = self._status('extruder').get('target')
            run['bed_before'] = self._status('heater_bed').get('target')
            run['currents'] = self._quiet(self._tmc)
            self.moving += 1
            try:
                self.printer.lookup_object('gcode_move').reset_last_position()
                self._current()
                # Same first step as the stock RESUME. What the CFS repeated
                # before this clear is not this purge's.
                self.gcode.run_script_from_command('BOX_ERROR_CLEAR')
                if run['error'] == 'firmware_reported_error':
                    run['error'] = ''
                gcmd.respond_info('K1 Control: filament %s en tete, reprise par purge au bac'
                                  % run['slot'])
                if run['bed'] is not None:
                    self._script(run, 'M140 S%.3f' % run['bed'])
                self._purge(run)
                if self._status('extruder').get('target') != run['temp']:
                    self._script(run, 'M104 S%.3f' % run['temp'])
                if run['bed'] is not None:
                    run['deadline'] = self.reactor.monotonic() + BED_WAIT
                    self._script(run, 'M190 S%.3f' % run['bed'])
            finally:
                self.moving -= 1
        except Exception as error:
            return self._resume_abort(run, error)
        # Purge proven: a plain paused print from here, resumed the stock way.
        self.resume_run = None
        self.relay = None
        self._quiet(self._rearm)
        self._quiet(self._resume_restore, run)
        fans = self._quiet(self._resume_fans)
        try:
            self._stock_resume()
        except Exception:
            logging.exception('kctrl_start: stock RESUME after the purge')
            return self._resume_stopped(run, 'resume_command_failed', purged=True)
        self._quiet(self._clear_replay)
        if self._quiet(lambda: self._status('pause_resume').get('is_paused')) is not False:
            return self._resume_stopped(run, 'stock_resume_not_effective', purged=True)
        if fans:
            self._quiet(self._fans_back, fans)
        self._quiet(self._prime)
        self.resume_last = {'outcome': 'resumed', 'slot': run['slot'], 'reason': run['reason']}
        logging.info('kctrl_start: resume by purge complete slot=%s reason=%s',
                     run['slot'], run['reason'])
        gcmd.respond_info('K1 Control: filament %s repris au bac, impression relancee'
                          % run['slot'])
        return ''

    def _resume_abort(self, run, error):
        if isinstance(error, (StartRefused, EndRefused)):
            reason = str(error)
        else:
            logging.exception('kctrl_start: resume by purge')
            reason = run.get('error') or 'resume_command_failed'
        return self._resume_stopped(run, reason)

    def _resume_stopped(self, run, reason, purged=False):
        self.resume_run = None
        self.resume_last = {'outcome': 'refused', 'reason': reason, 'slot': run['slot'],
                            'cause': run['reason']}
        logging.info('kctrl_start: resume by purge refused (%s) slot=%s', reason, run['slot'])
        if self.down:
            return reason
        self._quiet(self._leave_latched)
        if reason == 'print_cancelled':
            return reason                # the cancel owns the machine: no re-heat
        if self._quiet(self._still_paused, run) is True:
            if not purged:
                self._quiet(self._target_back, run)
            self._quiet(self._pause_current, run.get('currents'))
        return reason

    def _target_back(self, run):
        # What the pause held before this attempt; a bed cut by a guard
        # refusal comes back, a paused part must stay on its plate.
        nozzle, bed = run.get('nozzle_before'), run.get('bed_before')
        if (finite(nozzle) and 0. <= nozzle <= 300.
                and self._status('extruder').get('target') != nozzle):
            self.gcode.run_script_from_command('M104 S%.3f' % nozzle)
        now = self._status('heater_bed').get('target')
        if finite(bed) and 0. < bed <= 130. and finite(now) and now < bed:
            self.gcode.run_script_from_command('M140 S%.3f' % bed)

    def _rearm(self):
        # The stock relay leaves the runout alarm off (15 November).
        if not self.change.runout_armed():
            self.change.rearm_runout('resume')

    def _resume_restore(self, run):
        """Limits and pressure advance of the file, where a stock load changed them."""
        source = run.get('note')
        if not (source and isinstance(source.get('limits'), dict)):
            source = (self.printing if self.printing
                      and self.printing.get('filename') == run['filename'] else None)
        if not source:
            return
        now = self._status('toolhead')
        words = ['%s=%.3f' % (LIMIT_WORDS[key], value)
                 for key, value in sorted((source.get('limits') or {}).items())
                 if key in LIMIT_WORDS and finite(value) and value > 0.
                 and now.get(key) != value]
        if words:
            self.gcode.run_script_from_command('SET_VELOCITY_LIMIT ' + ' '.join(words))
        now, advance, words = self._status('extruder'), source.get('advance') or {}, []
        value = advance.get('pressure_advance')
        if finite(value) and value >= 0. and now.get('pressure_advance') != value:
            words.append('ADVANCE=%.6f' % value)
        value = advance.get('smooth_time')
        if finite(value) and value > 0. and now.get('smooth_time') != value:
            words.append('SMOOTH_TIME=%.6f' % value)
        if words:
            self.gcode.run_script_from_command('SET_PRESSURE_ADVANCE ' + ' '.join(words))

    def _resume_fans(self):
        sd = self.printer.lookup_object('virtual_sdcard')
        path = self.printer.lookup_object('kctrl_slot_map').printing_file()
        if not path:
            return None
        count = self._status('gcode_macro PRINTER_PARAM').get('fans')
        count = count if type(count) is int and 1 <= count <= 8 else 3
        return file_fans(path, sd.file_position, count,
                         pause=lambda: self.reactor.pause(self.reactor.monotonic() + .001))

    def _fans_back(self, fans):
        self.gcode.run_script_from_command(
            '\n'.join('M106 P%d S%d' % item for item in sorted(fans.items())))

    def _stock_resume(self):
        self.resuming = self.flushed = True
        try:
            self.gcode.run_script_from_command('RESUME')
        finally:
            self.resuming = self.flushed = False

    def _flush(self, gcmd):
        if self.flushed:
            # The purge just proved more than this flush would push.
            self.flushed = False
            logging.info('kctrl_start: stock flush skipped, purge just proven')
            return
        result = self.resume_hooks['BOX_RESUME_EXTRUDE'](gcmd)
        if self.in_resume and self._relay_ready():
            # The stock RESUME raises the bed next: never with the guard latched.
            self._quiet(self._leave_latched)
        return result

    def _clear_replay(self):
        # The stock RESUME asks the file to replay the failed reload first:
        # it would cut the filament this purge has just proven.
        sd = self.printer.lookup_object('virtual_sdcard')
        if sd.resume_tnn is not None:
            logging.info('kctrl_start: stock reload %s not replayed', sd.resume_tnn)
            sd.resume_tnn = None

    def _prime(self):
        # At the stop point: what the purge pulled back before its wipes.
        self.gcode.run_script_from_command('SAVE_GCODE_STATE NAME=KCTRL_RESUME_PRIME')
        try:
            self.gcode.run_script_from_command('M83\nG1 E%.3f F1800\nM400' % RESUME_PRIME)
        finally:
            self.gcode.run_script_from_command(
                'RESTORE_GCODE_STATE NAME=KCTRL_RESUME_PRIME MOVE=0')

    def get_status(self, eventtime=None):
        return {'enabled': self.enabled, 'installed': bool(self.originals),
                'phase': self.phase, 'failure': self.failure,
                'reference': self.reference, 'reference_valid': self.reference_valid,
                'branch': self.run.get('branch') if self.run else None,
                'slot': self.run.get('slot') if self.run else None,
                'retained_attribution': self.adopted,
                'head': dict(self.head) if self.head else None,
                'head_saved': self.head_saved, 'rest': self.rest,
                'recovery': dict(self.recovery) if self.recovery else None,
                'recovery_timeout': self.recovery_timeout,
                'relay': {
                    'installed': bool(self.resume_hooks), 'failure': self.resume_failure,
                    'note': ({key: self.relay.get(key) for key in (
                        'tool', 'target', 'slot', 'head', 'paused', 'tried')}
                             if self.relay else None),
                    'last': dict(self.resume_last) if self.resume_last else None},
                'selection_policy': 'preserve-active-tool-target-v1',
                'revision': REVISION, 'physical_validation': False}


def load_config(config):
    return KctrlStart(config)
