"""Creality prtouch_v3 probe-count adapter for K1 Control calibration.

The proprietary prtouch_v3 BED_MESH_CALIBRATE implementation reads the
``[bed_mesh] probe_count`` and ``algorithm`` values loaded at Klipper start. It
does not honour the dynamic arguments like upstream Klipper. This component
wraps only the K1 Control calibration backend so the reviewed matrix and its
compatible interpolation are loaded before heating, then restores both values
after heaters are turned off.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import stat
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

if TYPE_CHECKING:
    from ..confighelper import ConfigHelper


ALLOWED_COUNTS = {(6, 6)}
ALLOWED_ALGORITHMS = {"lagrange", "bicubic"}
CLOSED_PATH_PHASES = {"idle", "committed", "cancelled"}
MeshConfiguration = Tuple[Tuple[int, int], str]
FileMeshConfiguration = Tuple[Tuple[int, int], Optional[str]]


class ProbeCountError(Exception):
    pass


class ProbeCountFile:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(65536), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _effective(configuration: FileMeshConfiguration) -> MeshConfiguration:
        count, algorithm = configuration
        return count, algorithm or "lagrange"

    @staticmethod
    def _rewrite(
        document: bytes,
        target: FileMeshConfiguration,
    ) -> Tuple[bytes, FileMeshConfiguration]:
        target_count, target_algorithm = target
        effective_target_algorithm = target_algorithm or "lagrange"
        if target_count not in ALLOWED_COUNTS:
            raise ProbeCountError(
                "Le PRTouch Creality de cette K1 est limité à 36 points physiques (6x6)."
            )
        if effective_target_algorithm != "lagrange":
            raise ProbeCountError("Seul Lagrange 6x6 est autorisé sur ce PRTouch.")
        lines = document.splitlines(keepends=True)
        in_bed_mesh = False
        section_count = 0
        count_match_count = 0
        algorithm_match_count = 0
        previous_count: Optional[Tuple[int, int]] = None
        previous_algorithm: Optional[str] = None
        rewritten = []
        count_line_index: Optional[int] = None
        count_indent = b""
        count_eol = b"\n"
        count_pattern = re.compile(
            rb"^(?P<prefix>[ \t]*probe_count[ \t]*:[ \t]*)"
            rb"(?P<x>[0-9]+)[ \t]*,[ \t]*(?P<y>[0-9]+)"
            rb"(?P<suffix>[ \t]*(?:[#;].*)?)(?P<eol>\r?\n)?$",
            re.IGNORECASE,
        )
        algorithm_pattern = re.compile(
            rb"^(?P<prefix>[ \t]*algorithm[ \t]*:[ \t]*)"
            rb"(?P<algorithm>[A-Za-z]+)"
            rb"(?P<suffix>[ \t]*(?:[#;].*)?)(?P<eol>\r?\n)?$",
            re.IGNORECASE,
        )
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(b"[") and stripped.endswith(b"]"):
                in_bed_mesh = stripped.lower() == b"[bed_mesh]"
                if in_bed_mesh:
                    section_count += 1
            if in_bed_mesh:
                count_match = count_pattern.match(line)
                if count_match:
                    count_match_count += 1
                    previous_count = (
                        int(count_match.group("x")),
                        int(count_match.group("y")),
                    )
                    count_line_index = len(rewritten)
                    count_indent = re.match(rb"^[ \t]*", line).group(0)
                    count_eol = count_match.group("eol") or b"\n"
                    line = (
                        count_match.group("prefix")
                        + ("%d,%d" % target_count).encode("ascii")
                        + count_match.group("suffix")
                        + (count_match.group("eol") or b"")
                    )
                algorithm_match = algorithm_pattern.match(line)
                if algorithm_match:
                    algorithm_match_count += 1
                    previous_algorithm = algorithm_match.group("algorithm").decode("ascii").lower()
                    if target_algorithm is None:
                        line = b""
                    else:
                        line = (
                            algorithm_match.group("prefix")
                            + target_algorithm.encode("ascii")
                            + algorithm_match.group("suffix")
                            + (algorithm_match.group("eol") or b"")
                        )
            rewritten.append(line)
        if (
            section_count != 1
            or count_match_count != 1
            or algorithm_match_count > 1
            or previous_count is None
            or count_line_index is None
        ):
            raise ProbeCountError("Le couple probe_count/algorithm [bed_mesh] n'est pas unique.")
        if previous_count not in ALLOWED_COUNTS or (
            previous_algorithm is not None and previous_algorithm not in ALLOWED_ALGORITHMS
        ):
            raise ProbeCountError("La configuration bed_mesh courante n'est pas une base revue.")
        if previous_algorithm is None and max(previous_count) > 6:
            raise ProbeCountError("Une matrice supérieure à 6 sans algorithme explicite est invalide.")
        if algorithm_match_count == 0 and target_algorithm is not None:
            rewritten.insert(
                count_line_index + 1,
                count_indent + b"algorithm: " + target_algorithm.encode("ascii") + count_eol,
            )
        return b"".join(rewritten), (previous_count, previous_algorithm)

    def read(self) -> FileMeshConfiguration:
        document = self.path.read_bytes()
        _, current = self._rewrite(document, ((6, 6), None))
        return current

    def write(self, target: FileMeshConfiguration) -> FileMeshConfiguration:
        source = self.path.read_bytes()
        rewritten, previous = self._rewrite(source, target)
        if previous == target:
            return previous
        mode = stat.S_IMODE(self.path.stat().st_mode)
        temporary = self.path.with_name(self.path.name + ".k1-control-bed-mesh.next")
        try:
            with temporary.open("wb") as stream:
                stream.write(rewritten)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(str(temporary), mode)
            if self._sha256(temporary) != hashlib.sha256(rewritten).hexdigest():
                raise ProbeCountError("La copie bed_mesh préparée est invalide.")
            os.replace(str(temporary), str(self.path))
        finally:
            if temporary.exists():
                temporary.unlink()
        if self.read() != target:
            raise ProbeCountError("La configuration bed_mesh écrite ne peut pas être relue.")
        return previous


class ProbeCountAwareBackend:
    def __init__(self, backend: Any, orchestrator: Any) -> None:
        self.backend = backend
        self.orchestrator = orchestrator
        self.config = ProbeCountFile(orchestrator.backups.printer_config)
        self.previous_config: Optional[FileMeshConfiguration] = None
        self.changed = False
        self._recover_existing_change()

    def _backup_config(self) -> Optional[FileMeshConfiguration]:
        evidence = self.orchestrator.state.get("backup")
        campaign_id = self.orchestrator.state.get("campaign_id")
        if not isinstance(evidence, dict) or not campaign_id:
            return None
        root = Path(str(evidence.get("root", "")))
        expected = self.orchestrator.backups.backup_root / str(campaign_id)
        try:
            if root.resolve() != expected.resolve():
                return None
        except OSError:
            return None
        backup = root / "printer.cfg.before"
        if not backup.is_file():
            return None
        expected_hash = str(evidence.get("printer_cfg_sha256", ""))
        if ProbeCountFile._sha256(backup) != expected_hash:
            return None
        return ProbeCountFile(backup).read()

    def _recover_existing_change(self) -> None:
        previous = self._backup_config()
        if previous is None:
            return
        current = self.config.read()
        if current != previous:
            self.previous_config = previous
            self.changed = True

    async def query_status(self) -> Dict[str, Any]:
        return await self.backend.query_status()

    async def update_mesh(self, matrix: Any) -> Any:
        return await self.backend.update_mesh(matrix)

    async def wait_klippy_ready(self, timeout: int) -> None:
        await self.backend.wait_klippy_ready(timeout)

    async def _loaded_config(self) -> MeshConfiguration:
        result = await self.backend.klippy_apis.query_objects({"configfile": None})
        bed_mesh = result.get("configfile", {}).get("settings", {}).get("bed_mesh", {})
        raw = bed_mesh.get("probe_count")
        algorithm = str(bed_mesh.get("algorithm", "")).lower()
        if not isinstance(raw, (list, tuple)) or len(raw) != 2:
            raise ProbeCountError("Le probe_count chargé n'est pas observable.")
        if algorithm not in ALLOWED_ALGORITHMS:
            raise ProbeCountError("L'algorithme bed_mesh chargé n'est pas observable.")
        return (int(raw[0]), int(raw[1])), algorithm

    @staticmethod
    def _safe_after_restart(status: Dict[str, Any]) -> bool:
        stats = status.get("print_stats", {})
        runtime = status.get("gcode_macro KCTRL_STATE", {})
        path = status.get("gcode_macro KCTRL_CAL_PATH_STATE", {})
        return (
            stats.get("state") == "standby"
            and not stats.get("filename")
            and float(status.get("extruder", {}).get("target", 0)) == 0
            and float(status.get("heater_bed", {}).get("target", 0)) == 0
            and int(runtime.get("ready", 0)) == 1
            and int(runtime.get("session_active", 0)) == 0
            and int(runtime.get("low_moves_armed", 0)) == 0
            and path.get("phase") in CLOSED_PATH_PHASES
            and int(path.get("motion_armed", 0)) == 0
        )

    async def _restart_and_verify(self, expected: MeshConfiguration) -> None:
        try:
            await self.backend.run_gcode("RESTART", disconnect_ok=True)
        finally:
            await self.backend.wait_klippy_ready(120)
        deadline = asyncio.get_running_loop().time() + 120
        last_error = "état non prêt"
        while asyncio.get_running_loop().time() < deadline:
            try:
                loaded = await self._loaded_config()
                status = await self.backend.query_status()
                if loaded == expected and self._safe_after_restart(status):
                    return
                last_error = "bed_mesh=%s, safe=%s" % (
                    loaded,
                    self._safe_after_restart(status),
                )
            except Exception as error:
                last_error = str(error)
            await asyncio.sleep(1)
        raise ProbeCountError("Klipper n'a pas chargé la matrice sûre : %s" % last_error)

    def _assert_backup_precedes_change(self) -> None:
        previous = self._backup_config()
        if previous is None:
            raise ProbeCountError("Le backup exact doit précéder le changement de matrice.")

    async def _configure(self, target: MeshConfiguration) -> None:
        target_count, target_algorithm = target
        if target_count not in ALLOWED_COUNTS:
            raise ProbeCountError("Matrice non compatible avec prtouch_v3.")
        if target_algorithm not in ALLOWED_ALGORITHMS:
            raise ProbeCountError("Interpolation non compatible avec prtouch_v3.")
        if max(target_count) > 6 and target_algorithm != "bicubic":
            raise ProbeCountError("Les matrices supérieures à 6 exigent bicubic au démarrage.")
        loaded = await self._loaded_config()
        current_file = self.config.read()
        current = ProbeCountFile._effective(current_file)
        if loaded != current:
            raise ProbeCountError("printer.cfg et la configuration bed_mesh chargée divergent.")
        if current == target:
            return
        self._assert_backup_precedes_change()
        previous = self.config.write((target_count, target_algorithm))
        self.previous_config = previous
        self.changed = True
        try:
            await self._restart_and_verify(target)
        except Exception:
            try:
                self.config.write(previous)
                await self._restart_and_verify(ProbeCountFile._effective(previous))
                self.changed = False
                self.previous_config = None
            except Exception:
                logging.exception("K1 Control probe_count rollback failed")
            raise

    async def _restore(self) -> None:
        if not self.changed or self.previous_config is None:
            return
        previous = self.previous_config
        self.config.write(previous)
        await self._restart_and_verify(ProbeCountFile._effective(previous))
        self.changed = False
        self.previous_config = None

    async def run_gcode(self, script: str, disconnect_ok: bool = False) -> Any:
        state = self.orchestrator.state
        if script == "BED_MESH_CLEAR" and state.get("phase") == "preparing":
            config = state.get("config") or {}
            target = (
                (int(config.get("x_count", 0)), int(config.get("y_count", 0))),
                str(config.get("algorithm", "")).lower(),
            )
            await self._configure(target)
        result = await self.backend.run_gcode(script, disconnect_ok=disconnect_ok)
        if script == "TURN_OFF_HEATERS" and self.changed:
            try:
                await self._restore()
            except Exception:
                logging.exception("K1 Control probe_count restore after heaters-off failed")
                raise
        return result


class K1ControlProbeCount:
    def __init__(self, config: "ConfigHelper") -> None:
        self.server = config.get_server()

    def component_init(self) -> None:
        control = self.server.lookup_component("k1_control")
        orchestrator = control.orchestrator
        if isinstance(orchestrator.backend, ProbeCountAwareBackend):
            return
        orchestrator.backend = ProbeCountAwareBackend(orchestrator.backend, orchestrator)


def load_component(config: "ConfigHelper") -> K1ControlProbeCount:
    return K1ControlProbeCount(config)
