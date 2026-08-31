#!/usr/bin/env python3
"""Protocole CFS exact de la K1, sans transport et sans effet physique.

Le transport Creality actif sur la K1 attend une trame applicative sans l'octet
0xF7 ni le CRC. Il ajoute l'enveloppe sur le fil et renvoie une réponse complète.
Ce module garde les deux formes explicites afin de vérifier hors imprimante les
octets vus dans les journaux réels.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Tuple


PACK_HEAD = 0xF7
STATUS_OPERATIONAL = 0xFF
STATUS_OK = 0x00

CMD_SET_BOX_MODE = 0x04
CMD_GET_BUFFER_STATE = 0x05
CMD_GET_FILAMENT_SENSOR_STATE = 0x08
CMD_GET_BOX_STATE = 0x0A
CMD_SET_PRE_LOADING = 0x0D
CMD_TIGHTEN_UP_ENABLE = 0x0F
CMD_EXTRUDE_PROCESS = 0x10
CMD_RETRUDE_PROCESS = 0x11

SENSOR_MATERIAL = 0x00
SENSOR_CONNECTIONS = 0x01
MODE_FEED = bytes((0x00, 0x01))
TRIGGER_BUFFER = 0x00
TRIGGER_MATERIAL = 0x01

ROUTE_RE = re.compile(r"^T([1-4])([ABCD])$")
SLOT_MASKS = {"A": 0x01, "B": 0x02, "C": 0x04, "D": 0x08}


class ProtocolError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Route:
    logical: str
    address: int
    slot: str
    mask: int


@dataclass(frozen=True)
class Response:
    raw: bytes
    address: int
    length: int
    status: int
    command: int
    data: bytes
    crc: int


def route(value: str, max_boxes: int = 2) -> Route:
    match = ROUTE_RE.fullmatch(str(value).upper())
    if match is None:
        raise ProtocolError("route_invalid")
    address = int(match.group(1))
    slot = match.group(2)
    if not 1 <= address <= max_boxes:
        raise ProtocolError("route_box_out_of_scope")
    return Route("T%d%s" % (address, slot), address, slot, SLOT_MASKS[slot])


def _byte_values(values: Iterable[int]) -> Tuple[int, ...]:
    result = tuple(int(value) for value in values)
    if any(value < 0 or value > 0xFF for value in result):
        raise ProtocolError("byte_out_of_range")
    return result


def crc8(values: Iterable[int]) -> int:
    crc = 0x00
    for value in _byte_values(values):
        crc ^= value
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ 0x07) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc


def application_frame(
    address: int,
    command: int,
    data: Iterable[int] = (),
    status: int = STATUS_OPERATIONAL,
) -> bytes:
    payload = _byte_values(data)
    address = int(address)
    command = int(command)
    status = int(status)
    if not 1 <= address <= 0xFE:
        raise ProtocolError("address_invalid")
    _byte_values((command, status))
    length = len(payload) + 3
    return bytes((address, length, status, command) + payload)


def wire_frame_from_application(frame: bytes) -> bytes:
    frame = bytes(frame)
    if len(frame) < 4:
        raise ProtocolError("application_frame_too_short")
    if frame[1] != len(frame) - 1:
        raise ProtocolError("application_length_mismatch")
    checksum = crc8(frame[1:])
    return bytes((PACK_HEAD,)) + frame + bytes((checksum,))


def wire_frame(
    address: int,
    status: int,
    command: int,
    data: Iterable[int] = (),
) -> bytes:
    return wire_frame_from_application(
        application_frame(address, command, data, status=status)
    )


def parse_response(
    raw: bytes,
    expected_address: int,
    expected_command: int,
) -> Response:
    raw = bytes(raw)
    if len(raw) < 6:
        raise ProtocolError("response_too_short")
    if raw[0] != PACK_HEAD:
        raise ProtocolError("response_head_invalid")
    expected_total = raw[2] + 3
    if len(raw) != expected_total:
        raise ProtocolError("response_length_mismatch")
    if crc8(raw[2:-1]) != raw[-1]:
        raise ProtocolError("response_crc_invalid")
    if raw[1] != int(expected_address):
        raise ProtocolError("response_address_mismatch")
    if raw[4] != int(expected_command):
        raise ProtocolError("response_command_mismatch")
    return Response(
        raw=raw,
        address=raw[1],
        length=raw[2],
        status=raw[3],
        command=raw[4],
        data=raw[5:-1],
        crc=raw[-1],
    )


def set_feed_mode(target: Route) -> bytes:
    return application_frame(target.address, CMD_SET_BOX_MODE, MODE_FEED)


def set_print_mode(target: Route) -> bytes:
    return application_frame(
        target.address, CMD_SET_BOX_MODE, (target.mask, 0x00)
    )


def get_material_sensor(target: Route) -> bytes:
    return application_frame(
        target.address,
        CMD_GET_FILAMENT_SENSOR_STATE,
        (SENSOR_MATERIAL,),
    )


def get_connections_sensor(target: Route) -> bytes:
    return application_frame(
        target.address,
        CMD_GET_FILAMENT_SENSOR_STATE,
        (SENSOR_CONNECTIONS,),
    )


def get_buffer_state(target: Route) -> bytes:
    return application_frame(target.address, CMD_GET_BUFFER_STATE)


def tighten(address: int, enabled: bool) -> bytes:
    return application_frame(
        address, CMD_TIGHTEN_UP_ENABLE, (0x01 if enabled else 0x00,)
    )


def extrude_stage(target: Route, stage: int) -> bytes:
    if int(stage) not in (0, 4, 5, 6):
        raise ProtocolError("extrude_stage_not_qualified_on_K1")
    return application_frame(
        target.address,
        CMD_EXTRUDE_PROCESS,
        (target.mask, int(stage), 0x00),
    )


def retrude(target: Route, trigger: int) -> bytes:
    if int(trigger) not in (TRIGGER_BUFFER, TRIGGER_MATERIAL):
        raise ProtocolError("retrude_trigger_invalid")
    return application_frame(
        target.address, CMD_RETRUDE_PROCESS, (target.mask, int(trigger))
    )
