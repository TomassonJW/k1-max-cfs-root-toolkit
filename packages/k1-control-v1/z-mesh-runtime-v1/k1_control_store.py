# K1 Control atomic persistent state for the captured Creality Klipper runtime.
# Offline candidate: do not install without G4-K1-CONTROL-Z-MESH-RUNTIME-V1.
from __future__ import print_function

import ast
import hashlib
import json
import logging
import math
import os


SCHEMA = 1
RECORD_LENGTH = 17
EMPTY_RECORD = [1, 0, 0.0, 0, 0, 0, 0, 0, 0, 0, 0.0, 0, 0, 0, 0, 0, 0]


class StateStoreError(Exception):
    pass


def _integer(value, label, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise StateStoreError("%s must be an integer >= %d" % (label, minimum))
    return value


def _offset(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StateStoreError("%s must be numeric" % label)
    value = float(value)
    if not math.isfinite(value) or value < -2.0 or value > 2.0:
        raise StateStoreError("%s must be finite and between -2.0 and 2.0" % label)
    return value


def validate_record(record):
    if not isinstance(record, (list, tuple)) or len(record) != RECORD_LENGTH:
        raise StateStoreError("record must contain exactly %d fields" % RECORD_LENGTH)
    result = list(record)
    if _integer(result[0], "schema") != SCHEMA:
        raise StateStoreError("unsupported record schema")
    result[1] = _integer(result[1], "accepted_valid")
    result[9] = _integer(result[9], "previous_valid")
    if result[1] not in (0, 1) or result[9] not in (0, 1):
        raise StateStoreError("valid flags must be 0 or 1")
    result[2] = _offset(result[2], "accepted_z")
    result[10] = _offset(result[10], "previous_z")
    for index, label in (
        (3, "plate"),
        (4, "temperature_band"),
        (5, "probe_revision"),
        (6, "nozzle_id"),
        (7, "config_id"),
        (8, "accepted_at"),
        (11, "previous_plate"),
        (12, "previous_temperature_band"),
        (13, "previous_probe_revision"),
        (14, "previous_nozzle_id"),
        (15, "previous_config_id"),
        (16, "previous_accepted_at"),
    ):
        result[index] = _integer(result[index], label)
    if result[1] == 1:
        for index in (3, 5, 6, 7, 8):
            if result[index] < 1:
                raise StateStoreError("accepted context is incomplete")
    if result[9] == 1:
        for index in (11, 13, 14, 15, 16):
            if result[index] < 1:
                raise StateStoreError("previous context is incomplete")
    return result


def _canonical_record(record):
    return json.dumps(record, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def encode_record(record):
    normalized = validate_record(record)
    canonical = _canonical_record(normalized)
    envelope = {
        "record": normalized,
        "schema": SCHEMA,
        "sha256": hashlib.sha256(canonical).hexdigest(),
    }
    return (json.dumps(envelope, separators=(",", ":"), sort_keys=True) + "\n").encode("ascii")


def decode_record(payload):
    try:
        envelope = json.loads(payload.decode("ascii"))
    except Exception as exc:
        raise StateStoreError("state file is not valid JSON: %s" % exc)
    if not isinstance(envelope, dict) or envelope.get("schema") != SCHEMA:
        raise StateStoreError("state envelope schema is invalid")
    record = validate_record(envelope.get("record"))
    expected = hashlib.sha256(_canonical_record(record)).hexdigest()
    if envelope.get("sha256") != expected:
        raise StateStoreError("state checksum mismatch")
    return record


def _sync_directory(directory):
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    try:
        descriptor = os.open(directory, flags)
    except OSError:
        if os.name == "nt":
            return
        raise
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_write(path, payload):
    directory = os.path.dirname(path)
    temporary = path + ".tmp"
    handle = open(temporary, "wb")
    try:
        os.chmod(temporary, 0o600)
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    finally:
        handle.close()
    os.replace(temporary, path)
    _sync_directory(directory)


def read_file(path):
    with open(path, "rb") as handle:
        payload = handle.read()
    return decode_record(payload), payload


def load_state(path):
    previous_path = path + ".previous"
    if not os.path.exists(path):
        return list(EMPTY_RECORD), "empty", os.path.exists(previous_path)
    try:
        record, _ = read_file(path)
        return record, "ok", os.path.exists(previous_path)
    except Exception:
        logging.exception("K1 Control state integrity failure")
        recovery_available = False
        if os.path.exists(previous_path):
            try:
                read_file(previous_path)
                recovery_available = True
            except Exception:
                logging.exception("K1 Control previous state is also invalid")
        return list(EMPTY_RECORD), "invalid", recovery_available


def persist_state(path, record):
    payload = encode_record(record)
    directory = os.path.dirname(path)
    if not os.path.isdir(directory):
        raise StateStoreError("state directory does not exist")
    if os.path.exists(path):
        _, current_payload = read_file(path)
        _atomic_write(path + ".previous", current_payload)
    _atomic_write(path, payload)
    return decode_record(payload)


class K1ControlStore(object):
    def __init__(self, config):
        self.printer = config.get_printer()
        self.filename = os.path.expanduser(config.get("filename"))
        self.record, self.integrity, self.recovery_available = load_state(self.filename)
        gcode = self.printer.lookup_object("gcode")
        gcode.register_command(
            "K1_STATE_SAVE",
            self.cmd_K1_STATE_SAVE,
            desc="Atomically save a validated K1 Control state record",
        )

    def cmd_K1_STATE_SAVE(self, gcmd):
        value = gcmd.get("RECORD")
        try:
            record = ast.literal_eval(value)
            self.record = persist_state(self.filename, record)
        except Exception as exc:
            raise gcmd.error("K1 Control atomic state save failed: %s" % exc)
        self.integrity = "ok"
        self.recovery_available = os.path.exists(self.filename + ".previous")

    def get_status(self, eventtime):
        return {
            "record": list(self.record),
            "integrity": self.integrity,
            "recovery_available": self.recovery_available,
        }


def load_config(config):
    return K1ControlStore(config)
