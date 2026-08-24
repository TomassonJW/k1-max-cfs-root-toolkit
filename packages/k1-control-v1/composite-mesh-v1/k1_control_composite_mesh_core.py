"""One bounded physical campaign producing a persistent 11x11 composite mesh."""

from __future__ import annotations

import asyncio
import hashlib
import math
import os
import time
from pathlib import Path
from typing import Any, Dict, List


GATE_ID = "G4-K1-CONTROL-COMPOSITE-MESH-V1"
RECOVERY_GATE_ID = "G4-K1-CONTROL-COMPOSITE-MESH-RECOVERY-V1"
PLATE_ID = "PEI_TEXTURED_A"
BED_TARGET_C = 55
NOZZLE_TARGET_C = 140
SOAK_SECONDS = 200
ROBUST_PROFILE = "k1_p001_t055_r001_n06x06"
TARGET_PROFILE = "k1_p001_t055_r001_n11x11"
TEMP_PREFIX = "K1_COMPOSITE_CAPTURE_"

PASS_LAYOUTS = (
    {
        "name": "north_west",
        "profile": TEMP_PREFIX + "NORTH_WEST_06X06",
        "mesh_min": (5, 5),
        "mesh_max": (150, 150),
        "probe_count": (6, 6),
        "x_indices": (0, 1, 2, 3, 4, 5),
        "y_indices": (0, 1, 2, 3, 4, 5),
    },
    {
        "name": "north_east",
        "profile": TEMP_PREFIX + "NORTH_EAST_06X06",
        "mesh_min": (150, 5),
        "mesh_max": (295, 150),
        "probe_count": (6, 6),
        "x_indices": (5, 6, 7, 8, 9, 10),
        "y_indices": (0, 1, 2, 3, 4, 5),
    },
    {
        "name": "south_west",
        "profile": TEMP_PREFIX + "SOUTH_WEST_06X06",
        "mesh_min": (5, 150),
        "mesh_max": (150, 295),
        "probe_count": (6, 6),
        "x_indices": (0, 1, 2, 3, 4, 5),
        "y_indices": (5, 6, 7, 8, 9, 10),
    },
    {
        "name": "south_east",
        "profile": TEMP_PREFIX + "SOUTH_EAST_06X06",
        "mesh_min": (150, 150),
        "mesh_max": (295, 295),
        "probe_count": (6, 6),
        "x_indices": (5, 6, 7, 8, 9, 10),
        "y_indices": (5, 6, 7, 8, 9, 10),
    },
)


class CompositeMeshError(RuntimeError):
    pass


def default_state() -> Dict[str, Any]:
    return {
        "version": 1,
        "phase": "idle",
        "busy": False,
        "campaign_id": None,
        "last_error": None,
        "cancel_requested": False,
        "pass_index": 0,
        "passes": [],
        "qualification": None,
        "candidate_matrix": None,
        "candidate_printer_cfg_sha256": None,
        "config_written": False,
        "backup": None,
    }


def validate_matrix(value: Any, rows: int, columns: int) -> List[List[float]]:
    if not isinstance(value, (list, tuple)) or len(value) != rows:
        raise CompositeMeshError("La matrice ne contient pas le nombre de lignes attendu.")
    matrix: List[List[float]] = []
    for row in value:
        if not isinstance(row, (list, tuple)) or len(row) != columns:
            raise CompositeMeshError("La matrice ne contient pas le nombre de colonnes attendu.")
        converted = []
        for item in row:
            number = float(item)
            if not math.isfinite(number):
                raise CompositeMeshError("La matrice contient une valeur non finie.")
            converted.append(number)
        matrix.append(converted)
    return matrix


class CompositeMeshOrchestrator:
    def __init__(
        self,
        backend: Any,
        store: Any,
        backups: Any,
        composer: Any,
        renderer: Any,
        clock: Any = time.monotonic,
        sleep: Any = asyncio.sleep,
    ) -> None:
        self.backend = backend
        self.store = store
        self.backups = backups
        self.composer = composer
        self.renderer = renderer
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
        result["target_profile"] = TARGET_PROFILE
        result["pass_target_count"] = len(PASS_LAYOUTS)
        result["completed_passes"] = len(result.get("passes") or [])
        result["physical_contacts"] = sum(
            len(item.get("x_indices", [])) * len(item.get("y_indices", []))
            for item in result.get("passes") or []
        )
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
    def _hash_bytes(value: bytes) -> str:
        return hashlib.sha256(value).hexdigest()

    @staticmethod
    def _hash_path(path: Path) -> str:
        digest = hashlib.sha256()
        with Path(path).open("rb") as stream:
            for block in iter(lambda: stream.read(65536), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _profiles(status: Dict[str, Any]) -> Dict[str, Any]:
        profiles = status.get("bed_mesh", {}).get("profiles", {})
        return profiles if isinstance(profiles, dict) else {}

    @staticmethod
    def _assert_runtime(status: Dict[str, Any]) -> None:
        stats = status.get("print_stats", {})
        if stats.get("state") != "standby" or stats.get("filename"):
            raise CompositeMeshError("L'imprimante n'est pas au repos.")
        runtime = status.get("gcode_macro KCTRL_STATE", {})
        if (
            int(runtime.get("ready", 0)) != 1
            or int(runtime.get("accepted_z_valid", 0)) != 1
            or int(runtime.get("session_active", 0)) != 0
            or int(runtime.get("low_moves_armed", 0)) != 0
        ):
            raise CompositeMeshError("Le runtime Z n'est pas fermé et qualifié.")
        path = status.get("gcode_macro KCTRL_CAL_PATH_STATE", {})
        if path.get("phase") not in ("idle", "committed", "cancelled"):
            raise CompositeMeshError("Le chemin Z n'est pas fermé.")
        if int(path.get("motion_armed", 0)) != 0 or int(path.get("commit_ready", 0)) != 0:
            raise CompositeMeshError("Le chemin Z est encore armé.")
        box = status.get("box", {})
        for unit in ("T1", "T2"):
            if box.get(unit, {}).get("state") != "connect":
                raise CompositeMeshError("Le CFS %s n'est pas connecté." % unit)

    @classmethod
    def _assert_fresh_start(cls, status: Dict[str, Any]) -> None:
        cls._assert_runtime(status)
        if float(status.get("extruder", {}).get("target", 0)) != 0:
            raise CompositeMeshError("La buse possède déjà une cible de chauffe.")
        if float(status.get("heater_bed", {}).get("target", 0)) != 0:
            raise CompositeMeshError("Le plateau possède déjà une cible de chauffe.")
        profiles = cls._profiles(status)
        if ROBUST_PROFILE not in profiles:
            raise CompositeMeshError("Le profil robuste 6x6 est absent.")
        if TARGET_PROFILE in profiles:
            raise CompositeMeshError("Le profil composite 11x11 existe déjà.")
        if any(name.startswith(TEMP_PREFIX) or name == "K1_TRANSIENT" for name in profiles):
            raise CompositeMeshError("Un profil temporaire existe déjà.")

    @classmethod
    def _assert_physical_context(cls, status: Dict[str, Any]) -> None:
        cls._assert_runtime(status)
        if "xyz" not in str(status.get("toolhead", {}).get("homed_axes", "")):
            raise CompositeMeshError("La référence XYZ unique a été perdue.")
        if float(status.get("heater_bed", {}).get("target", 0)) != BED_TARGET_C:
            raise CompositeMeshError("La cible du plateau a changé entre deux passages.")
        if float(status.get("extruder", {}).get("target", 0)) != NOZZLE_TARGET_C:
            raise CompositeMeshError("La cible de la buse a changé entre deux passages.")

    async def _run_gcode_when_ready(
        self, command: str, timeout: int = 120, disconnect_ok: bool = False
    ) -> Any:
        deadline = self._clock() + timeout
        last_error = "Klipper non disponible"
        while self._clock() < deadline:
            try:
                return await self.backend.run_gcode(command, disconnect_ok=disconnect_ok)
            except Exception as error:
                last_error = str(error)
            await self._sleep(1)
        raise CompositeMeshError("Commande Klipper non stabilisée : %s" % last_error)

    async def _turn_off_heaters(self) -> None:
        try:
            await self._run_gcode_when_ready("TURN_OFF_HEATERS", timeout=30)
        except Exception:
            pass

    async def _reset_runtime_flags(self) -> None:
        for command in (
            "SET_GCODE_VARIABLE MACRO=KCTRL_STATE VARIABLE=low_moves_armed VALUE=0",
            "SET_GCODE_VARIABLE MACRO=KCTRL_STATE VARIABLE=armed_mesh_profile VALUE='\"none\"'",
            "SET_GCODE_VARIABLE MACRO=KCTRL_STATE VARIABLE=expected_nozzle_c VALUE=0",
            "SET_GCODE_VARIABLE MACRO=KCTRL_STATE VARIABLE=temperature_owner VALUE='\"none\"'",
        ):
            await self._run_gcode_when_ready(command)

    async def _preheat(self) -> None:
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
                and float(bed.get("temperature", 0)) >= BED_TARGET_C - 1
                and float(nozzle.get("temperature", 0)) >= NOZZLE_TARGET_C - 1
            ):
                break
            await self._sleep(1)
        else:
            raise CompositeMeshError("Les températures ne sont pas atteintes.")
        soak_deadline = self._clock() + SOAK_SECONDS
        while self._clock() < soak_deadline:
            self._check_cancelled()
            await self._sleep(min(1.0, soak_deadline - self._clock()))
        for command in (
            "SET_GCODE_VARIABLE MACRO=KCTRL_STATE VARIABLE=low_moves_armed VALUE=0",
            "SET_GCODE_VARIABLE MACRO=KCTRL_STATE VARIABLE=armed_mesh_profile VALUE='\"none\"'",
            "SET_GCODE_VARIABLE MACRO=KCTRL_STATE VARIABLE=expected_nozzle_c VALUE=%d" % NOZZLE_TARGET_C,
            "SET_GCODE_VARIABLE MACRO=KCTRL_STATE VARIABLE=temperature_owner VALUE='\"calibration\"'",
        ):
            await self.backend.run_gcode(command)

    @staticmethod
    def _mesh_command(layout: Dict[str, Any]) -> str:
        return (
            "BED_MESH_CALIBRATE PROFILE=%s MESH_MIN=%d,%d MESH_MAX=%d,%d "
            "PROBE_COUNT=%d,%d ALGORITHM=lagrange"
            % (
                layout["profile"],
                layout["mesh_min"][0], layout["mesh_min"][1],
                layout["mesh_max"][0], layout["mesh_max"][1],
                layout["probe_count"][0], layout["probe_count"][1],
            )
        )

    async def _capture_pass(
        self, layout: Dict[str, Any], campaign_id: str
    ) -> Dict[str, Any]:
        before = await self.backend.query_status()
        self._assert_physical_context(before)
        await self.backend.run_gcode("BED_MESH_CLEAR")
        await self.backend.run_gcode(self._mesh_command(layout))
        self._check_cancelled()
        measured = await self.backend.query_status()
        self._assert_physical_context(measured)
        if measured.get("bed_mesh", {}).get("profile_name") != layout["profile"]:
            raise CompositeMeshError(
                "Le passage PRTouch n'a pas produit son profil temporaire."
            )
        rows = int(layout["probe_count"][1])
        columns = int(layout["probe_count"][0])
        matrix = validate_matrix(measured.get("bed_mesh", {}).get("probed_matrix"), rows, columns)
        return {
            "name": layout["name"],
            "context": {
                "session_id": campaign_id,
                "plate_id": PLATE_ID,
                "bed_target_c": BED_TARGET_C,
                "nozzle_target_c": NOZZLE_TARGET_C,
                "homing_epoch": campaign_id,
                "klipper_restart_count": 0,
            },
            "x_indices": list(layout["x_indices"]),
            "y_indices": list(layout["y_indices"]),
            "mesh_min": list(layout["mesh_min"]),
            "mesh_max": list(layout["mesh_max"]),
            "probe_count": list(layout["probe_count"]),
            "algorithm": "lagrange",
            "matrix": matrix,
        }

    def _compose(self, passes: List[Dict[str, Any]]) -> Dict[str, Any]:
        try:
            return self.composer({
                "target": {
                    "x_count": 11,
                    "y_count": 11,
                    "mesh_min": [5, 5],
                    "mesh_max": [295, 295],
                },
                "passes": passes,
            })
        except Exception as error:
            raise CompositeMeshError("Fusion composite refusée : %s" % error) from error

    def _write_candidate(self, matrix: Any, backup: Dict[str, Any]) -> str:
        path = Path(self.backups.printer_config)
        source = path.read_bytes()
        if self._hash_bytes(source) != backup.get("printer_cfg_sha256"):
            raise CompositeMeshError("printer.cfg a changé après le backup.")
        try:
            candidate = self.renderer(source, matrix)
        except Exception as error:
            raise CompositeMeshError("Rendu du profil composite refusé : %s" % error) from error
        temporary = path.with_name(path.name + ".k1-composite.next")
        try:
            with temporary.open("wb") as stream:
                stream.write(candidate)
                stream.flush()
                os.fsync(stream.fileno())
            if self._hash_path(temporary) != self._hash_bytes(candidate):
                raise CompositeMeshError("Le candidat printer.cfg écrit est altéré.")
            os.replace(str(temporary), str(path))
        finally:
            if temporary.exists():
                temporary.unlink()
        final_hash = self._hash_path(path)
        if final_hash != self._hash_bytes(candidate):
            raise CompositeMeshError("La transaction printer.cfg est incomplète.")
        return final_hash

    @staticmethod
    def _matrix_matches(actual: Any, expected: Any, tolerance: float = 0.000001) -> bool:
        try:
            left = validate_matrix(actual, 11, 11)
            right = validate_matrix(expected, 11, 11)
        except CompositeMeshError:
            return False
        return all(
            abs(left[y][x] - right[y][x]) <= tolerance
            for y in range(11)
            for x in range(11)
        )

    async def _wait_safe_final(self, expect_target: bool, timeout: int = 180) -> Dict[str, Any]:
        deadline = self._clock() + timeout
        last_error = "état final non disponible"
        while self._clock() < deadline:
            try:
                status = await self.backend.query_status()
                self._assert_runtime(status)
                if float(status.get("extruder", {}).get("target", 0)) != 0 or float(status.get("heater_bed", {}).get("target", 0)) != 0:
                    raise CompositeMeshError("Les chauffes ne sont pas coupées.")
                if status.get("toolhead", {}).get("homed_axes"):
                    raise CompositeMeshError("Les axes sont encore référencés.")
                profiles = self._profiles(status)
                if ROBUST_PROFILE not in profiles or status.get("bed_mesh", {}).get("profile_name") != ROBUST_PROFILE:
                    raise CompositeMeshError("Le profil robuste n'est pas actif.")
                if (TARGET_PROFILE in profiles) != expect_target:
                    raise CompositeMeshError("Présence du profil composite inattendue.")
                if any(name.startswith(TEMP_PREFIX) for name in profiles):
                    raise CompositeMeshError("Un profil temporaire subsiste.")
                return status
            except Exception as error:
                last_error = str(error)
            await self._sleep(1)
        raise CompositeMeshError("État final non stabilisé : %s" % last_error)

    async def _restart_and_load_robust(self) -> None:
        await self._run_gcode_when_ready("RESTART", disconnect_ok=True)
        await self.backend.wait_klippy_ready(120)
        await self._run_gcode_when_ready("BED_MESH_PROFILE LOAD=%s" % ROBUST_PROFILE)
        await self._turn_off_heaters()
        await self._reset_runtime_flags()

    async def _rollback(self, restore_config: bool, restart_required: bool) -> None:
        await self._turn_off_heaters()
        if restore_config:
            self.backups.restore(str(self.state.get("campaign_id")), self.state.get("backup"))
            restart_required = True
        if restart_required:
            await self._restart_and_load_robust()
        else:
            await self._run_gcode_when_ready("BED_MESH_PROFILE LOAD=%s" % ROBUST_PROFILE)
            await self._reset_runtime_flags()
        await self._wait_safe_final(expect_target=False)

    async def _qualify_and_persist(
        self, passes: List[Dict[str, Any]], backup: Dict[str, Any]
    ) -> Dict[str, Any]:
        qualification = self._compose(passes)
        candidate_matrix = qualification.get("candidate_matrix")
        validate_matrix(candidate_matrix, 11, 11)
        self._transition(
            "composed",
            qualification=qualification,
            candidate_matrix=candidate_matrix,
        )
        await self._turn_off_heaters()
        self._transition("persisting")
        candidate_hash = self._write_candidate(candidate_matrix, backup)
        self._transition(
            "restarting",
            config_written=True,
            candidate_printer_cfg_sha256=candidate_hash,
        )
        await self._run_gcode_when_ready("RESTART", disconnect_ok=True)
        await self.backend.wait_klippy_ready(120)
        await self._run_gcode_when_ready("BED_MESH_PROFILE LOAD=%s" % TARGET_PROFILE)
        loaded = await self.backend.query_status()
        if loaded.get("bed_mesh", {}).get("profile_name") != TARGET_PROFILE:
            raise CompositeMeshError("Le profil composite n'est pas actif après persistance.")
        if not self._matrix_matches(
            loaded.get("bed_mesh", {}).get("probed_matrix"), candidate_matrix
        ):
            raise CompositeMeshError("Le profil composite relu diffère des 121 positions.")
        await self._run_gcode_when_ready("BED_MESH_PROFILE LOAD=%s" % ROBUST_PROFILE)
        await self._turn_off_heaters()
        await self._reset_runtime_flags()
        await self._wait_safe_final(expect_target=True)
        self._transition("qualified", busy=False, cancel_requested=False, last_error=None)
        return self.public_state()

    async def recover_complete_capture(self, gate: str) -> Dict[str, Any]:
        if gate != RECOVERY_GATE_ID:
            raise CompositeMeshError("La gate de reprise composite exacte est obligatoire.")
        async with self._lock:
            passes = self.state.get("passes")
            backup = self.state.get("backup")
            if (
                self.state.get("busy")
                or self.state.get("phase") != "failed"
                or not isinstance(passes, list)
                or len(passes) != 4
                or not isinstance(backup, dict)
                or bool(self.state.get("config_written"))
            ):
                raise CompositeMeshError("La capture complète à reprendre est absente.")
            status = await self.backend.query_status()
            self._assert_fresh_start(status)
            if self._hash_path(Path(self.backups.printer_config)) != backup.get(
                "printer_cfg_sha256"
            ):
                raise CompositeMeshError("printer.cfg ne correspond plus au backup physique.")
            if bool(backup.get("z_state_present")):
                z_path = Path(self.backups.z_state)
                if not z_path.is_file() or self._hash_path(z_path) != backup.get(
                    "z_state_sha256"
                ):
                    raise CompositeMeshError("L'état Z ne correspond plus au backup physique.")
            elif Path(self.backups.z_state).exists():
                raise CompositeMeshError("L'état Z absent au backup existe maintenant.")
            self._cancel_requested.clear()
            self._transition(
                "recomposing", busy=True, cancel_requested=False, last_error=None
            )
            try:
                return await self._qualify_and_persist(passes, backup)
            except Exception as error:
                cleanup_error = None
                try:
                    await self._rollback(
                        bool(self.state.get("config_written")),
                        bool(self.state.get("config_written")),
                    )
                except Exception as cleanup:
                    cleanup_error = cleanup
                message = str(error)
                if cleanup_error is not None:
                    message += " ; restauration KO: %s" % cleanup_error
                self._transition("failed", busy=False, last_error=message)
                raise CompositeMeshError(message)

    async def recover_interrupted(self) -> Dict[str, Any]:
        status = await self.backend.query_status()
        stats = status.get("print_stats", {})
        if stats.get("state") != "standby" or stats.get("filename"):
            self._transition("failed", busy=False, last_error="Reprise refusée : une impression est active.")
            return self.public_state()
        if not isinstance(self.state.get("backup"), dict):
            self._transition("interrupted", busy=False, last_error="Campagne interrompue avant backup.")
            return self.public_state()
        phase = str(self.state.get("phase", "idle"))
        restart_required = phase not in ("preflight", "preheating") or bool(status.get("toolhead", {}).get("homed_axes"))
        await self._rollback(bool(self.state.get("config_written")), restart_required)
        self._transition("interrupted", busy=False, last_error="Campagne interrompue puis restaurée.")
        return self.public_state()

    async def run(self, gate: str, plate_clear: bool) -> Dict[str, Any]:
        if gate != GATE_ID:
            raise CompositeMeshError("La gate composite exacte est obligatoire.")
        if not plate_clear:
            raise CompositeMeshError("Le plateau libre doit être confirmé.")
        async with self._lock:
            if self.state.get("busy"):
                raise CompositeMeshError("Une campagne composite est déjà en cours.")
            self._cancel_requested.clear()
            campaign_id = "%s-%03d-composite-mesh-v1" % (
                time.strftime("%Y%m%d-%H%M%S", time.localtime()),
                int(time.time() * 1000) % 1000,
            )
            self.state = default_state()
            self._transition("preflight", busy=True, campaign_id=campaign_id)
            physical_started = False
            restart_required = False
            try:
                status = await self.backend.query_status()
                self._assert_fresh_start(status)
                backup = self.backups.create(campaign_id)
                self._transition("preheating", backup=backup)
                physical_started = True
                await self._preheat()
                self._transition("cleaning")
                restart_required = True
                await self.backend.run_gcode(
                    "NOZZLE_CLEAR HOT_MIN_TEMP=%d HOT_MAX_TEMP=180 BED_MAX_TEMP=%d"
                    % (NOZZLE_TARGET_C, BED_TARGET_C)
                )
                self._check_cancelled()
                self._transition("homing")
                await self.backend.run_gcode("KCTRL_CALIBRATION_HOME")
                homed = await self.backend.query_status()
                self._assert_physical_context(homed)

                passes: List[Dict[str, Any]] = []
                for index, layout in enumerate(PASS_LAYOUTS, start=1):
                    self._check_cancelled()
                    self._transition("measuring", pass_index=index, passes=passes)
                    passes.append(await self._capture_pass(layout, campaign_id))
                    self._transition("captured", pass_index=index, passes=passes)

                return await self._qualify_and_persist(passes, backup)
            except asyncio.CancelledError:
                if physical_started:
                    await self._rollback(bool(self.state.get("config_written")), restart_required)
                self._transition("cancelled", busy=False, last_error="Campagne composite annulée puis restaurée.")
                raise
            except Exception as error:
                cleanup_error = None
                if physical_started:
                    try:
                        await self._rollback(bool(self.state.get("config_written")), restart_required)
                    except Exception as cleanup:
                        cleanup_error = cleanup
                message = str(error)
                if cleanup_error is not None:
                    message += " ; restauration KO: %s" % cleanup_error
                self._transition("failed", busy=False, last_error=message)
                raise CompositeMeshError(message)
