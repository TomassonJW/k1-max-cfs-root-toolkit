"""Bounded one-shot acquisition for the first composite-mesh physical gate."""

from __future__ import annotations

import asyncio
import math
import time
from typing import Any, Dict


GATE_ID = "G4-K1-CONTROL-COMPOSITE-MESH-SUBGRID-V1"
PLATE_ID = "PEI_TEXTURED_A"
BED_TARGET_C = 55
NOZZLE_TARGET_C = 140
SOAK_SECONDS = 200
TEMP_PROFILE = "K1_COMPOSITE_ODD_ODD_05X05"
ROBUST_PROFILE = "k1_p001_t055_r001_n06x06"
MESH_COMMAND = (
    "BED_MESH_CALIBRATE PROFILE=%s MESH_MIN=34,34 MESH_MAX=266,266 "
    "PROBE_COUNT=5,5 ALGORITHM=lagrange" % TEMP_PROFILE
)


class CompositeSubgridError(RuntimeError):
    pass


def default_state() -> Dict[str, Any]:
    return {
        "schema": 1,
        "phase": "idle",
        "busy": False,
        "campaign_id": None,
        "last_error": None,
        "cancel_requested": False,
        "matrix": None,
        "context": None,
        "backup": None,
    }


def validate_matrix(value: Any) -> Any:
    if not isinstance(value, (list, tuple)) or len(value) != 5:
        raise CompositeSubgridError("La sous-grille ne contient pas cinq lignes.")
    matrix = []
    for row in value:
        if not isinstance(row, (list, tuple)) or len(row) != 5:
            raise CompositeSubgridError("La sous-grille ne contient pas cinq colonnes.")
        converted = []
        for item in row:
            number = float(item)
            if not math.isfinite(number):
                raise CompositeSubgridError("La sous-grille contient une valeur non finie.")
            converted.append(number)
        matrix.append(converted)
    return matrix


class CompositeSubgridOrchestrator:
    def __init__(
        self,
        backend: Any,
        store: Any,
        backups: Any,
        clock: Any = time.monotonic,
        sleep: Any = asyncio.sleep,
    ) -> None:
        self.backend = backend
        self.store = store
        self.backups = backups
        self.state = store.load() or default_state()
        self._clock = clock
        self._sleep = sleep
        self._lock = asyncio.Lock()
        self._cancel_requested = asyncio.Event()

    def public_state(self) -> Dict[str, Any]:
        result = dict(self.state)
        result["gate"] = GATE_ID
        result["plate"] = PLATE_ID
        result["bed_target_c"] = BED_TARGET_C
        result["nozzle_target_c"] = NOZZLE_TARGET_C
        result["soak_seconds"] = SOAK_SECONDS
        result["subgrid"] = "odd_odd_05x05"
        result["physical_contacts"] = 25
        result["mesh_min"] = [34, 34]
        result["mesh_max"] = [266, 266]
        result["temporary_profile"] = TEMP_PROFILE
        result["robust_profile"] = ROBUST_PROFILE
        result["backup_available"] = isinstance(result.get("backup"), dict)
        result.pop("backup", None)
        return result

    def _transition(self, phase: str, **updates: Any) -> None:
        self.state.update(updates)
        self.state["phase"] = phase
        self.store.save(self.state)

    def request_cancel(self) -> Dict[str, Any]:
        self._cancel_requested.set()
        self.state["cancel_requested"] = True
        if self.state.get("busy"):
            self._transition("cancelling")
        else:
            self.store.save(self.state)
        return self.public_state()

    def _check_cancelled(self) -> None:
        if self._cancel_requested.is_set():
            raise asyncio.CancelledError()

    @staticmethod
    def _assert_common_state(status: Dict[str, Any]) -> None:
        stats = status.get("print_stats", {})
        if stats.get("state") != "standby" or stats.get("filename"):
            raise CompositeSubgridError("L'imprimante n'est pas au repos.")
        if float(status.get("extruder", {}).get("target", 0)) != 0:
            raise CompositeSubgridError("La buse possède déjà une cible de chauffe.")
        if float(status.get("heater_bed", {}).get("target", 0)) != 0:
            raise CompositeSubgridError("Le plateau possède déjà une cible de chauffe.")
        runtime = status.get("gcode_macro KCTRL_STATE", {})
        if (
            int(runtime.get("ready", 0)) != 1
            or int(runtime.get("accepted_z_valid", 0)) != 1
            or int(runtime.get("session_active", 0)) != 0
            or int(runtime.get("low_moves_armed", 0)) != 0
        ):
            raise CompositeSubgridError("Le runtime Z n'est pas fermé et qualifié.")
        path = status.get("gcode_macro KCTRL_CAL_PATH_STATE", {})
        if path.get("phase") not in ("idle", "committed", "cancelled"):
            raise CompositeSubgridError("Le chemin Z n'est pas fermé.")
        if int(path.get("motion_armed", 0)) != 0:
            raise CompositeSubgridError("Le chemin Z est encore armé.")
        profiles = status.get("bed_mesh", {}).get("profiles", {})
        if ROBUST_PROFILE not in profiles:
            raise CompositeSubgridError("Le profil robuste 6x6 est absent.")
        if TEMP_PROFILE in profiles or "K1_TRANSIENT" in profiles:
            raise CompositeSubgridError("Un profil temporaire existe déjà.")
        box = status.get("box", {})
        for unit in ("T1", "T2"):
            if box.get(unit, {}).get("state") != "connect":
                raise CompositeSubgridError("Le CFS %s n'est pas connecté." % unit)

    @staticmethod
    def _assert_final_state(status: Dict[str, Any]) -> None:
        CompositeSubgridOrchestrator._assert_common_state(status)
        bed_mesh = status.get("bed_mesh", {})
        if bed_mesh.get("profile_name") != ROBUST_PROFILE:
            raise CompositeSubgridError("Le profil robuste n'est pas rechargé.")

    async def _turn_off_heaters(self) -> None:
        try:
            await self.backend.run_gcode("TURN_OFF_HEATERS")
        except Exception:
            pass

    async def _reset_runtime_flags(self) -> None:
        commands = (
            "SET_GCODE_VARIABLE MACRO=KCTRL_STATE VARIABLE=low_moves_armed VALUE=0",
            "SET_GCODE_VARIABLE MACRO=KCTRL_STATE VARIABLE=armed_mesh_profile VALUE='\"none\"'",
            "SET_GCODE_VARIABLE MACRO=KCTRL_STATE VARIABLE=expected_nozzle_c VALUE=0",
            "SET_GCODE_VARIABLE MACRO=KCTRL_STATE VARIABLE=temperature_owner VALUE='\"none\"'",
        )
        for command in commands:
            try:
                await self.backend.run_gcode(command)
            except Exception:
                pass

    async def _wait_final_state(self, timeout: int = 120) -> Dict[str, Any]:
        deadline = self._clock() + timeout
        last_error = "état final non disponible"
        while self._clock() < deadline:
            try:
                status = await self.backend.query_status()
                self._assert_final_state(status)
                return status
            except Exception as error:
                last_error = str(error)
            await self._sleep(1)
        raise CompositeSubgridError("État final non stabilisé : %s" % last_error)

    async def _restore_after_capture(self, restart_required: bool = True) -> None:
        await self._turn_off_heaters()
        try:
            await self.backend.run_gcode("BED_MESH_PROFILE LOAD=%s" % ROBUST_PROFILE)
        except Exception:
            pass
        if restart_required:
            try:
                await self.backend.run_gcode("BED_MESH_PROFILE REMOVE=%s" % TEMP_PROFILE)
            except Exception:
                pass
            try:
                await self.backend.run_gcode("RESTART", disconnect_ok=True)
                await self.backend.wait_klippy_ready(120)
                await self.backend.run_gcode("BED_MESH_PROFILE LOAD=%s" % ROBUST_PROFILE)
            finally:
                await self._turn_off_heaters()
        await self._reset_runtime_flags()

    async def _preheat(self) -> None:
        self._check_cancelled()
        await self.backend.run_gcode("M140 S%d" % BED_TARGET_C)
        await self.backend.run_gcode("M104 S%d" % NOZZLE_TARGET_C)
        deadline = self._clock() + 1200
        while self._clock() < deadline:
            self._check_cancelled()
            status = await self.backend.query_status()
            bed = status.get("heater_bed", {})
            nozzle = status.get("extruder", {})
            if (
                float(bed.get("target", 0)) == BED_TARGET_C
                and float(nozzle.get("target", 0)) == NOZZLE_TARGET_C
                and float(bed.get("temperature", 0)) >= BED_TARGET_C - 1.0
                and float(nozzle.get("temperature", 0)) >= NOZZLE_TARGET_C - 1.0
            ):
                break
            await self._sleep(1)
        else:
            raise CompositeSubgridError("Les températures ne sont pas atteintes.")
        soak_deadline = self._clock() + SOAK_SECONDS
        while self._clock() < soak_deadline:
            self._check_cancelled()
            await self._sleep(min(1.0, soak_deadline - self._clock()))
        self._check_cancelled()
        await self.backend.run_gcode(
            "SET_GCODE_VARIABLE MACRO=KCTRL_STATE VARIABLE=low_moves_armed VALUE=0"
        )
        await self.backend.run_gcode(
            "SET_GCODE_VARIABLE MACRO=KCTRL_STATE VARIABLE=armed_mesh_profile VALUE='\"none\"'"
        )
        await self.backend.run_gcode(
            "SET_GCODE_VARIABLE MACRO=KCTRL_STATE VARIABLE=expected_nozzle_c VALUE=%d"
            % NOZZLE_TARGET_C
        )
        await self.backend.run_gcode(
            "SET_GCODE_VARIABLE MACRO=KCTRL_STATE VARIABLE=temperature_owner VALUE='\"calibration\"'"
        )

    async def recover_interrupted(self) -> Dict[str, Any]:
        phase = str(self.state.get("phase", "idle"))
        status = await self.backend.query_status()
        stats = status.get("print_stats", {})
        if stats.get("state") != "standby" or stats.get("filename"):
            self._transition(
                "failed",
                busy=False,
                last_error="Reprise refusée : une impression est active.",
            )
            return self.public_state()
        if phase == "preflight":
            self._transition(
                "interrupted",
                busy=False,
                last_error="Sous-grille interrompue avant toute action physique.",
            )
            return self.public_state()
        restart_required = phase in ("measuring", "captured")
        await self._restore_after_capture(restart_required)
        self._transition(
            "interrupted",
            busy=False,
            last_error="Sous-grille interrompue puis restaurée au démarrage.",
        )
        return self.public_state()

    async def run(self, gate: str, plate_clear: bool) -> Dict[str, Any]:
        if gate != GATE_ID:
            raise CompositeSubgridError("La gate composite exacte est obligatoire.")
        if not plate_clear:
            raise CompositeSubgridError("Le plateau libre doit être confirmé.")
        async with self._lock:
            if self.state.get("busy"):
                raise CompositeSubgridError("Une sous-grille est déjà en cours.")
            self._cancel_requested.clear()
            campaign_id = "%s-%03d-composite-subgrid-v1" % (
                time.strftime("%Y%m%d-%H%M%S", time.localtime()),
                int(time.time() * 1000) % 1000,
            )
            self.state = default_state()
            self._transition(
                "preflight",
                busy=True,
                campaign_id=campaign_id,
                last_error=None,
                cancel_requested=False,
            )
            cleanup_required = False
            restart_required = False
            try:
                status = await self.backend.query_status()
                self._assert_common_state(status)
                backup = self.backups.create(campaign_id)
                self._transition("preheating", backup=backup)
                cleanup_required = True
                await self._preheat()
                self._transition("cleaning")
                await self.backend.run_gcode(
                    "NOZZLE_CLEAR HOT_MIN_TEMP=%d HOT_MAX_TEMP=180 BED_MAX_TEMP=%d"
                    % (NOZZLE_TARGET_C, BED_TARGET_C)
                )
                self._check_cancelled()
                self._transition("homing")
                await self.backend.run_gcode("KCTRL_CALIBRATION_HOME")
                self._check_cancelled()
                homed = await self.backend.query_status()
                if "xyz" not in str(homed.get("toolhead", {}).get("homed_axes", "")):
                    raise CompositeSubgridError("Le référencement XYZ n'est pas confirmé.")
                self._transition("measuring")
                await self.backend.run_gcode("BED_MESH_CLEAR")
                restart_required = True
                await self.backend.run_gcode(MESH_COMMAND)
                self._check_cancelled()
                measured = await self.backend.query_status()
                matrix = validate_matrix(measured.get("bed_mesh", {}).get("probed_matrix"))
                if measured.get("bed_mesh", {}).get("profile_name") != TEMP_PROFILE:
                    raise CompositeSubgridError("Le profil temporaire mesuré n'est pas actif.")
                context = {
                    "session_id": campaign_id,
                    "plate_id": PLATE_ID,
                    "bed_target_c": BED_TARGET_C,
                    "nozzle_target_c": NOZZLE_TARGET_C,
                    "homing_epoch": campaign_id,
                    "klipper_restart_count": 0,
                    "x_indices": [1, 3, 5, 7, 9],
                    "y_indices": [1, 3, 5, 7, 9],
                }
                self._transition("captured", matrix=matrix, context=context)
                await self._restore_after_capture()
                await self._wait_final_state()
                self._transition("qualified", busy=False)
                return self.public_state()
            except asyncio.CancelledError:
                if cleanup_required:
                    await self._restore_after_capture(restart_required)
                self._transition(
                    "cancelled", busy=False, last_error="Sous-grille annulée après arrêt borné."
                )
                raise
            except Exception as error:
                cleanup_error = None
                if cleanup_required:
                    try:
                        await self._restore_after_capture(restart_required)
                    except Exception as cleanup:
                        cleanup_error = cleanup
                message = str(error)
                if cleanup_error is not None:
                    message += " ; restauration KO: %s" % cleanup_error
                self._transition("failed", busy=False, last_error=message)
                raise CompositeSubgridError(message)
