#!/usr/bin/env python3
"""Propriétaire CFS direct, pur et fermé au premier écart.

La classe ne chauffe pas, ne déplace pas les axes, ne touche pas au mesh et ne
se connecte à aucune imprimante. Le transport, le capteur de tête et l'unique
traction locale du retrait sont injectés. Cela permet de tester l'ordre exact
avant de fabriquer un connecteur Klipper séparé.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
import struct
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Set

try:
    from . import protocol
except ImportError:  # chargement direct par les tests du dépôt
    import protocol  # type: ignore


SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")


class OwnerError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class TemperatureProof:
    owner: str
    expected_c: float
    target_c: float
    actual_c: float
    material_min_c: float
    material_max_c: float
    cfs_temperature_command: bool

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "TemperatureProof":
        if not hasattr(value, "get"):
            raise OwnerError("temperature_proof_invalid")
        raw_cfs_temperature_command = value.get("cfs_temperature_command")
        if not isinstance(raw_cfs_temperature_command, bool):
            raise OwnerError("temperature_proof_invalid")
        try:
            result = cls(
                owner=str(value.get("owner", "")),
                expected_c=float(value.get("expected_c")),
                target_c=float(value.get("target_c")),
                actual_c=float(value.get("actual_c")),
                material_min_c=float(value.get("material_min_c")),
                material_max_c=float(value.get("material_max_c")),
                cfs_temperature_command=raw_cfs_temperature_command,
            )
        except (TypeError, ValueError):
            raise OwnerError("temperature_proof_invalid")
        if not all(
            math.isfinite(item)
            for item in (
                result.expected_c,
                result.target_c,
                result.actual_c,
                result.material_min_c,
                result.material_max_c,
            )
        ):
            raise OwnerError("temperature_proof_invalid")
        if result.owner != "k1_control":
            raise OwnerError("temperature_owner_invalid")
        if result.cfs_temperature_command:
            raise OwnerError("cfs_temperature_command_forbidden")
        if not 170.0 <= result.material_min_c <= result.material_max_c <= 320.0:
            raise OwnerError("material_temperature_bounds_invalid")
        if not result.material_min_c <= result.expected_c <= result.material_max_c:
            raise OwnerError("expected_temperature_out_of_bounds")
        if abs(result.target_c - result.expected_c) > 0.5:
            raise OwnerError("target_temperature_mismatch")
        if abs(result.actual_c - result.expected_c) > 5.0:
            raise OwnerError("actual_temperature_not_ready")
        return result


class DirectCfsOwner:
    """Séquence chargement/retrait sans retry automatique.

    Le transport doit offrir `send(frame, timeout_s, retry=False)`. La trame
    donnée au transport est la trame applicative exacte observée sur la K1.
    """

    def __init__(
        self,
        transport,
        head_sensor: Callable[[], bool],
        after_cutter_sensor: Callable[[], bool],
        tip_pull: Optional[Callable[[float, float], bool]] = None,
        connected_boxes: Iterable[int] = (1, 2),
        active_route: Optional[str] = None,
        max_pushes: int = 8,
    ) -> None:
        if not callable(head_sensor):
            raise OwnerError("head_sensor_owner_missing")
        if not callable(after_cutter_sensor):
            raise OwnerError("after_cutter_sensor_owner_missing")
        if tip_pull is not None and not callable(tip_pull):
            raise OwnerError("tip_pull_owner_invalid")
        self.transport = transport
        self.head_sensor = head_sensor
        self.after_cutter_sensor = after_cutter_sensor
        self.tip_pull = tip_pull
        self.connected_boxes = tuple(sorted(set(int(x) for x in connected_boxes)))
        if not self.connected_boxes or any(x < 1 or x > 2 for x in self.connected_boxes):
            raise OwnerError("connected_boxes_invalid")
        self.max_pushes = int(max_pushes)
        if not 1 <= self.max_pushes <= 20:
            raise OwnerError("max_pushes_invalid")
        self.active_route = (
            protocol.route(active_route).logical if active_route is not None else None
        )
        self.phase = "loaded" if self.active_route else "idle"
        self.failure_code: Optional[str] = None
        self.used_effect_ids: Set[str] = set()
        self.frames: List[List[int]] = []
        self.trace: List[Dict[str, Any]] = []
        self.automatic_retry_count = 0
        self.tip_pull_count = 0
        self.load_count = 0
        self.load_tail_recovery_count = 0
        self.takeover_finalize_count = 0
        self.last_buffer_state: Optional[int] = None
        self.unload_count = 0
        self.retained_head_segment = False
        self.cleanup_failures: List[str] = []

    def result(self) -> Dict[str, Any]:
        return {
            "phase": self.phase,
            "failure_code": self.failure_code,
            "active_route": self.active_route,
            "effect_ids": sorted(self.used_effect_ids),
            "frames": [list(item) for item in self.frames],
            "trace": list(self.trace),
            "automatic_retry_count": self.automatic_retry_count,
            "tip_pull_count": self.tip_pull_count,
            "load_count": self.load_count,
            "load_tail_recovery_count": self.load_tail_recovery_count,
            "takeover_finalize_count": self.takeover_finalize_count,
            "last_buffer_state": self.last_buffer_state,
            "unload_count": self.unload_count,
            "retained_head_segment": self.retained_head_segment,
            "cleanup_failures": list(self.cleanup_failures),
            "temperature_commands": [],
            "geometry_commands": [],
            "mesh_commands": [],
            "purge_commands": [],
            "printer_transport": False,
            "physical_action": False,
            "deployment_candidate": False,
        }

    def load(
        self,
        logical_route: str,
        effect_id: str,
        temperature: Mapping[str, Any],
    ) -> Dict[str, Any]:
        try:
            target = protocol.route(logical_route)
        except protocol.ProtocolError as error:
            self._fail(error.code)
            return self.result()
        tension_enabled: Set[int] = set()
        tension_disable_attempted: Set[int] = set()
        route_latched = False
        try:
            self._begin("idle", "loading", effect_id)
            TemperatureProof.from_mapping(temperature)
            if target.address not in self.connected_boxes:
                raise OwnerError("target_box_not_connected")
            head_present_before_load = self._read_head_sensor()
            if head_present_before_load and not self.retained_head_segment:
                raise OwnerError("head_path_not_clear_before_load")
            if self._read_after_cutter_sensor():
                raise OwnerError("after_cutter_path_not_clear_before_load")

            sensor = self._send_ok(protocol.get_material_sensor(target), 2.0)
            if len(sensor.data) != 1:
                raise OwnerError("material_sensor_response_invalid")
            if sensor.data[0] & target.mask == 0:
                raise OwnerError("target_slot_has_no_material")

            self._send_ok(protocol.set_feed_mode(target), 2.0)
            for address in self.connected_boxes:
                # Un timeout après l'envoi laisse l'effet réel inconnu. L'adresse
                # est donc considérée tendue avant même de lire la réponse.
                tension_enabled.add(address)
                self._send_ok(protocol.tighten(address, True), 2.0)

            self._send_ok(protocol.extrude_stage(target, 0), 15.0)
            self._send_ok(protocol.extrude_stage(target, 4), 15.0)

            wheel_values: List[float] = []
            reached = False
            for _ in range(self.max_pushes):
                response = self._send_ok(protocol.extrude_stage(target, 5), 15.0)
                if len(response.data) != 4:
                    raise OwnerError("load_push_response_invalid")
                wheel = struct.unpack(">f", response.data)[0]
                if not math.isfinite(wheel):
                    raise OwnerError("load_wheel_value_invalid")
                wheel_values.append(wheel)
                reached_sensor = (
                    self._read_after_cutter_sensor()
                    if self.retained_head_segment
                    else self._read_head_sensor()
                )
                if reached_sensor:
                    reached = True
                    break
            if not reached:
                raise OwnerError(
                    "after_cutter_sensor_not_reached"
                    if self.retained_head_segment
                    else "head_sensor_not_reached"
                )

            self._send_ok(protocol.extrude_stage(target, 6), 15.0)
            if not self._read_head_sensor():
                raise OwnerError("head_sensor_lost_after_load")
            if not self._read_after_cutter_sensor():
                raise OwnerError("after_cutter_sensor_not_reached")
            buffer_response = self._send_ok(protocol.get_buffer_state(target), 2.0)
            if buffer_response.data != bytes((0x00,)):
                raise OwnerError("buffer_not_middle_after_load")
            self._send_ok(protocol.set_print_mode(target), 2.0)
            route_latched = True
            self.active_route = target.logical
            self.retained_head_segment = False

            self._disable_tension(
                tension_enabled,
                tension_disable_attempted,
                strict=True,
            )
            self.load_count += 1
            self.phase = "loaded"
            self.trace.append(
                {
                    "kind": "load_complete",
                    "route": target.logical,
                    "push_count": len(wheel_values),
                    "wheel_values": wheel_values,
                }
            )
        except (OwnerError, protocol.ProtocolError) as error:
            code = getattr(error, "code", str(error))
            if route_latched:
                self.active_route = target.logical
            self._fail(code)
        finally:
            if tension_enabled:
                self._disable_tension(
                    tension_enabled,
                    tension_disable_attempted,
                    strict=False,
                )
        return self.result()

    def recover_load_tail(
        self,
        logical_route: str,
        effect_id: str,
        temperature: Mapping[str, Any],
    ) -> Dict[str, Any]:
        """Termine une insertion deja arrivee aux deux capteurs.

        Cette reprise correspond uniquement a la fin stock observee apres
        ``EXTRUDE_ERR8`` : elle ne renvoie ni stage 0 ni stage 5. Elle retend
        les CFS apres un restart, envoie une fois stage 4 puis stage 6, prouve
        les deux capteurs et verrouille la route.
        """

        try:
            target = protocol.route(logical_route)
        except protocol.ProtocolError as error:
            self._fail(error.code)
            return self.result()
        tension_enabled: Set[int] = set()
        tension_disable_attempted: Set[int] = set()
        route_latched = False
        try:
            self._begin("idle", "recovering_load_tail", effect_id)
            TemperatureProof.from_mapping(temperature)
            if target.address not in self.connected_boxes:
                raise OwnerError("target_box_not_connected")
            if not self.retained_head_segment:
                raise OwnerError("load_tail_retained_segment_not_adopted")
            if not self._read_head_sensor() or not self._read_after_cutter_sensor():
                raise OwnerError("load_tail_sensor_proof_missing")

            sensor = self._send_ok(protocol.get_material_sensor(target), 2.0)
            if len(sensor.data) != 1:
                raise OwnerError("material_sensor_response_invalid")
            if sensor.data[0] & target.mask == 0:
                raise OwnerError("target_slot_has_no_material")

            self._send_ok(protocol.set_feed_mode(target), 2.0)
            for address in self.connected_boxes:
                tension_enabled.add(address)
                self._send_ok(protocol.tighten(address, True), 2.0)

            # Fin exacte vue dans la reprise stock EXTRUDE_ERR8. Aucun stage 5
            # n'est permis ici : le filament a deja atteint la tete.
            self._send_ok(protocol.extrude_stage(target, 4), 15.0)
            self._send_ok(protocol.extrude_stage(target, 6), 15.0)
            if not self._read_head_sensor() or not self._read_after_cutter_sensor():
                raise OwnerError("load_tail_sensor_proof_lost")
            buffer_response = self._send_ok(protocol.get_buffer_state(target), 2.0)
            if buffer_response.data != bytes((0x00,)):
                raise OwnerError("buffer_not_middle_after_load")
            self._send_ok(protocol.set_print_mode(target), 2.0)
            route_latched = True
            self.active_route = target.logical
            self.retained_head_segment = False

            self._disable_tension(
                tension_enabled,
                tension_disable_attempted,
                strict=True,
            )
            self.load_count += 1
            self.load_tail_recovery_count += 1
            self.phase = "loaded"
            self.trace.append(
                {
                    "kind": "load_tail_recovery_complete",
                    "route": target.logical,
                    "stages": [4, 6],
                    "stage5_count": 0,
                    "automatic_retry": False,
                }
            )
        except (OwnerError, protocol.ProtocolError) as error:
            code = getattr(error, "code", str(error))
            if route_latched:
                self.active_route = target.logical
            self._fail(code)
        finally:
            if tension_enabled:
                self._disable_tension(
                    tension_enabled,
                    tension_disable_attempted,
                    strict=False,
                )
        return self.result()

    def finalize_load_takeover(
        self,
        logical_route: str,
        effect_id: str,
    ) -> Dict[str, Any]:
        """Verrouille une route déjà prise localement, sans moteur filament.

        La méthode lit le slot et le buffer une fois. Elle n'envoie le mode
        impression que si les deux capteurs sont présents et si le buffer est
        revenu exactement au milieu (0).
        """

        try:
            target = protocol.route(logical_route)
        except protocol.ProtocolError as error:
            self._fail(error.code)
            return self.result()
        try:
            self._begin("idle", "finalizing_load_takeover", effect_id)
            if target.address not in self.connected_boxes:
                raise OwnerError("target_box_not_connected")
            if not self.retained_head_segment:
                raise OwnerError("takeover_segment_state_not_adopted")
            if not self._read_head_sensor() or not self._read_after_cutter_sensor():
                raise OwnerError("takeover_sensor_proof_missing")

            sensor = self._send_ok(protocol.get_material_sensor(target), 2.0)
            if len(sensor.data) != 1:
                raise OwnerError("material_sensor_response_invalid")
            if sensor.data[0] & target.mask == 0:
                raise OwnerError("target_slot_has_no_material")
            buffer_response = self._send_ok(protocol.get_buffer_state(target), 2.0)
            if len(buffer_response.data) != 1:
                raise OwnerError("buffer_state_response_invalid")
            self.last_buffer_state = int(buffer_response.data[0])
            if self.last_buffer_state != 0:
                raise OwnerError("buffer_not_middle_after_takeover")

            self._send_ok(protocol.set_print_mode(target), 2.0)
            self.active_route = target.logical
            self.retained_head_segment = False
            self.load_count += 1
            self.takeover_finalize_count += 1
            self.phase = "loaded"
            self.trace.append(
                {
                    "kind": "load_takeover_finalized",
                    "route": target.logical,
                    "buffer_state": self.last_buffer_state,
                    "motor_frame_count": 0,
                    "automatic_retry": False,
                }
            )
        except (OwnerError, protocol.ProtocolError) as error:
            self._fail(getattr(error, "code", str(error)))
        return self.result()

    def reconcile_loaded(
        self,
        logical_route: str,
        observation_id: str,
    ) -> Dict[str, Any]:
        """Réassocie une route perdue sans commander de moteur filament."""

        try:
            target = protocol.route(logical_route)
        except protocol.ProtocolError as error:
            self._fail(error.code)
            return self.result()
        try:
            self._begin("idle", "reconciling", observation_id)
            if target.address not in self.connected_boxes:
                raise OwnerError("target_box_not_connected")
            head_present = self._read_head_sensor()
            after_cutter_present = self._read_after_cutter_sensor()
            if not head_present or not after_cutter_present:
                raise OwnerError("reconcile_sensor_proof_missing")
            sensor = self._send_ok(protocol.get_material_sensor(target), 2.0)
            if len(sensor.data) != 1:
                raise OwnerError("material_sensor_response_invalid")
            if sensor.data[0] & target.mask == 0:
                raise OwnerError("target_slot_has_no_material")
            self.active_route = target.logical
            self.phase = "loaded"
            self.trace.append(
                {
                    "kind": "route_reconciled_without_filament_effect",
                    "route": target.logical,
                    "automatic_retry": False,
                }
            )
        except (OwnerError, protocol.ProtocolError) as error:
            self._fail(getattr(error, "code", str(error)))
        return self.result()

    def unload(
        self,
        logical_route: str,
        effect_id: str,
        temperature: Mapping[str, Any],
    ) -> Dict[str, Any]:
        try:
            target = protocol.route(logical_route)
        except protocol.ProtocolError as error:
            self._fail(error.code)
            return self.result()
        try:
            self._begin("loaded", "unloading", effect_id)
            TemperatureProof.from_mapping(temperature)
            if self.active_route != target.logical:
                raise OwnerError("active_route_mismatch")
            if target.address not in self.connected_boxes:
                raise OwnerError("target_box_not_connected")
            head_present = self._read_head_sensor()
            after_cutter_present = self._read_after_cutter_sensor()
            if not head_present or not after_cutter_present:
                raise OwnerError("head_sensor_clear_before_unload")
            if self.tip_pull is None:
                raise OwnerError("tip_pull_owner_missing")

            self._send_ok(protocol.set_feed_mode(target), 2.0)
            self._send_ok(
                protocol.retrude(target, protocol.TRIGGER_BUFFER), 20.0
            )
            self.tip_pull_count += 1
            if not self._run_tip_pull(-20.0, 140.0):
                raise OwnerError("tip_pull_not_proven")
            self._send_ok(
                protocol.retrude(target, protocol.TRIGGER_MATERIAL), 20.0
            )
            head_present = self._read_head_sensor()
            after_cutter_present = self._read_after_cutter_sensor()
            if after_cutter_present:
                raise OwnerError("after_cutter_sensor_not_cleared_after_unload")

            self.active_route = None
            self.retained_head_segment = bool(head_present)
            self.unload_count += 1
            self.phase = "idle"
            self.trace.append(
                {
                    "kind": "unload_complete",
                    "route": target.logical,
                    "tip_pull_mm": -20.0,
                    "tip_pull_velocity": 140.0,
                    "retained_head_segment": self.retained_head_segment,
                }
            )
        except (OwnerError, protocol.ProtocolError) as error:
            self._fail(getattr(error, "code", str(error)))
        return self.result()

    def _begin(self, required_phase: str, running_phase: str, effect_id: str) -> None:
        if self.phase != required_phase:
            raise OwnerError("phase_invalid")
        effect_id = str(effect_id)
        if not SAFE_ID.fullmatch(effect_id):
            raise OwnerError("effect_id_invalid")
        if effect_id in self.used_effect_ids:
            raise OwnerError("duplicate_effect_id")
        self.used_effect_ids.add(effect_id)
        self.phase = running_phase
        self.failure_code = None
        self.trace.append({"kind": "effect_begin", "effect_id": effect_id})

    def _read_head_sensor(self) -> bool:
        return self._read_boolean_sensor(self.head_sensor, "head_sensor")

    def _read_after_cutter_sensor(self) -> bool:
        return self._read_boolean_sensor(
            self.after_cutter_sensor,
            "after_cutter_sensor",
        )

    @staticmethod
    def _read_boolean_sensor(callback: Callable[[], bool], name: str) -> bool:
        try:
            value = callback()
        except Exception as error:
            raise OwnerError("%s_exception_%s" % (name, type(error).__name__))
        if value not in (True, False):
            raise OwnerError("%s_value_invalid" % name)
        return bool(value)

    def _run_tip_pull(self, distance_mm: float, velocity: float) -> bool:
        try:
            return self.tip_pull(distance_mm, velocity) is True  # type: ignore[misc]
        except Exception as error:
            raise OwnerError("tip_pull_exception_%s" % type(error).__name__)

    def _send_ok(self, frame: bytes, timeout_s: float):
        frame = bytes(frame)
        self.frames.append(list(frame))
        try:
            raw = self.transport.send(frame, timeout_s, retry=False)
        except Exception as error:
            raise OwnerError("transport_exception_%s" % type(error).__name__)
        if raw is None:
            raise OwnerError("transport_timeout_cmd_%02x" % frame[3])
        response = protocol.parse_response(raw, frame[0], frame[3])
        if response.status != protocol.STATUS_OK:
            raise OwnerError(
                "cfs_status_%02x_cmd_%02x" % (response.status, response.command)
            )
        return response

    def _disable_tension(
        self,
        enabled: Set[int],
        attempted: Set[int],
        strict: bool,
    ) -> None:
        """Tente au plus une désactivation par adresse et par chargement."""

        for address in sorted(tuple(enabled)):
            if address in attempted:
                continue
            attempted.add(address)
            try:
                self._send_ok(protocol.tighten(address, False), 2.0)
                enabled.discard(address)
            except (OwnerError, protocol.ProtocolError) as error:
                self.cleanup_failures.append(getattr(error, "code", str(error)))
                if strict:
                    raise OwnerError("tension_disable_not_proven")
        if attempted:
            self.trace.append(
                {
                    "kind": "tension_disable",
                    "addresses_attempted_once": sorted(attempted),
                    "addresses_still_uncertain": sorted(enabled),
                    "automatic_retry": False,
                }
            )

    def _fail(self, code: str) -> None:
        self.failure_code = str(code)
        self.phase = "failed_safe"
        self.trace.append(
            {"kind": "failed_safe", "code": self.failure_code, "automatic_retry": False}
        )
