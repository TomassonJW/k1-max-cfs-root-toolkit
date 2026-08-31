from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import struct
import sys
import types

import pytest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "cfs-direct-owner-offline-v1"
PACKAGE_NAME = "cfs_direct_owner_offline_v1"


def _load(name, filename):
    spec = spec_from_file_location(name, PACKAGE / filename)
    module = module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


if PACKAGE_NAME not in sys.modules:
    package_module = types.ModuleType(PACKAGE_NAME)
    package_module.__path__ = [str(PACKAGE)]
    sys.modules[PACKAGE_NAME] = package_module

protocol = _load(PACKAGE_NAME + ".protocol", "protocol.py")
owner_module = _load(PACKAGE_NAME + ".owner", "owner.py")
adapter_module = _load(PACKAGE_NAME + ".runtime_adapter", "runtime_adapter.py")


TEMP = {
    "owner": "k1_control",
    "expected_c": 220.0,
    "target_c": 220.0,
    "actual_c": 219.5,
    "material_min_c": 200.0,
    "material_max_c": 240.0,
    "cfs_temperature_command": False,
}


def response(frame, data=b"", status=0):
    return protocol.wire_frame(frame[0], status, frame[3], data)


class ScriptedTransport:
    def __init__(self, plan):
        self.plan = list(plan)
        self.calls = []

    def send(self, frame, timeout_s, retry=False):
        frame = bytes(frame)
        self.calls.append((frame, float(timeout_s), retry))
        assert retry is False
        assert self.plan, "trame CFS non prévue: %r" % list(frame)
        expected, result = self.plan.pop(0)
        assert frame == expected
        if isinstance(result, Exception):
            raise result
        return result

    def assert_done(self):
        assert self.plan == []


class SensorSequence:
    def __init__(self, values):
        self.values = list(values)

    def __call__(self):
        assert self.values, "lecture du capteur de tête non prévue"
        return self.values.pop(0)

    def assert_done(self):
        assert self.values == []


def ok_plan(frames_and_data):
    return [(frame, response(frame, data)) for frame, data in frames_and_data]


def successful_load_plan(route_value="T1A", material_mask=None, pushes=1):
    target = protocol.route(route_value)
    if material_mask is None:
        material_mask = target.mask
    items = [
        (protocol.get_material_sensor(target), bytes((material_mask,))),
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


def successful_unload_plan(route_value="T1A"):
    target = protocol.route(route_value)
    return ok_plan(
        [
            (protocol.set_feed_mode(target), b""),
            (protocol.retrude(target, protocol.TRIGGER_BUFFER), b""),
            (protocol.retrude(target, protocol.TRIGGER_MATERIAL), b""),
        ]
    )


def test_protocol_matches_exact_k1_log_vectors():
    target = protocol.route("T1A")
    assert protocol.set_feed_mode(target) == bytes((1, 5, 255, 4, 0, 1))
    assert protocol.get_material_sensor(target) == bytes((1, 4, 255, 8, 0))
    assert protocol.extrude_stage(target, 5) == bytes((1, 6, 255, 16, 1, 5, 0))
    assert protocol.retrude(target, 0) == bytes((1, 5, 255, 17, 1, 0))
    assert protocol.wire_frame(1, 0, 8, (9,)) == bytes.fromhex(
        "f7 01 04 00 08 09 cf"
    )
    assert protocol.wire_frame(1, 0, 17) == bytes.fromhex("f7 01 03 00 11 ca")


@pytest.mark.parametrize(
    "raw,code",
    [
        (b"\x00\x01\x03\x00\x11\xca", "response_head_invalid"),
        (b"\xf7\x01\x03\x00\x11\x00", "response_crc_invalid"),
        (b"\xf7\x01\x04\x00\x11\xca", "response_length_mismatch"),
    ],
)
def test_protocol_rejects_malformed_responses(raw, code):
    with pytest.raises(protocol.ProtocolError) as caught:
        protocol.parse_response(raw, 1, 17)
    assert caught.value.code == code


def test_protocol_rejects_wrong_address_and_command():
    valid = protocol.wire_frame(2, 0, 17)
    with pytest.raises(protocol.ProtocolError, match="response_address_mismatch"):
        protocol.parse_response(valid, 1, 17)
    valid = protocol.wire_frame(1, 0, 16)
    with pytest.raises(protocol.ProtocolError, match="response_command_mismatch"):
        protocol.parse_response(valid, 1, 17)


def test_runtime_adapter_uses_exact_stock_interface_without_retry():
    class SerialObject:
        def __init__(self):
            self.args = None

        def cmd_send_data_with_response(self, frame, timeout_s, retry):
            self.args = (frame, timeout_s, retry)
            return bytes.fromhex("f7 01 03 00 11 ca")

    serial = SerialObject()
    adapter = adapter_module.StockSerial485Transport(serial)
    frame = protocol.retrude(protocol.route("T1A"), 0)
    assert adapter.send(frame, 20.0, retry=False) == bytes.fromhex(
        "f7 01 03 00 11 ca"
    )
    assert serial.args == (frame, 20.0, False)
    with pytest.raises(
        adapter_module.TransportAdapterError, match="transport_retry_forbidden"
    ):
        adapter.send(frame, 20.0, retry=True)


def test_load_t1a_uses_exact_order_and_reaches_loaded_state():
    transport = ScriptedTransport(successful_load_plan(pushes=2))
    head_sensor = SensorSequence((False, False, True, True))
    after_cutter_sensor = SensorSequence((False, True))
    owner = owner_module.DirectCfsOwner(
        transport, head_sensor, after_cutter_sensor, max_pushes=3
    )

    result = owner.load("T1A", "load-job-001", TEMP)

    assert result["phase"] == "loaded"
    assert result["active_route"] == "T1A"
    assert result["failure_code"] is None
    assert result["load_count"] == 1
    assert result["automatic_retry_count"] == 0
    assert result["temperature_commands"] == []
    assert result["geometry_commands"] == []
    assert result["mesh_commands"] == []
    assert result["purge_commands"] == []
    assert result["trace"][-1]["push_count"] == 2
    assert all(retry is False for _, _, retry in transport.calls)
    transport.assert_done()
    head_sensor.assert_done()
    after_cutter_sensor.assert_done()


def test_load_t2d_maps_second_box_and_slot_mask_eight():
    transport = ScriptedTransport(successful_load_plan("T2D", material_mask=8))
    head_sensor = SensorSequence((False, True, True))
    after_cutter_sensor = SensorSequence((False, True))
    owner = owner_module.DirectCfsOwner(
        transport, head_sensor, after_cutter_sensor
    )

    result = owner.load("T2D", "load-job-t2d", TEMP)

    assert result["phase"] == "loaded"
    assert result["active_route"] == "T2D"
    assert protocol.set_print_mode(protocol.route("T2D")) in [
        call[0] for call in transport.calls
    ]
    transport.assert_done()
    head_sensor.assert_done()
    after_cutter_sensor.assert_done()


def test_load_stops_on_cfs_status_without_retrying_stage_five():
    target = protocol.route("T1A")
    prefix = ok_plan(
        [
            (protocol.get_material_sensor(target), b"\x01"),
            (protocol.set_feed_mode(target), b""),
            (protocol.tighten(1, True), b""),
            (protocol.tighten(2, True), b""),
            (protocol.extrude_stage(target, 0), b""),
            (protocol.extrude_stage(target, 4), b""),
        ]
    )
    failed = protocol.extrude_stage(target, 5)
    cleanup = ok_plan(
        [(protocol.tighten(1, False), b""), (protocol.tighten(2, False), b"")]
    )
    transport = ScriptedTransport(
        prefix + [(failed, response(failed, status=0x0C))] + cleanup
    )
    owner = owner_module.DirectCfsOwner(
        transport, SensorSequence((False,)), SensorSequence((False,))
    )

    result = owner.load("T1A", "load-status-0c", TEMP)

    assert result["phase"] == "failed_safe"
    assert result["failure_code"] == "cfs_status_0c_cmd_10"
    assert [call[0] for call in transport.calls].count(failed) == 1
    assert result["automatic_retry_count"] == 0
    transport.assert_done()


def test_load_timeout_is_not_retried_and_tension_cleanup_is_attempted_once():
    target = protocol.route("T1A")
    prefix = ok_plan(
        [
            (protocol.get_material_sensor(target), b"\x01"),
            (protocol.set_feed_mode(target), b""),
            (protocol.tighten(1, True), b""),
            (protocol.tighten(2, True), b""),
            (protocol.extrude_stage(target, 0), b""),
            (protocol.extrude_stage(target, 4), b""),
        ]
    )
    push = protocol.extrude_stage(target, 5)
    disable_one = protocol.tighten(1, False)
    disable_two = protocol.tighten(2, False)
    transport = ScriptedTransport(
        prefix
        + [(push, None)]
        + ok_plan([(disable_one, b""), (disable_two, b"")])
    )
    owner = owner_module.DirectCfsOwner(
        transport, SensorSequence((False,)), SensorSequence((False,))
    )

    result = owner.load("T1A", "load-timeout", TEMP)

    sent = [call[0] for call in transport.calls]
    assert result["failure_code"] == "transport_timeout_cmd_10"
    assert sent.count(push) == 1
    assert sent.count(disable_one) == 1
    assert sent.count(disable_two) == 1
    transport.assert_done()


def test_tension_disable_failure_is_never_retried():
    plan = successful_load_plan()
    disable_one, _ = plan[-2]
    disable_two = plan[-1][0]
    plan[-2] = (disable_one, response(disable_one, status=0x0C))
    transport = ScriptedTransport(plan)
    owner = owner_module.DirectCfsOwner(
        transport,
        SensorSequence((False, True, True)),
        SensorSequence((False, True)),
    )

    result = owner.load("T1A", "load-disable-failure", TEMP)

    sent = [call[0] for call in transport.calls]
    assert result["phase"] == "failed_safe"
    assert result["active_route"] == "T1A"
    assert result["failure_code"] == "tension_disable_not_proven"
    assert sent.count(disable_one) == 1
    assert sent.count(disable_two) == 1
    assert result["cleanup_failures"] == ["cfs_status_0c_cmd_0f"]
    transport.assert_done()


def test_load_refuses_missing_material_before_any_motor_stage():
    target = protocol.route("T1A")
    sensor_frame = protocol.get_material_sensor(target)
    transport = ScriptedTransport([(sensor_frame, response(sensor_frame, b"\x08"))])
    owner = owner_module.DirectCfsOwner(
        transport, SensorSequence((False,)), SensorSequence((False,))
    )

    result = owner.load("T1A", "load-empty-slot", TEMP)

    assert result["failure_code"] == "target_slot_has_no_material"
    assert result["frames"] == [list(sensor_frame)]
    transport.assert_done()


def test_load_refuses_when_head_path_is_not_clear():
    transport = ScriptedTransport([])
    owner = owner_module.DirectCfsOwner(
        transport, SensorSequence((True,)), SensorSequence(())
    )

    result = owner.load("T1A", "load-head-occupied", TEMP)

    assert result["failure_code"] == "head_path_not_clear_before_load"
    assert result["frames"] == []
    transport.assert_done()


def test_load_stops_after_bounded_pushes_when_head_sensor_never_trips():
    target = protocol.route("T1A")
    plan = ok_plan(
        [
            (protocol.get_material_sensor(target), b"\x01"),
            (protocol.set_feed_mode(target), b""),
            (protocol.tighten(1, True), b""),
            (protocol.tighten(2, True), b""),
            (protocol.extrude_stage(target, 0), b""),
            (protocol.extrude_stage(target, 4), b""),
            (protocol.extrude_stage(target, 5), struct.pack(">f", 0.1)),
            (protocol.extrude_stage(target, 5), struct.pack(">f", 0.2)),
            (protocol.tighten(1, False), b""),
            (protocol.tighten(2, False), b""),
        ]
    )
    transport = ScriptedTransport(plan)
    owner = owner_module.DirectCfsOwner(
        transport,
        SensorSequence((False, False, False)),
        SensorSequence((False,)),
        max_pushes=2,
    )

    result = owner.load("T1A", "load-no-head", TEMP)

    assert result["failure_code"] == "head_sensor_not_reached"
    assert result["automatic_retry_count"] == 0
    transport.assert_done()


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"owner": "stock_cfs"}, "temperature_owner_invalid"),
        ({"target_c": 215.0}, "target_temperature_mismatch"),
        ({"actual_c": 180.0}, "actual_temperature_not_ready"),
        ({"cfs_temperature_command": True}, "cfs_temperature_command_forbidden"),
        ({"cfs_temperature_command": "false"}, "temperature_proof_invalid"),
    ],
)
def test_temperature_gate_refuses_before_any_cfs_frame(changes, code):
    proof = dict(TEMP)
    proof.update(changes)
    transport = ScriptedTransport([])
    owner = owner_module.DirectCfsOwner(
        transport, SensorSequence(()), SensorSequence(())
    )

    result = owner.load("T1A", "load-temperature-gate", proof)

    assert result["failure_code"] == code
    assert result["frames"] == []
    transport.assert_done()


def test_unload_uses_exact_order_and_one_local_pull():
    pulls = []
    transport = ScriptedTransport(successful_unload_plan())
    head_sensor = SensorSequence((True, False))
    after_cutter_sensor = SensorSequence((True, False))
    owner = owner_module.DirectCfsOwner(
        transport,
        head_sensor,
        after_cutter_sensor,
        tip_pull=lambda distance, velocity: pulls.append((distance, velocity)) or True,
        active_route="T1A",
    )

    result = owner.unload("T1A", "unload-job-001", TEMP)

    assert result["phase"] == "idle"
    assert result["active_route"] is None
    assert result["unload_count"] == 1
    assert result["tip_pull_count"] == 1
    assert pulls == [(-20.0, 140.0)]
    assert result["automatic_retry_count"] == 0
    transport.assert_done()
    head_sensor.assert_done()
    after_cutter_sensor.assert_done()


def test_unload_stops_if_local_pull_is_not_proven():
    target = protocol.route("T1A")
    plan = ok_plan(
        [
            (protocol.set_feed_mode(target), b""),
            (protocol.retrude(target, protocol.TRIGGER_BUFFER), b""),
        ]
    )
    transport = ScriptedTransport(plan)
    owner = owner_module.DirectCfsOwner(
        transport,
        SensorSequence((True,)),
        SensorSequence((True,)),
        tip_pull=lambda _distance, _velocity: False,
        active_route="T1A",
    )

    result = owner.unload("T1A", "unload-pull-ko", TEMP)

    assert result["failure_code"] == "tip_pull_not_proven"
    assert result["active_route"] == "T1A"
    assert result["tip_pull_count"] == 1
    transport.assert_done()


def test_unload_finish_timeout_is_not_retried():
    target = protocol.route("T1A")
    finish = protocol.retrude(target, protocol.TRIGGER_MATERIAL)
    plan = ok_plan(
        [
            (protocol.set_feed_mode(target), b""),
            (protocol.retrude(target, protocol.TRIGGER_BUFFER), b""),
        ]
    ) + [(finish, None)]
    transport = ScriptedTransport(plan)
    owner = owner_module.DirectCfsOwner(
        transport,
        SensorSequence((True,)),
        SensorSequence((True,)),
        tip_pull=lambda _distance, _velocity: True,
        active_route="T1A",
    )

    result = owner.unload("T1A", "unload-timeout", TEMP)

    assert result["failure_code"] == "transport_timeout_cmd_11"
    assert [call[0] for call in transport.calls].count(finish) == 1
    assert result["active_route"] == "T1A"
    transport.assert_done()


def test_unload_requires_head_sensor_to_clear():
    transport = ScriptedTransport(successful_unload_plan())
    owner = owner_module.DirectCfsOwner(
        transport,
        SensorSequence((True, True)),
        SensorSequence((True, False)),
        tip_pull=lambda _distance, _velocity: True,
        active_route="T1A",
    )

    result = owner.unload("T1A", "unload-sensor-stuck", TEMP)

    assert result["failure_code"] == "head_sensor_not_cleared_after_unload"
    assert result["active_route"] == "T1A"
    transport.assert_done()


def test_two_complete_cycles_are_allowed_but_effect_ids_are_once_only():
    plan = (
        successful_load_plan()
        + successful_unload_plan()
        + successful_load_plan()
        + successful_unload_plan()
    )
    transport = ScriptedTransport(plan)
    head_sensor = SensorSequence(
        (False, True, True, True, False, False, True, True, True, False)
    )
    after_cutter_sensor = SensorSequence(
        (False, True, True, False, False, True, True, False)
    )
    owner = owner_module.DirectCfsOwner(
        transport,
        head_sensor,
        after_cutter_sensor,
        tip_pull=lambda _distance, _velocity: True,
    )

    assert owner.load("T1A", "load-cycle-1", TEMP)["phase"] == "loaded"
    assert owner.unload("T1A", "unload-cycle-1", TEMP)["phase"] == "idle"
    assert owner.load("T1A", "load-cycle-2", TEMP)["phase"] == "loaded"
    result = owner.unload("T1A", "unload-cycle-2", TEMP)
    assert result["phase"] == "idle"
    assert result["load_count"] == 2
    assert result["unload_count"] == 2
    assert result["tip_pull_count"] == 2
    frame_count = len(result["frames"])

    duplicate = owner.load("T1A", "load-cycle-1", TEMP)
    assert duplicate["phase"] == "failed_safe"
    assert duplicate["failure_code"] == "duplicate_effect_id"
    assert len(duplicate["frames"]) == frame_count
    transport.assert_done()
    head_sensor.assert_done()
    after_cutter_sensor.assert_done()


def test_invalid_route_fails_closed_without_transport():
    transport = ScriptedTransport([])
    owner = owner_module.DirectCfsOwner(
        transport, SensorSequence(()), SensorSequence(())
    )

    result = owner.load("T3A", "invalid-route", TEMP)

    assert result["phase"] == "failed_safe"
    assert result["failure_code"] == "route_box_out_of_scope"
    assert result["frames"] == []
    transport.assert_done()


def test_reconcile_lost_t1a_uses_only_a_sensor_query():
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

    assert result["phase"] == "loaded"
    assert result["active_route"] == "T1A"
    assert result["load_count"] == 0
    assert result["frames"] == [list(sensor_frame)]
    assert result["trace"][-1]["kind"] == "route_reconciled_without_filament_effect"
    transport.assert_done()


def test_reconcile_requires_both_filament_path_sensors():
    transport = ScriptedTransport([])
    owner = owner_module.DirectCfsOwner(
        transport,
        SensorSequence((True,)),
        SensorSequence((False,)),
    )

    result = owner.reconcile_loaded("T1A", "reconcile-sensor-ko")

    assert result["phase"] == "failed_safe"
    assert result["failure_code"] == "reconcile_sensor_proof_missing"
    assert result["frames"] == []
    transport.assert_done()
