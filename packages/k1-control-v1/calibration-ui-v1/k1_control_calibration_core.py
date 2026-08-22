"""Bounded calibration workflow used by the K1 Control Moonraker component."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import shutil
import statistics
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


MESH_COUNT = 6
MESH_ROWS = 6
MESH_COLUMNS = 6
MEAN_ABSOLUTE_LIMIT_MM = 0.020
RMS_LIMIT_MM = 0.025
MAXIMUM_LIMIT_MM = 0.060
Z_LADDER_MM = (5.0, 2.0, 1.0, 0.5, 0.3, 0.2, 0.15, 0.1)
Z_ADJUSTMENTS_MM = (-0.1, -0.05, -0.01, -0.005, 0.005, 0.01, 0.05, 0.1)


class CalibrationError(RuntimeError):
    pass


def _boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def default_state() -> Dict[str, Any]:
    return {
        "version": 1,
        "phase": "idle",
        "busy": False,
        "campaign_id": None,
        "config": None,
        "mesh_index": 0,
        "meshes": [],
        "qualification": None,
        "candidate_matrix": None,
        "z_ladder_index": None,
        "last_error": None,
        "updated_at": int(time.time()),
    }


def validate_config(raw: Dict[str, Any]) -> Dict[str, Any]:
    config = {
        "plate_id": int(raw.get("plate_id", 0)),
        "plate_label": str(raw.get("plate_label", "")).strip(),
        "bed_temp_c": int(raw.get("bed_temp_c", -1)),
        "nozzle_temp_c": int(raw.get("nozzle_temp_c", -1)),
        "soak_seconds": int(raw.get("soak_seconds", -1)),
        "probe_revision": int(raw.get("probe_revision", 0)),
        "nozzle_id": int(raw.get("nozzle_id", 0)),
        "config_id": int(raw.get("config_id", 0)),
        "x_count": int(raw.get("x_count", 0)),
        "y_count": int(raw.get("y_count", 0)),
        "algorithm": str(raw.get("algorithm", "")).strip().lower(),
        "seed_offset_mm": float(raw.get("seed_offset_mm", 0.0)),
        "replace_existing": _boolean(raw.get("replace_existing", False)),
    }
    if config["plate_id"] < 1 or not config["plate_label"]:
        raise CalibrationError("Plaque non sélectionnée.")
    if not 45 <= config["bed_temp_c"] <= 100:
        raise CalibrationError("Température plateau hors plage 45-100 °C.")
    if not 100 <= config["nozzle_temp_c"] <= 180:
        raise CalibrationError("Température buse hors plage 100-180 °C.")
    if not 60 <= config["soak_seconds"] <= 1200:
        raise CalibrationError("Stabilisation hors plage 60-1200 s.")
    if min(config["probe_revision"], config["nozzle_id"], config["config_id"]) < 1:
        raise CalibrationError("Identité de calibration incomplète.")
    if not 3 <= config["x_count"] <= 6 or not 3 <= config["y_count"] <= 6:
        raise CalibrationError("L'interface sûre limite la matrice à 3x3-6x6.")
    if config["algorithm"] not in ("lagrange", "bicubic"):
        raise CalibrationError("Interpolation inconnue.")
    if config["algorithm"] == "lagrange" and max(config["x_count"], config["y_count"]) > 6:
        raise CalibrationError("Lagrange est limité à 6 points par axe.")
    if config["algorithm"] == "bicubic" and min(config["x_count"], config["y_count"]) < 4:
        raise CalibrationError("Bicubique exige au moins 4 points par axe.")
    if not math.isfinite(config["seed_offset_mm"]) or abs(config["seed_offset_mm"]) > 1.0:
        raise CalibrationError("Seed Z hors plage ±1 mm.")
    return config


def validate_matrix(
    matrix: Any, rows: int = MESH_ROWS, columns: int = MESH_COLUMNS
) -> List[List[float]]:
    if not isinstance(matrix, list) or len(matrix) != rows:
        raise CalibrationError("Le mesh ne contient pas le nombre de lignes attendu.")
    result: List[List[float]] = []
    for row in matrix:
        if not isinstance(row, list) or len(row) != columns:
            raise CalibrationError("Une ligne du mesh ne contient pas le nombre de valeurs attendu.")
        values = [float(value) for value in row]
        if not all(math.isfinite(value) and abs(value) <= 5.0 for value in values):
            raise CalibrationError("Le mesh contient une valeur invalide.")
        result.append(values)
    return result


def pointwise_median(matrices: Sequence[List[List[float]]]) -> List[List[float]]:
    rows = len(matrices[0])
    columns = len(matrices[0][0])
    return [
        [round(statistics.median(matrix[row][column] for matrix in matrices), 6)
         for column in range(columns)]
        for row in range(rows)
    ]


def aggregate_meshes(
    matrices: Sequence[List[List[float]]],
    rows: int = MESH_ROWS,
    columns: int = MESH_COLUMNS,
) -> Dict[str, Any]:
    if len(matrices) != MESH_COUNT:
        raise CalibrationError("Exactement six meshes sont obligatoires.")
    checked = [validate_matrix(matrix, rows, columns) for matrix in matrices]
    batch_a = pointwise_median(checked[:3])
    batch_b = pointwise_median(checked[3:])
    candidate = pointwise_median(checked)
    deltas = [
        abs(batch_a[row][column] - batch_b[row][column])
        for row in range(rows)
        for column in range(columns)
    ]
    mean_absolute = sum(deltas) / len(deltas)
    rms = math.sqrt(sum(delta * delta for delta in deltas) / len(deltas))
    maximum = max(deltas)
    return {
        "accepted": (
            mean_absolute <= MEAN_ABSOLUTE_LIMIT_MM
            and rms <= RMS_LIMIT_MM
            and maximum <= MAXIMUM_LIMIT_MM
        ),
        "method": "two_independent_pointwise_median_batches_of_three",
        "observed_mm": {
            "mean_absolute": round(mean_absolute, 9),
            "rms": round(rms, 9),
            "maximum": round(maximum, 9),
        },
        "limits_mm": {
            "mean_absolute": MEAN_ABSOLUTE_LIMIT_MM,
            "rms": RMS_LIMIT_MM,
            "maximum": MAXIMUM_LIMIT_MM,
        },
        "candidate_matrix": candidate,
    }


class AtomicJsonStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return default_state()
        value = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("version") != 1:
            raise CalibrationError("État de campagne illisible.")
        return value

    def save(self, state: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        state["updated_at"] = int(time.time())
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(state, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(str(temporary), str(self.path))


class BackupManager:
    def __init__(self, printer_config: Path, z_state: Path, backup_root: Path) -> None:
        self.printer_config = Path(printer_config)
        self.z_state = Path(z_state)
        self.backup_root = Path(backup_root)

    @staticmethod
    def _hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(65536), b""):
                digest.update(block)
        return digest.hexdigest()

    def create(self, campaign_id: str) -> Dict[str, Any]:
        root = self.backup_root / campaign_id
        root.mkdir(parents=True, exist_ok=False)
        config_copy = root / "printer.cfg.before"
        shutil.copy2(str(self.printer_config), str(config_copy))
        evidence: Dict[str, Any] = {
            "root": str(root),
            "printer_cfg_sha256": self._hash(config_copy),
            "z_state_present": self.z_state.exists(),
        }
        if self._hash(self.printer_config) != evidence["printer_cfg_sha256"]:
            raise CalibrationError("Le backup printer.cfg ne correspond pas à la source.")
        if self.z_state.exists():
            state_copy = root / "k1-control-z-state.json.before"
            shutil.copy2(str(self.z_state), str(state_copy))
            evidence["z_state_sha256"] = self._hash(state_copy)
            if self._hash(self.z_state) != evidence["z_state_sha256"]:
                raise CalibrationError("Le backup Z ne correspond pas à la source.")
        manifest = root / "backup.json"
        manifest.write_text(json.dumps(evidence, sort_keys=True) + "\n", encoding="utf-8")
        return evidence

    def restore(self, campaign_id: str, evidence: Dict[str, Any]) -> Dict[str, Any]:
        expected_root = (self.backup_root / campaign_id).resolve()
        root = Path(str(evidence.get("root", ""))).resolve()
        if root != expected_root or root.parent != self.backup_root.resolve():
            raise CalibrationError("Le backup demandé n'appartient pas à cette campagne.")
        manifest_path = root / "backup.json"
        config_copy = root / "printer.cfg.before"
        if not manifest_path.is_file() or not config_copy.is_file():
            raise CalibrationError("Le backup de campagne est incomplet.")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest != evidence:
            raise CalibrationError("Le manifeste du backup ne correspond plus à l'état enregistré.")
        if self._hash(config_copy) != evidence.get("printer_cfg_sha256"):
            raise CalibrationError("L'empreinte du backup printer.cfg est invalide.")

        z_present = bool(evidence.get("z_state_present"))
        z_copy = root / "k1-control-z-state.json.before"
        if z_present:
            if not z_copy.is_file() or self._hash(z_copy) != evidence.get("z_state_sha256"):
                raise CalibrationError("L'empreinte du backup Z est invalide.")

        config_next = self.printer_config.with_name(self.printer_config.name + ".k1-control-restore.next")
        z_next = self.z_state.with_name(self.z_state.name + ".k1-control-restore.next")
        try:
            shutil.copy2(str(config_copy), str(config_next))
            if self._hash(config_next) != evidence["printer_cfg_sha256"]:
                raise CalibrationError("La copie préparée de printer.cfg est invalide.")
            if z_present:
                self.z_state.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(z_copy), str(z_next))
                if self._hash(z_next) != evidence["z_state_sha256"]:
                    raise CalibrationError("La copie préparée de l'état Z est invalide.")
            os.replace(str(config_next), str(self.printer_config))
            if z_present:
                os.replace(str(z_next), str(self.z_state))
            elif self.z_state.exists():
                self.z_state.unlink()
        finally:
            if config_next.exists():
                config_next.unlink()
            if z_next.exists():
                z_next.unlink()

        if self._hash(self.printer_config) != evidence["printer_cfg_sha256"]:
            raise CalibrationError("printer.cfg restauré ne correspond pas au backup.")
        if z_present:
            if not self.z_state.is_file() or self._hash(self.z_state) != evidence["z_state_sha256"]:
                raise CalibrationError("L'état Z restauré ne correspond pas au backup.")
        elif self.z_state.exists():
            raise CalibrationError("L'état Z absent avant campagne n'a pas été retiré.")
        return {
            "printer_cfg_sha256": evidence["printer_cfg_sha256"],
            "z_state_present": z_present,
            "z_state_sha256": evidence.get("z_state_sha256"),
        }


class CalibrationOrchestrator:
    def __init__(
        self,
        backend: Any,
        store: AtomicJsonStore,
        backups: BackupManager,
        clock: Any = time.monotonic,
        sleep: Any = asyncio.sleep,
    ) -> None:
        self.backend = backend
        self.store = store
        self.backups = backups
        self.state = store.load()
        self._lock = asyncio.Lock()
        self._cancel_requested = asyncio.Event()
        self._clock = clock
        self._sleep = sleep

    def public_state(self) -> Dict[str, Any]:
        value = dict(self.state)
        value["backup_available"] = isinstance(value.get("backup"), dict)
        value.pop("backup", None)
        value.pop("meshes", None)
        value.pop("candidate_matrix", None)
        if isinstance(value.get("qualification"), dict):
            value["qualification"] = dict(value["qualification"])
            value["qualification"].pop("candidate_matrix", None)
        return value

    def _transition(self, phase: str, **updates: Any) -> None:
        self.state.update(updates)
        self.state["phase"] = phase
        self.store.save(self.state)

    @staticmethod
    def _profile(config: Dict[str, Any]) -> str:
        return "k1_p%03d_t%03d_r%03d_n%02dx%02d" % (
            config["plate_id"], config["bed_temp_c"], config["probe_revision"],
            config["x_count"], config["y_count"],
        )

    async def _turn_off_heaters(self) -> None:
        try:
            await self.backend.run_gcode("TURN_OFF_HEATERS")
        except Exception:
            pass

    async def _clear_mesh_best_effort(self) -> None:
        try:
            await self.backend.run_gcode("BED_MESH_CLEAR")
        except Exception:
            pass

    def request_cancel(self) -> Dict[str, Any]:
        self._cancel_requested.set()
        if self.state.get("busy"):
            self._transition("cancelling", last_error=None)
        return self.public_state()

    def _check_cancelled(self) -> None:
        if self._cancel_requested.is_set():
            raise asyncio.CancelledError()

    async def _preheat(self, config: Dict[str, Any]) -> None:
        self._check_cancelled()
        await self.backend.run_gcode("M140 S%d" % config["bed_temp_c"])
        await self.backend.run_gcode("M104 S%d" % config["nozzle_temp_c"])
        deadline = self._clock() + 1200
        while self._clock() < deadline:
            self._check_cancelled()
            status = await self.backend.query_status()
            bed = status.get("heater_bed", {})
            nozzle = status.get("extruder", {})
            if (
                float(bed.get("target", 0)) == config["bed_temp_c"]
                and float(nozzle.get("target", 0)) == config["nozzle_temp_c"]
                and float(bed.get("temperature", 0)) >= config["bed_temp_c"] - 1.0
                and float(nozzle.get("temperature", 0)) >= config["nozzle_temp_c"] - 1.0
            ):
                break
            await self._sleep(1)
        else:
            raise CalibrationError("Les températures de calibration ne sont pas atteintes.")
        soak_deadline = self._clock() + config["soak_seconds"]
        while self._clock() < soak_deadline:
            self._check_cancelled()
            await self._sleep(max(0.0, min(1.0, soak_deadline - self._clock())))
        self._check_cancelled()
        await self.backend.run_gcode(
            "SET_GCODE_VARIABLE MACRO=KCTRL_STATE VARIABLE=low_moves_armed VALUE=0"
        )
        await self.backend.run_gcode(
            "SET_GCODE_VARIABLE MACRO=KCTRL_STATE VARIABLE=armed_mesh_profile VALUE='\"none\"'"
        )
        await self.backend.run_gcode(
            "SET_GCODE_VARIABLE MACRO=KCTRL_STATE VARIABLE=expected_nozzle_c VALUE=%d" %
            config["nozzle_temp_c"]
        )
        await self.backend.run_gcode(
            "SET_GCODE_VARIABLE MACRO=KCTRL_STATE VARIABLE=temperature_owner VALUE='\"calibration\"'"
        )

    async def run_mesh_campaign(self, raw_config: Dict[str, Any], plate_clear: bool) -> Dict[str, Any]:
        if not plate_clear:
            raise CalibrationError("Le plateau libre doit être confirmé.")
        config = validate_config(raw_config)
        async with self._lock:
            if self.state.get("busy"):
                raise CalibrationError("Une calibration est déjà en cours.")
            self._cancel_requested.clear()
            campaign_id = "%s-%03d-calibration-ui-v1" % (
                time.strftime("%Y%m%d-%H%M%S", time.localtime()),
                int(time.time() * 1000) % 1000,
            )
            self.state = default_state()
            self._transition(
                "preflight", busy=True, campaign_id=campaign_id, config=config,
                meshes=[], mesh_index=0, last_error=None,
            )
            try:
                status = await self.backend.query_status()
                self._assert_start_state(
                    status, self._profile(config), config["replace_existing"]
                )
                backup = self.backups.create(campaign_id)
                self._transition("preparing", backup=backup)
                await self.backend.run_gcode("BED_MESH_CLEAR")
                await self._preheat(config)
                await self.backend.run_gcode(
                    "NOZZLE_CLEAR HOT_MIN_TEMP=%d HOT_MAX_TEMP=180 BED_MAX_TEMP=%d" %
                    (config["nozzle_temp_c"], config["bed_temp_c"])
                )
                self._check_cancelled()
                await self.backend.run_gcode("KCTRL_CALIBRATION_HOME")
                self._check_cancelled()
                for index in range(MESH_COUNT):
                    self._transition("measuring", mesh_index=index + 1)
                    await self.backend.run_gcode(
                        "KCTRL_MESH_CALIBRATE X_COUNT=%d Y_COUNT=%d ALGORITHM=%s" %
                        (config["x_count"], config["y_count"], config["algorithm"])
                    )
                    self._check_cancelled()
                    status = await self.backend.query_status()
                    matrix = validate_matrix(
                        status.get("bed_mesh", {}).get("probed_matrix"),
                        config["y_count"], config["x_count"],
                    )
                    self.state["meshes"].append(matrix)
                    self.store.save(self.state)
                self._transition("qualifying")
                self._check_cancelled()
                qualification = aggregate_meshes(
                    self.state["meshes"], config["y_count"], config["x_count"]
                )
                self.state["qualification"] = qualification
                self.state["candidate_matrix"] = qualification["candidate_matrix"]
                self.store.save(self.state)
                if not qualification["accepted"]:
                    await self._clear_mesh_best_effort()
                    await self._turn_off_heaters()
                    self._transition("mesh_rejected", busy=False)
                    return self.public_state()
                self._transition("committing_mesh")
                self._check_cancelled()
                await self.backend.update_mesh(qualification["candidate_matrix"])
                await self.backend.wait_klippy_ready(120)
                self._check_cancelled()
                await self.backend.run_gcode("BED_MESH_PROFILE LOAD=K1_TRANSIENT")
                status = await self.backend.query_status()
                self._assert_same_matrix(
                    status.get("bed_mesh", {}).get("probed_matrix"),
                    qualification["candidate_matrix"],
                    config["y_count"], config["x_count"],
                )
                self._check_cancelled()
                try:
                    await self.backend.run_gcode(
                        "KCTRL_MESH_COMMIT PLATE=%d TEMP_BAND=%d PROBE_REV=%d X_COUNT=%d Y_COUNT=%d" %
                        (config["plate_id"], config["bed_temp_c"], config["probe_revision"],
                         config["x_count"], config["y_count"]),
                        disconnect_ok=True,
                    )
                finally:
                    await self.backend.wait_klippy_ready(120)
                status = await self.backend.query_status()
                profiles = status.get("bed_mesh", {}).get("profiles", {})
                if self._profile(config) not in profiles or "K1_TRANSIENT" in profiles:
                    raise CalibrationError("Le profil robuste n'est pas persisté proprement.")
                self._assert_same_matrix(
                    profiles[self._profile(config)].get("points"),
                    qualification["candidate_matrix"],
                    config["y_count"], config["x_count"],
                )
                self._check_cancelled()
                self._transition("mesh_ready", busy=False)
                return self.public_state()
            except asyncio.CancelledError:
                await self._clear_mesh_best_effort()
                await self._turn_off_heaters()
                self._transition("cancelled", busy=False, last_error="Campagne annulée.")
                raise
            except Exception as error:
                await self._turn_off_heaters()
                self._transition("failed", busy=False, last_error=str(error))
                raise

    async def begin_z(self, plate_clear: bool, nozzle_clean: bool) -> Dict[str, Any]:
        if not plate_clear or not nozzle_clean:
            raise CalibrationError("Plateau libre et buse propre doivent être confirmés.")
        async with self._lock:
            if self.state.get("phase") != "mesh_ready" or self.state.get("busy"):
                raise CalibrationError("Le mesh robuste n'est pas prêt.")
            self._cancel_requested.clear()
            config = validate_config(self.state["config"])
            self._transition("starting_z", busy=True)
            try:
                await self._preheat(config)
                await self.backend.run_gcode("KCTRL_CALIBRATION_HOME")
                self._check_cancelled()
                await self.backend.run_gcode(
                    "KCTRL_CAL_PATH_LOAD_MESH PLATE=%d TEMP_BAND=%d PROBE_REV=%d X_COUNT=%d Y_COUNT=%d BED_TEMP=%d NOZZLE_TEMP=%d" %
                    (config["plate_id"], config["bed_temp_c"], config["probe_revision"],
                     config["x_count"], config["y_count"], config["bed_temp_c"], config["nozzle_temp_c"])
                )
                self._check_cancelled()
                await self.backend.run_gcode(
                    "KCTRL_CAL_PATH_START_Z SEED=%s PLATE=%d TEMP_BAND=%d PROBE_REV=%d NOZZLE_ID=%d CONFIG_ID=%d" %
                    (config["seed_offset_mm"], config["plate_id"], config["bed_temp_c"],
                     config["probe_revision"], config["nozzle_id"], config["config_id"])
                )
                self._check_cancelled()
                await self.backend.run_gcode("KCTRL_CAL_PATH_BEGIN CLEAR_PLATE=1 CLEAN_NOZZLE=1")
                self._check_cancelled()
                self._transition("z_testing", busy=False, z_ladder_index=0)
                return self.public_state()
            except asyncio.CancelledError:
                await self._turn_off_heaters()
                self._transition("cancelled", busy=False, last_error="Campagne annulée.")
                raise
            except Exception as error:
                await self._turn_off_heaters()
                self._transition("failed", busy=False, last_error=str(error))
                raise

    async def step_z(self) -> Dict[str, Any]:
        async with self._lock:
            if self.state.get("phase") != "z_testing" or self.state.get("busy"):
                raise CalibrationError("La session Z n'est pas disponible.")
            current = int(self.state.get("z_ladder_index", 0))
            if current >= len(Z_LADDER_MM) - 1:
                raise CalibrationError("Le dernier palier Z est déjà atteint.")
            next_index = current + 1
            await self.backend.run_gcode("KCTRL_CAL_PATH_MOVE HEIGHT=%s" % Z_LADDER_MM[next_index])
            self._transition("z_testing", z_ladder_index=next_index)
            return self.public_state()

    async def adjust_z(self, delta: float) -> Dict[str, Any]:
        value = float(delta)
        if value not in Z_ADJUSTMENTS_MM:
            raise CalibrationError("Ajustement Z non autorisé.")
        async with self._lock:
            if self.state.get("phase") != "z_testing" or self.state.get("z_ladder_index") != len(Z_LADDER_MM) - 1:
                raise CalibrationError("Les ajustements sont limités au dernier palier 0,1 mm.")
            await self.backend.run_gcode("KCTRL_CAL_PATH_ADJUST DELTA=%s" % value)
            return self.public_state()

    async def confirm_gap(self, observed: bool) -> Dict[str, Any]:
        if not observed:
            raise CalibrationError("Le jeu final doit être réellement observé.")
        async with self._lock:
            if self.state.get("phase") != "z_testing" or self.state.get("z_ladder_index") != len(Z_LADDER_MM) - 1:
                raise CalibrationError("Le dernier palier Z n'est pas atteint.")
            await self.backend.run_gcode("KCTRL_CAL_PATH_CONFIRM_GAP CONFIRMED=1")
            await self.backend.run_gcode("KCTRL_CAL_PATH_PARK")
            self._transition("z_confirmed")
            return self.public_state()

    async def accept_z(self) -> Dict[str, Any]:
        async with self._lock:
            if self.state.get("phase") != "z_confirmed":
                raise CalibrationError("Le jeu Z n'est pas confirmé.")
            accepted_at = int(time.time())
            await self.backend.run_gcode("KCTRL_CAL_PATH_COMMIT_Z ACCEPTED_AT=%d" % accepted_at)
            await self._turn_off_heaters()
            status = await self.backend.query_status()
            runtime = status.get("gcode_macro KCTRL_STATE", {})
            if int(runtime.get("accepted_z_valid", 0)) != 1:
                raise CalibrationError("Le Z accepté n'est pas relu dans le runtime.")
            self._transition("accepted", busy=False, accepted_at=accepted_at)
            return self.public_state()

    async def cancel(self) -> Dict[str, Any]:
        async with self._lock:
            status = await self.backend.query_status()
            path = status.get("gcode_macro KCTRL_CAL_PATH_STATE", {})
            runtime = status.get("gcode_macro KCTRL_STATE", {})
            if int(path.get("motion_armed", 0)) == 1:
                await self.backend.run_gcode("KCTRL_CAL_PATH_PARK")
            if int(runtime.get("session_active", 0)) == 1:
                await self.backend.run_gcode("KCTRL_CAL_PATH_CANCEL_Z")
            await self._turn_off_heaters()
            self._transition("cancelled", busy=False)
            return self.public_state()

    async def restore_previous_z(self) -> Dict[str, Any]:
        async with self._lock:
            status = await self.backend.query_status()
            runtime = status.get("gcode_macro KCTRL_STATE", {})
            if (
                status.get("print_stats", {}).get("state") != "standby"
                or "xyz" not in str(status.get("toolhead", {}).get("homed_axes", ""))
                or int(runtime.get("previous_z_valid", 0)) != 1
            ):
                raise CalibrationError(
                    "Le Z précédent exige un enregistrement disponible et les axes XYZ référencés."
                )
            await self.backend.run_gcode("KCTRL_Z_RESTORE_PREVIOUS")
            self._transition("restored", busy=False)
            return self.public_state()

    async def rollback_campaign(self) -> Dict[str, Any]:
        async with self._lock:
            if self.state.get("busy"):
                raise CalibrationError("La campagne doit d'abord être annulée.")
            campaign_id = self.state.get("campaign_id")
            backup = self.state.get("backup")
            if not campaign_id or not isinstance(backup, dict):
                raise CalibrationError("Aucun backup de campagne n'est disponible.")
            status = await self.backend.query_status()
            path = status.get("gcode_macro KCTRL_CAL_PATH_STATE", {})
            runtime = status.get("gcode_macro KCTRL_STATE", {})
            if int(path.get("motion_armed", 0)) == 1:
                await self.backend.run_gcode("KCTRL_CAL_PATH_PARK")
            if int(runtime.get("session_active", 0)) == 1:
                await self.backend.run_gcode("KCTRL_CAL_PATH_CANCEL_Z")
            await self._turn_off_heaters()
            restored = self.backups.restore(str(campaign_id), backup)
            try:
                await self.backend.run_gcode("RESTART", disconnect_ok=True)
            finally:
                await self.backend.wait_klippy_ready(120)
            self._transition("rolled_back", busy=False, rollback=restored)
            return self.public_state()

    @staticmethod
    def _assert_start_state(
        status: Dict[str, Any], target_profile: str, replace_existing: bool
    ) -> None:
        stats = status.get("print_stats", {})
        if stats.get("state") != "standby" or stats.get("filename"):
            raise CalibrationError("L'imprimante n'est pas au repos.")
        if float(status.get("extruder", {}).get("target", 0)) != 0 or float(status.get("heater_bed", {}).get("target", 0)) != 0:
            raise CalibrationError("Une chauffe est déjà demandée.")
        runtime = status.get("gcode_macro KCTRL_STATE", {})
        if int(runtime.get("ready", 0)) != 1 or int(runtime.get("session_active", 0)) != 0 or int(runtime.get("low_moves_armed", 0)) != 0:
            raise CalibrationError("Le runtime K1 Control n'est pas vide et fermé.")
        path = status.get("gcode_macro KCTRL_CAL_PATH_STATE", {})
        if path.get("phase") != "idle" or int(path.get("motion_armed", 0)) != 0:
            raise CalibrationError("Le chemin de calibration n'est pas fermé.")
        if target_profile in status.get("bed_mesh", {}).get("profiles", {}) and not replace_existing:
            raise CalibrationError("Le profil cible existe déjà.")

    @staticmethod
    def _assert_same_matrix(
        actual: Any, expected: Any, rows: int, columns: int
    ) -> None:
        left = validate_matrix(actual, rows, columns)
        right = validate_matrix(expected, rows, columns)
        for row in range(rows):
            for column in range(columns):
                if abs(left[row][column] - right[row][column]) > 0.000001:
                    raise CalibrationError("Le maillage relu diffère du candidat robuste.")
