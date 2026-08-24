#!/usr/bin/env python3
"""In-memory API simulation for the offline mesh editor."""

from __future__ import annotations

import json
import threading
from typing import Any, Dict, Mapping, Optional, Tuple

from klipper_profile import render_klipper_profile
from mesh_editor_core import (
    DERIVED_PROFILE_ID,
    SOURCE_ID,
    MeshEditor,
    MeshEditorError,
)


ApiResult = Tuple[int, Any, str]


class FakeMeshEditorApi:
    """Future-shaped domain API with no network or persistent side effect."""

    def __init__(self) -> None:
        self.editor: Optional[MeshEditor] = None
        self.scenario = "ready"
        self._lock = threading.RLock()

    def _require_editor(self, profile_id: str) -> MeshEditor:
        if self.editor is None:
            raise MeshEditorError("crée d'abord le profil dérivé v001")
        if profile_id != DERIVED_PROFILE_ID:
            raise MeshEditorError("le profil dérivé demandé est inconnu")
        return self.editor

    def _status(self) -> Dict[str, Any]:
        profile = self.editor.state() if self.editor is not None else None
        return {
            "schema": "k1-control.mesh-editor.fake-api-status.v1",
            "mode": "offline_simulation",
            "scenario": self.scenario,
            "busy": self.scenario == "loading",
            "simulated_validation_error": (
                "Correction simulée refusée, aucune donnée n'a changé."
                if self.scenario == "validation_error"
                else None
            ),
            "profile": profile,
            "capabilities": {
                "create": True,
                "correct": True,
                "undo": True,
                "redo": True,
                "restore": True,
                "export_json": True,
                "export_klipper": True,
                "printer_connection": False,
                "deployment": False,
            },
        }

    def handle(
        self,
        method: str,
        path: str,
        payload: Optional[Mapping[str, Any]] = None,
    ) -> ApiResult:
        with self._lock:
            return self._handle_unlocked(method, path, payload)

    def _handle_unlocked(
        self,
        method: str,
        path: str,
        payload: Optional[Mapping[str, Any]] = None,
    ) -> ApiResult:
        payload = payload or {}
        try:
            if method == "GET" and path == "/api/mesh-editor/v1/status":
                return 200, self._status(), "application/json"

            if method == "POST" and path == "/api/mesh-editor/v1/profiles":
                if payload.get("source_id") != SOURCE_ID or payload.get("version") != 1:
                    raise MeshEditorError(
                        "seule la dérivation v001 de la source physique qualifiée est permise"
                    )
                self.editor = MeshEditor()
                self.scenario = "ready"
                return 201, self._status(), "application/json"

            if method == "POST" and path == "/api/mesh-editor/v1/simulation":
                scenario = payload.get("scenario")
                if scenario not in ("ready", "loading", "validation_error", "restored"):
                    raise MeshEditorError("le scénario simulé est inconnu")
                if scenario == "restored" and self.editor is not None:
                    self.editor.restore_source()
                self.scenario = scenario
                return 200, self._status(), "application/json"

            prefix = "/api/mesh-editor/v1/profiles/"
            if not path.startswith(prefix):
                return 404, {"error": "route_not_found"}, "application/json"
            remainder = path[len(prefix) :]
            profile_id, separator, action_path = remainder.partition("/")
            if not separator:
                return 404, {"error": "route_not_found"}, "application/json"
            editor = self._require_editor(profile_id)

            if method == "POST" and action_path == "corrections":
                if self.scenario == "validation_error":
                    return (
                        422,
                        {
                            "error": "simulated_validation_error",
                            "message": "Correction simulée refusée, aucune donnée n'a changé.",
                            "state": editor.state(),
                        },
                        "application/json",
                    )
                result = editor.apply_correction(
                    payload.get("selection"),
                    str(payload.get("direction", "")),
                    payload.get("step_mm"),
                )
                self.scenario = "ready"
                return 200, result, "application/json"

            if method == "POST" and action_path == "actions":
                action = payload.get("action")
                if action == "undo":
                    state = editor.undo()
                elif action == "redo":
                    state = editor.redo()
                elif action == "restore_source":
                    state = editor.restore_source()
                    self.scenario = "restored"
                else:
                    raise MeshEditorError("l'action d'historique est inconnue")
                return 200, {"state": state}, "application/json"

            if method == "GET" and action_path == "export/json":
                document = editor.export_document()
                return (
                    200,
                    json.dumps(
                        document,
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=True,
                    )
                    + "\n",
                    "application/json",
                )

            if method == "GET" and action_path == "export/klipper":
                return (
                    200,
                    render_klipper_profile(editor.export_document()),
                    "text/plain; charset=utf-8",
                )

            return 404, {"error": "route_not_found"}, "application/json"
        except MeshEditorError as error:
            return (
                422,
                {"error": "validation_error", "message": str(error)},
                "application/json",
            )
