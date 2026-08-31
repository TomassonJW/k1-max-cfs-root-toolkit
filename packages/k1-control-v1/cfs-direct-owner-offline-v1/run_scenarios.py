#!/usr/bin/env python3
"""Qualification déterministe du propriétaire CFS sans imprimante ni pytest."""

from __future__ import annotations

import json
from pathlib import Path
import struct
import sys
from typing import Any, Callable, Dict, Iterable, List, Tuple


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import owner as owner_module  # type: ignore
import protocol  # type: ignore
import runtime_adapter  # type: ignore


TEMP = {
    "owner": "k1_control",
    "expected_c": 220.0,
    "target_c": 220.0,
    "actual_c": 219.5,
    "material_min_c": 200.0,
    "material_max_c": 240.0,
    "cfs_temperature_command": False,
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def response(frame: bytes, data: bytes = b"", status: int = 0) -> bytes:
    return protocol.wire_frame(frame[0], status, frame[3], data)


class ScriptedTransport:
    def __init__(self, plan: Iterable[Tuple[bytes, Any]]):
        self.plan = list(plan)
        self.calls: List[Tuple[bytes, float, bool]] = []

    def send(self, frame: bytes, timeout_s: float, retry: bool = False):
        frame = bytes(frame)
        self.calls.append((frame, float(timeout_s), retry))
        require(retry is False, "transport_retry_requested")
        require(bool(self.plan), "unexpected_frame_%r" % list(frame))
        expected, result = self.plan.pop(0)
        require(frame == expected, "frame_order_mismatch")
        if isinstance(result, Exception):
            raise result
        return result

    def done(self) -> None:
        require(self.plan == [], "planned_frames_not_consumed")


class SensorSequence:
    def __init__(self, values: Iterable[Any]):
        self.values = list(values)

    def __call__(self):
        require(bool(self.values), "unexpected_head_sensor_read")
        return self.values.pop(0)

    def done(self) -> None:
        require(self.values == [], "head_sensor_values_not_consumed")


def ok_plan(frames_and_data: Iterable[Tuple[bytes, bytes]]):
    return [(frame, response(frame, data)) for frame, data in frames_and_data]


def successful_load_plan(route_value: str = "T1A", pushes: int = 1):
    target = protocol.route(route_value)
    items = [
        (protocol.get_material_sensor(target), bytes((target.mask,))),
        (protocol.set_feed_mode(target), b""),
        (protocol.tighten(1, True), b""),
        (protocol.tighten(2, True), b""),
        (protocol.extrude_stage(target, 0), b""),
        (protocol.extrude_stage(target, 4), b""),
    ]
    for index in range(pushes):
        items.append(
            (
                protocol.extrude_stage(target, 5),
                struct.pack(">f", float(index + 1) / 10.0),
            )
        )
    items.extend(
        [
            (protocol.extrude_stage(target, 6), b""),
            (protocol.get_buffer_state(target), b"\x00"),
            (protocol.set_print_mode(target), b""),
            (protocol.tighten(1, False), b""),
            (protocol.tighten(2, False), b""),
        ]
    )
    return ok_plan(items)


def successful_unload_plan(route_value: str = "T1A"):
    target = protocol.route(route_value)
    return ok_plan(
        [
            (protocol.set_feed_mode(target), b""),
            (protocol.retrude(target, protocol.TRIGGER_BUFFER), b""),
            (protocol.retrude(target, protocol.TRIGGER_MATERIAL), b""),
        ]
    )


def successful_load_tail_recovery_plan(route_value: str = "T1A"):
    target = protocol.route(route_value)
    return ok_plan(
        [
            (protocol.get_material_sensor(target), bytes((target.mask,))),
            (protocol.set_feed_mode(target), b""),
            (protocol.tighten(1, True), b""),
            (protocol.tighten(2, True), b""),
            (protocol.extrude_stage(target, 4), b""),
            (protocol.extrude_stage(target, 6), b""),
            (protocol.get_buffer_state(target), b"\x00"),
            (protocol.set_print_mode(target), b""),
            (protocol.tighten(1, False), b""),
            (protocol.tighten(2, False), b""),
        ]
    )


def successful_takeover_finalize_plan(route_value: str = "T1A"):
    target = protocol.route(route_value)
    return ok_plan(
        [
            (protocol.get_material_sensor(target), bytes((target.mask,))),
            (protocol.get_buffer_state(target), b"\x00"),
            (protocol.set_print_mode(target), b""),
        ]
    )


def scenario_protocol_exact_vectors() -> None:
    target = protocol.route("T1A")
    require(
        protocol.set_feed_mode(target) == bytes((1, 5, 255, 4, 0, 1)),
        "feed_frame_mismatch",
    )
    require(
        protocol.extrude_stage(target, 5)
        == bytes((1, 6, 255, 16, 1, 5, 0)),
        "load_frame_mismatch",
    )
    require(
        protocol.retrude(target, 0) == bytes((1, 5, 255, 17, 1, 0)),
        "unload_frame_mismatch",
    )
    require(
        protocol.wire_frame(1, 0, 8, (9,))
        == bytes.fromhex("f7 01 04 00 08 09 cf"),
        "material_response_crc_mismatch",
    )
    require(
        protocol.wire_frame(1, 0, 17)
        == bytes.fromhex("f7 01 03 00 11 ca"),
        "unload_response_crc_mismatch",
    )


def scenario_protocol_rejects_corruption() -> None:
    cases = [
        (b"\x00\x01\x03\x00\x11\xca", "response_head_invalid"),
        (b"\xf7\x01\x03\x00\x11\x00", "response_crc_invalid"),
        (b"\xf7\x01\x04\x00\x11\xca", "response_length_mismatch"),
    ]
    for raw, expected in cases:
        try:
            protocol.parse_response(raw, 1, 17)
        except protocol.ProtocolError as error:
            require(error.code == expected, "wrong_protocol_error")
        else:
            raise AssertionError("corrupt_response_accepted")


def scenario_transport_exact_interface() -> None:
    class SerialObject:
        def __init__(self):
            self.args = None

        def cmd_send_data_with_response(self, frame, timeout_s, retry):
            self.args = (frame, timeout_s, retry)
            return bytes.fromhex("f7 01 03 00 11 ca")

    serial = SerialObject()
    adapter = runtime_adapter.StockSerial485Transport(serial)
    frame = protocol.retrude(protocol.route("T1A"), 0)
    require(adapter.send(frame, 20.0, False)[-1] == 0xCA, "adapter_response")
    require(serial.args == (frame, 20.0, False), "adapter_call_mismatch")
    try:
        adapter.send(frame, 20.0, True)
    except runtime_adapter.TransportAdapterError as error:
        require(str(error) == "transport_retry_forbidden", "adapter_retry_code")
    else:
        raise AssertionError("adapter_retry_accepted")


def scenario_load_t1a() -> None:
    transport = ScriptedTransport(successful_load_plan(pushes=2))
    head_sensor = SensorSequence((False, False, True, True))
    after_cutter_sensor = SensorSequence((False, True))
    owner = owner_module.DirectCfsOwner(
        transport, head_sensor, after_cutter_sensor, max_pushes=3
    )
    result = owner.load("T1A", "load-t1a", TEMP)
    require(result["phase"] == "loaded", "load_phase")
    require(result["active_route"] == "T1A", "load_route")
    require(result["trace"][-1]["push_count"] == 2, "load_push_count")
    require(result["automatic_retry_count"] == 0, "load_retry_count")
    require(result["temperature_commands"] == [], "hidden_temperature")
    require(result["geometry_commands"] == [], "hidden_geometry")
    require(result["mesh_commands"] == [], "hidden_mesh")
    transport.done()
    head_sensor.done()
    after_cutter_sensor.done()


def scenario_load_t2d() -> None:
    transport = ScriptedTransport(successful_load_plan("T2D"))
    head_sensor = SensorSequence((False, True, True))
    after_cutter_sensor = SensorSequence((False, True))
    owner = owner_module.DirectCfsOwner(
        transport, head_sensor, after_cutter_sensor
    )
    result = owner.load("T2D", "load-t2d", TEMP)
    require(result["active_route"] == "T2D", "second_box_route")
    require(
        protocol.set_print_mode(protocol.route("T2D"))
        in [item[0] for item in transport.calls],
        "second_box_mask",
    )
    transport.done()
    head_sensor.done()
    after_cutter_sensor.done()


def _load_failure_prefix(target):
    return ok_plan(
        [
            (protocol.get_material_sensor(target), bytes((target.mask,))),
            (protocol.set_feed_mode(target), b""),
            (protocol.tighten(1, True), b""),
            (protocol.tighten(2, True), b""),
            (protocol.extrude_stage(target, 0), b""),
            (protocol.extrude_stage(target, 4), b""),
        ]
    )


def scenario_status_error_no_retry() -> None:
    target = protocol.route("T1A")
    stage = protocol.extrude_stage(target, 5)
    plan = _load_failure_prefix(target)
    plan.append((stage, response(stage, status=0x0C)))
    plan.extend(
        ok_plan(
            [(protocol.tighten(1, False), b""), (protocol.tighten(2, False), b"")]
        )
    )
    transport = ScriptedTransport(plan)
    result = owner_module.DirectCfsOwner(
        transport, SensorSequence((False,)), SensorSequence((False,))
    ).load("T1A", "load-status", TEMP)
    require(result["failure_code"] == "cfs_status_0c_cmd_10", "status_code")
    require([item[0] for item in transport.calls].count(stage) == 1, "status_retry")
    transport.done()


def scenario_err8_tail_recovery_has_no_stage5() -> None:
    target = protocol.route("T1A")
    transport = ScriptedTransport(successful_load_tail_recovery_plan())
    owner = owner_module.DirectCfsOwner(
        transport,
        SensorSequence((True, True)),
        SensorSequence((True, True)),
    )
    owner.retained_head_segment = True
    result = owner.recover_load_tail("T1A", "recover-err8-tail", TEMP)
    sent = [item[0] for item in transport.calls]
    require(result["phase"] == "loaded", "tail_recovery_phase")
    require(result["active_route"] == "T1A", "tail_recovery_route")
    require(result["load_tail_recovery_count"] == 1, "tail_recovery_count")
    require(result["retained_head_segment"] is False, "tail_segment_not_consumed")
    require(protocol.extrude_stage(target, 0) not in sent, "tail_sent_stage0")
    require(protocol.extrude_stage(target, 5) not in sent, "tail_sent_stage5")
    require(sent.count(protocol.extrude_stage(target, 4)) == 1, "tail_stage4_count")
    require(sent.count(protocol.extrude_stage(target, 6)) == 1, "tail_stage6_count")
    require(result["automatic_retry_count"] == 0, "tail_automatic_retry")
    transport.done()


def scenario_err8_tail_recovery_requires_both_sensors() -> None:
    owner = owner_module.DirectCfsOwner(
        ScriptedTransport([]),
        SensorSequence((True,)),
        SensorSequence((False,)),
    )
    owner.retained_head_segment = True
    result = owner.recover_load_tail("T1A", "recover-missing-sensor", TEMP)
    require(
        result["failure_code"] == "load_tail_sensor_proof_missing",
        "tail_sensor_gate",
    )
    require(result["frames"] == [], "tail_sensor_gate_sent_frame")


def scenario_takeover_finalize_reads_then_latches_without_motor() -> None:
    target = protocol.route("T1A")
    transport = ScriptedTransport(successful_takeover_finalize_plan())
    owner = owner_module.DirectCfsOwner(
        transport,
        SensorSequence((True,)),
        SensorSequence((True,)),
    )
    owner.retained_head_segment = True
    result = owner.finalize_load_takeover("T1A", "finalize-takeover")
    sent = [item[0] for item in transport.calls]
    assert result["phase"] == "loaded"
    assert result["active_route"] == "T1A"
    assert result["last_buffer_state"] == 0
    assert result["takeover_finalize_count"] == 1
    assert result["retained_head_segment"] is False
    assert protocol.extrude_stage(target, 0) not in sent
    assert protocol.extrude_stage(target, 4) not in sent
    assert protocol.extrude_stage(target, 5) not in sent
    assert protocol.extrude_stage(target, 6) not in sent
    transport.done()


def scenario_takeover_finalize_refuses_nonmiddle_buffer() -> None:
    target = protocol.route("T1A")
    transport = ScriptedTransport(
        ok_plan(
            [
                (protocol.get_material_sensor(target), bytes((target.mask,))),
                (protocol.get_buffer_state(target), b"\x01"),
            ]
        )
    )
    owner = owner_module.DirectCfsOwner(
        transport,
        SensorSequence((True,)),
        SensorSequence((True,)),
    )
    owner.retained_head_segment = True
    result = owner.finalize_load_takeover("T1A", "finalize-buffer-one")
    assert result["failure_code"] == "buffer_not_middle_after_takeover"
    assert result["active_route"] is None
    assert result["last_buffer_state"] == 1
    assert protocol.set_print_mode(target) not in [item[0] for item in transport.calls]
    transport.done()


def scenario_timeout_no_retry() -> None:
    target = protocol.route("T1A")
    stage = protocol.extrude_stage(target, 5)
    plan = _load_failure_prefix(target)
    plan.append((stage, None))
    plan.extend(
        ok_plan(
            [(protocol.tighten(1, False), b""), (protocol.tighten(2, False), b"")]
        )
    )
    transport = ScriptedTransport(plan)
    result = owner_module.DirectCfsOwner(
        transport, SensorSequence((False,)), SensorSequence((False,))
    ).load("T1A", "load-timeout", TEMP)
    require(result["failure_code"] == "transport_timeout_cmd_10", "timeout_code")
    require([item[0] for item in transport.calls].count(stage) == 1, "timeout_retry")
    transport.done()


def scenario_disable_tension_no_retry() -> None:
    plan = successful_load_plan()
    first_disable = plan[-2][0]
    second_disable = plan[-1][0]
    plan[-2] = (first_disable, response(first_disable, status=0x0C))
    transport = ScriptedTransport(plan)
    result = owner_module.DirectCfsOwner(
        transport,
        SensorSequence((False, True, True)),
        SensorSequence((False, True)),
    ).load("T1A", "disable-ko", TEMP)
    sent = [item[0] for item in transport.calls]
    require(result["failure_code"] == "tension_disable_not_proven", "disable_code")
    require(sent.count(first_disable) == 1, "disable_first_retried")
    require(sent.count(second_disable) == 1, "disable_second_count")
    transport.done()


def scenario_missing_material() -> None:
    target = protocol.route("T1A")
    frame = protocol.get_material_sensor(target)
    transport = ScriptedTransport([(frame, response(frame, b"\x08"))])
    result = owner_module.DirectCfsOwner(
        transport, SensorSequence((False,)), SensorSequence((False,))
    ).load("T1A", "missing-material", TEMP)
    require(result["failure_code"] == "target_slot_has_no_material", "slot_gate")
    require(result["frames"] == [list(frame)], "motor_started_on_empty_slot")
    transport.done()


def scenario_head_must_start_clear() -> None:
    result = owner_module.DirectCfsOwner(
        ScriptedTransport([]), SensorSequence((True,)), SensorSequence(())
    ).load("T1A", "head-occupied", TEMP)
    require(result["failure_code"] == "head_path_not_clear_before_load", "head_gate")
    require(result["frames"] == [], "frame_sent_with_occupied_head")


def scenario_pushes_are_bounded() -> None:
    target = protocol.route("T1A")
    plan = _load_failure_prefix(target)
    plan.extend(
        ok_plan(
            [
                (protocol.extrude_stage(target, 5), struct.pack(">f", 0.1)),
                (protocol.extrude_stage(target, 5), struct.pack(">f", 0.2)),
                (protocol.tighten(1, False), b""),
                (protocol.tighten(2, False), b""),
            ]
        )
    )
    transport = ScriptedTransport(plan)
    result = owner_module.DirectCfsOwner(
        transport,
        SensorSequence((False, False, False)),
        SensorSequence((False,)),
        max_pushes=2,
    ).load("T1A", "bounded-pushes", TEMP)
    require(result["failure_code"] == "head_sensor_not_reached", "push_bound")
    require(result["automatic_retry_count"] == 0, "push_retry")
    transport.done()


def temperature_scenario(change: Dict[str, Any], code: str) -> Callable[[], None]:
    def run() -> None:
        proof = dict(TEMP)
        proof.update(change)
        result = owner_module.DirectCfsOwner(
            ScriptedTransport([]), SensorSequence(()), SensorSequence(())
        ).load("T1A", "temperature-gate", proof)
        require(result["failure_code"] == code, "temperature_code")
        require(result["frames"] == [], "temperature_gate_sent_frame")

    return run


def scenario_unload_success() -> None:
    pulls = []
    transport = ScriptedTransport(successful_unload_plan())
    head_sensor = SensorSequence((True, True))
    after_cutter_sensor = SensorSequence((True, False))
    owner = owner_module.DirectCfsOwner(
        transport,
        head_sensor,
        after_cutter_sensor,
        tip_pull=lambda distance, velocity: pulls.append((distance, velocity)) or True,
        active_route="T1A",
    )
    result = owner.unload("T1A", "unload-ok", TEMP)
    require(result["phase"] == "idle", "unload_phase")
    require(result["active_route"] is None, "unload_route")
    require(result["retained_head_segment"] is True, "retained_head_segment")
    require(pulls == [(-20.0, 140.0)], "tip_pull_contract")
    require(result["automatic_retry_count"] == 0, "unload_retry")
    transport.done()
    head_sensor.done()
    after_cutter_sensor.done()


def scenario_unload_pull_failure() -> None:
    target = protocol.route("T1A")
    transport = ScriptedTransport(
        ok_plan(
            [
                (protocol.set_feed_mode(target), b""),
                (protocol.retrude(target, protocol.TRIGGER_BUFFER), b""),
            ]
        )
    )
    owner = owner_module.DirectCfsOwner(
        transport,
        SensorSequence((True,)),
        SensorSequence((True,)),
        tip_pull=lambda _distance, _velocity: False,
        active_route="T1A",
    )
    result = owner.unload("T1A", "unload-pull-ko", TEMP)
    require(result["failure_code"] == "tip_pull_not_proven", "pull_failure")
    require(result["active_route"] == "T1A", "pull_failure_route")
    transport.done()


def scenario_unload_timeout_no_retry() -> None:
    target = protocol.route("T1A")
    finish = protocol.retrude(target, protocol.TRIGGER_MATERIAL)
    plan = ok_plan(
        [
            (protocol.set_feed_mode(target), b""),
            (protocol.retrude(target, protocol.TRIGGER_BUFFER), b""),
        ]
    )
    plan.append((finish, None))
    transport = ScriptedTransport(plan)
    owner = owner_module.DirectCfsOwner(
        transport,
        SensorSequence((True,)),
        SensorSequence((True,)),
        tip_pull=lambda _distance, _velocity: True,
        active_route="T1A",
    )
    result = owner.unload("T1A", "unload-timeout", TEMP)
    require(result["failure_code"] == "transport_timeout_cmd_11", "unload_timeout")
    require([item[0] for item in transport.calls].count(finish) == 1, "unload_retry")
    transport.done()


def scenario_unload_upstream_sensor_stuck() -> None:
    transport = ScriptedTransport(successful_unload_plan())
    owner = owner_module.DirectCfsOwner(
        transport,
        SensorSequence((True, True)),
        SensorSequence((True, True)),
        tip_pull=lambda _distance, _velocity: True,
        active_route="T1A",
    )
    result = owner.unload("T1A", "unload-sensor", TEMP)
    require(
        result["failure_code"] == "after_cutter_sensor_not_cleared_after_unload",
        "unload_upstream_sensor_gate",
    )
    require(result["active_route"] == "T1A", "stuck_sensor_route")
    transport.done()


def scenario_two_cycles_and_once_only_ids() -> None:
    plan = (
        successful_load_plan()
        + successful_unload_plan()
        + successful_load_plan()
        + successful_unload_plan()
    )
    transport = ScriptedTransport(plan)
    head_sensor = SensorSequence(
        (False, True, True, True, True, True, True, True, True)
    )
    after_cutter_sensor = SensorSequence(
        (False, True, True, False, False, True, True, True, False)
    )
    owner = owner_module.DirectCfsOwner(
        transport,
        head_sensor,
        after_cutter_sensor,
        tip_pull=lambda _distance, _velocity: True,
    )
    require(owner.load("T1A", "load-1", TEMP)["phase"] == "loaded", "cycle1_load")
    first_unload = owner.unload("T1A", "unload-1", TEMP)
    require(first_unload["phase"] == "idle", "cycle1_unload")
    require(first_unload["retained_head_segment"] is True, "cycle1_segment")
    second_load = owner.load("T1A", "load-2", TEMP)
    require(second_load["phase"] == "loaded", "cycle2_load")
    require(second_load["retained_head_segment"] is False, "cycle2_segment_consumed")
    result = owner.unload("T1A", "unload-2", TEMP)
    require(result["phase"] == "idle", "cycle2_unload")
    require(result["tip_pull_count"] == 2, "multiple_cycle_pull_count")
    frame_count = len(result["frames"])
    duplicate = owner.load("T1A", "load-1", TEMP)
    require(duplicate["failure_code"] == "duplicate_effect_id", "duplicate_id")
    require(len(duplicate["frames"]) == frame_count, "duplicate_sent_frame")
    transport.done()
    head_sensor.done()
    after_cutter_sensor.done()


def scenario_invalid_route_closed() -> None:
    result = owner_module.DirectCfsOwner(
        ScriptedTransport([]), SensorSequence(()), SensorSequence(())
    ).load("T3A", "invalid-route", TEMP)
    require(result["phase"] == "failed_safe", "invalid_route_phase")
    require(result["failure_code"] == "route_box_out_of_scope", "invalid_route_code")
    require(result["frames"] == [], "invalid_route_frame")


def scenario_reconcile_lost_t1a_without_filament_effect() -> None:
    target = protocol.route("T1A")
    sensor_frame = protocol.get_material_sensor(target)
    transport = ScriptedTransport(
        [(sensor_frame, response(sensor_frame, bytes((target.mask,))))]
    )
    owner = owner_module.DirectCfsOwner(
        transport,
        SensorSequence((True,)),
        SensorSequence((True,)),
    )
    result = owner.reconcile_loaded("T1A", "reconcile-t1a")
    require(result["phase"] == "loaded", "reconcile_phase")
    require(result["active_route"] == "T1A", "reconcile_route")
    require(result["load_count"] == 0, "reconcile_counted_as_load")
    require(len(result["frames"]) == 1, "reconcile_effect_frame")
    require(
        result["trace"][-1]["kind"]
        == "route_reconciled_without_filament_effect",
        "reconcile_trace",
    )
    transport.done()


def scenario_reconcile_requires_both_path_sensors() -> None:
    transport = ScriptedTransport([])
    owner = owner_module.DirectCfsOwner(
        transport,
        SensorSequence((True,)),
        SensorSequence((False,)),
    )
    result = owner.reconcile_loaded("T1A", "reconcile-missing-sensor")
    require(
        result["failure_code"] == "reconcile_sensor_proof_missing",
        "reconcile_sensor_gate",
    )
    require(result["frames"] == [], "reconcile_query_sent_without_sensor_proof")
    transport.done()


SCENARIOS = [
    ("protocol_exact_vectors", scenario_protocol_exact_vectors),
    ("protocol_rejects_corruption", scenario_protocol_rejects_corruption),
    ("transport_exact_interface", scenario_transport_exact_interface),
    ("load_t1a", scenario_load_t1a),
    ("load_t2d", scenario_load_t2d),
    ("status_error_no_retry", scenario_status_error_no_retry),
    ("err8_tail_recovery_has_no_stage5", scenario_err8_tail_recovery_has_no_stage5),
    (
        "err8_tail_recovery_requires_both_sensors",
        scenario_err8_tail_recovery_requires_both_sensors,
    ),
    (
        "takeover_finalize_reads_then_latches_without_motor",
        scenario_takeover_finalize_reads_then_latches_without_motor,
    ),
    (
        "takeover_finalize_refuses_nonmiddle_buffer",
        scenario_takeover_finalize_refuses_nonmiddle_buffer,
    ),
    ("timeout_no_retry", scenario_timeout_no_retry),
    ("disable_tension_no_retry", scenario_disable_tension_no_retry),
    ("missing_material", scenario_missing_material),
    ("head_must_start_clear", scenario_head_must_start_clear),
    ("pushes_are_bounded", scenario_pushes_are_bounded),
    (
        "temperature_owner",
        temperature_scenario({"owner": "stock_cfs"}, "temperature_owner_invalid"),
    ),
    (
        "temperature_target",
        temperature_scenario({"target_c": 215.0}, "target_temperature_mismatch"),
    ),
    (
        "temperature_actual",
        temperature_scenario({"actual_c": 180.0}, "actual_temperature_not_ready"),
    ),
    (
        "temperature_hidden_cfs",
        temperature_scenario(
            {"cfs_temperature_command": True},
            "cfs_temperature_command_forbidden",
        ),
    ),
    (
        "temperature_type",
        temperature_scenario(
            {"cfs_temperature_command": "false"}, "temperature_proof_invalid"
        ),
    ),
    ("unload_success", scenario_unload_success),
    ("unload_pull_failure", scenario_unload_pull_failure),
    ("unload_timeout_no_retry", scenario_unload_timeout_no_retry),
    ("unload_upstream_sensor_stuck", scenario_unload_upstream_sensor_stuck),
    ("two_cycles_and_once_only_ids", scenario_two_cycles_and_once_only_ids),
    ("invalid_route_closed", scenario_invalid_route_closed),
    (
        "reconcile_lost_t1a_without_filament_effect",
        scenario_reconcile_lost_t1a_without_filament_effect,
    ),
    ("reconcile_requires_both_path_sensors", scenario_reconcile_requires_both_path_sensors),
]


def run_all() -> Dict[str, Any]:
    results = []
    for name, scenario in SCENARIOS:
        try:
            scenario()
        except Exception as error:
            results.append(
                {
                    "name": name,
                    "status": "KO",
                    "error": "%s: %s" % (type(error).__name__, error),
                }
            )
        else:
            results.append({"name": name, "status": "OK"})
    ok_count = sum(item["status"] == "OK" for item in results)
    return {
        "schema": 1,
        "status": "OK" if ok_count == len(results) else "KO",
        "scenario_count": len(results),
        "ok_count": ok_count,
        "ko_count": len(results) - ok_count,
        "physical_action": False,
        "printer_transport": False,
        "deployment_candidate": False,
        "results": results,
    }


if __name__ == "__main__":
    report = run_all()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if report["status"] != "OK":
        raise SystemExit(1)
    print("CFS_DIRECT_OWNER_OFFLINE_V1_OK %d/%d" % (
        report["ok_count"], report["scenario_count"]
    ))
