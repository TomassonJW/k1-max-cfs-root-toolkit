"""Extension bornée du cœur pur pour fermeture sûre avant/après impression."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from . import k1_control_stock_cycle_core as base


SAFE_CLOSE_PHASES = {
    "await_empty_filament",
    "await_manual_clean",
    "geometry_ready_to_dispatch",
    "geometry_pending",
    "initial_load_ready",
    "await_release_camera",
    "initial_prime_ready",
    "await_prime_camera",
    "ready_to_print",
    "printing",
    "await_tool_change_camera",
    "await_refill_camera",
    "failed_safe",
}


class ActiveStockDerivedOrchestrator(base.StockDerivedOrchestrator):
    """Ajoute uniquement une sortie terminale explicite, jamais un retry."""

    @staticmethod
    def _intentional_unload_prefix():
        return [
            "KCTRL_CFS_RUNOUT_DISARM_V1",
            "SET_FILAMENT_SENSOR SENSOR=filament_sensor ENABLE=0",
            "SET_FILAMENT_SENSOR SENSOR=filament_sensor_2 ENABLE=0",
        ]

    def plan_preclean_unload(self, *, reconcile_required=True):
        self._require_phase("preclean_unload_ready")
        route = self._active_route()
        ticket_id = self._next_ticket_id("preclean-unload")
        reconcile = []
        if reconcile_required:
            reconcile.append(
                "KCTRL_CFS_DIRECT_RECONCILE ROUTE=%s OBSERVATION_ID=%s-reconcile"
                % (route, ticket_id)
            )
        command = "\n".join(
            reconcile
            + self._intentional_unload_prefix()
            + [self._cut_unload_command(route, ticket_id)]
        )
        return self._claim(
            "preclean_unload", command, "preclean_unload_pending", ticket_id
        )

    def plan_geometry(self):
        self._require_phase("geometry_ready_to_dispatch")
        self._require_current_geometry_runtime()
        ticket_id = self._next_ticket_id("geometry")
        command = "\n".join([
            "KCTRL_PREPARE_GEOMETRY_BEFORE_INSERTION_R4 "
            "BED=55 PROBE_NOZZLE=140 FIRST_NOZZLE=190 "
            "PLATE=1 PROBE_REV=1 NOZZLE_ID=1 CONFIG_ID=1 X_COUNT=11 Y_COUNT=11",
            "KCTRL_STOCK_GEOMETRY_HANDOFF_TAKE_V1 EFFECT_ID=%s-handoff"
            % ticket_id,
        ])
        return self._claim(
            "geometry_before_filament", command, "geometry_pending", ticket_id
        )

    def plan_equivalent_refill(self, pause_context: Mapping[str, Any]):
        """Remplace une bobine epuisee sans couper un filament deja absent.

        Le runout stock qualifie vide les deux capteurs apres sa poussee visible
        de 30 mm. Le ticket persiste d'abord la liberation *logique* de la route
        epuisee, sans moteur, puis reutilise le chargement/purge direct qualifie.
        Une rupture avec un segment encore present reste en pause et sans effet.
        """

        self._require_phase("printing")
        source = self._active_route()
        target, digest = self._unique_identical_spare(source)
        if not isinstance(pause_context, Mapping):
            self._fail("runout_pause_context_invalid")
        if pause_context.get("pause_latched") is not True:
            self._fail("runout_pause_not_latched")
        if pause_context.get("engaged_route") != source:
            self._fail("runout_pause_route_invalid")
        if pause_context.get("runout_owner") != "k1_control_cfs_runout_owner":
            self._fail("runout_signal_owner_invalid")
        signal_seq = pause_context.get("runout_signal_seq")
        if isinstance(signal_seq, bool) or not isinstance(signal_seq, int) or signal_seq < 1:
            self._fail("runout_signal_seq_invalid")
        if pause_context.get("head_sensor") is not False:
            self._fail("runout_head_tail_not_clear")
        if pause_context.get("after_cutter_sensor") is not False:
            self._fail("runout_after_cutter_tail_not_clear")
        active_c = pause_context.get("nozzle_target_c")
        if isinstance(active_c, bool) or not isinstance(active_c, (int, float)):
            self._fail("runout_nozzle_target_invalid")
        active_c = float(active_c)
        if not self.job["material_min_c"] <= active_c <= self.job["material_max_c"]:
            self._fail("runout_nozzle_target_out_of_bounds")
        context = deepcopy(dict(pause_context))
        ticket_id = self._next_ticket_id("equivalent-refill")
        guard = (
            "KCTRL_STOCK_CYCLE_REFILL_GUARD_V1 FROM=%s TO=%s "
            "SOURCE_IDENTITY=%s TARGET_IDENTITY=%s CANDIDATES=1 PAUSE_LATCHED=1"
            % (source, target, digest, digest)
        )
        command = "\n".join(
            [
                guard,
                (
                    "KCTRL_CFS_RUNOUT_RELEASE_V1 ROUTE=%s EFFECT_ID=%s-release"
                    % (source, ticket_id)
                ),
                (
                    "KCTRL_STOCK_CYCLE_LOAD_PURGE_V1 ROUTE=%s EFFECT_ID=%s-load "
                    "LOAD_C=%s PURGE_C=%s PURGE_MM=%s TRIPS=%d "
                    "MATERIAL_MIN_C=%s MATERIAL_MAX_C=%s"
                    % (
                        target,
                        ticket_id,
                        base._format_number(active_c),
                        base._format_number(active_c),
                        base._format_number(self.job["purge_mm"]),
                        int(self.job["release_trips"]),
                        base._format_number(self.job["material_min_c"]),
                        base._format_number(self.job["material_max_c"]),
                    )
                ),
            ]
        )
        self.state["pause_context"] = context
        self.state["planned_target_route"] = target
        return self._claim(
            "equivalent_refill", command, "equivalent_refill_pending", ticket_id
        )

    def plan_tool_change(self, target_route: str, pause_context=None):
        self._require_phase("printing")
        target = base._route(target_route, "tool_change_target_invalid")
        source = self._active_route()
        if target == source:
            self._fail("tool_change_target_same_as_source")
        self._require_available_target(target)
        source_material = self.inventory[source]["material"]
        target_material = self.inventory[target]["material"]
        if base.material_digest(source_material) != base.material_digest(target_material):
            # Une couleur ou matiere differente doit utiliser la paire exacte
            # source -> cible de la matrice de rincage Orca. Tant que la route
            # physique n'est pas associee sans ambiguite aux outils du G-code,
            # une purge generique est interdite.
            self._fail("gcode_transition_purge_not_resolved")
        if not isinstance(pause_context, Mapping) or pause_context.get("pause_latched") is not True:
            self._fail("tool_change_pause_not_latched")
        active_c = pause_context.get("nozzle_target_c")
        if isinstance(active_c, bool) or not isinstance(active_c, (int, float)):
            self._fail("tool_change_nozzle_target_invalid")
        active_c = float(active_c)
        if not self.job["material_min_c"] <= active_c <= self.job["material_max_c"]:
            self._fail("tool_change_nozzle_target_out_of_bounds")
        ticket_id = self._next_ticket_id("tool-change")
        unload = (
            "KCTRL_STOCK_CYCLE_CUT_UNLOAD_V1 ROUTE=%s EFFECT_ID=%s-unload "
            "UNLOAD_C=%s MATERIAL_MIN_C=%s MATERIAL_MAX_C=%s"
            % (
                source,
                ticket_id,
                base._format_number(active_c),
                base._format_number(self.job["material_min_c"]),
                base._format_number(self.job["material_max_c"]),
            )
        )
        load = (
            "KCTRL_STOCK_CYCLE_LOAD_PURGE_V1 ROUTE=%s EFFECT_ID=%s-load "
            "LOAD_C=%s PURGE_C=%s PURGE_MM=%s TRIPS=%d "
            "MATERIAL_MIN_C=%s MATERIAL_MAX_C=%s"
            % (
                target,
                ticket_id,
                base._format_number(active_c),
                base._format_number(active_c),
                base._format_number(self.job["purge_mm"]),
                int(self.job["release_trips"]),
                base._format_number(self.job["material_min_c"]),
                base._format_number(self.job["material_max_c"]),
            )
        )
        self.state["pause_context"] = deepcopy(dict(pause_context))
        self.state["planned_target_route"] = target
        return self._claim(
            "tool_change",
            "\n".join(self._intentional_unload_prefix() + [unload, load]),
            "tool_change_pending",
            ticket_id,
        )

    def complete_tool_change(self, ticket_id: str, proof: Mapping[str, Any]):
        pause_context = self.state.get("pause_context")
        if not isinstance(pause_context, Mapping):
            self._fail("tool_change_pause_context_missing")
        if abs(float(proof.get("active_nozzle_target_c", -999.0)) - float(pause_context["nozzle_target_c"])) > 0.01:
            self._fail("tool_change_temperature_changed")
        return super().complete_tool_change(ticket_id, proof)

    def plan_empty_runout_safe_close(
        self, reason: str, pause_context: Mapping[str, Any]
    ):
        """Refroidit et gare sans cutter apres une vraie fin de bobine.

        Cette sortie est reservee au cas ou aucun secours unique et strictement
        identique ne peut etre choisi. La route epuisee est d'abord liberee
        logiquement par le verrou runout, puis la machine est fermee sans aucun
        mouvement CFS. Le ticket unique couvre les deux commandes : aucun
        fragment n'est rejoue si leur resultat devient incertain.
        """

        if self.state.get("phase") != "failed_safe":
            self._fail("empty_runout_close_phase_invalid")
        if self.state.get("pending_ticket") is not None:
            self._block("empty_runout_close_pending_ticket", uncertain=True)
        if not isinstance(reason, str) or not reason or len(reason) > 96:
            self._fail("empty_runout_close_reason_invalid")
        if not isinstance(pause_context, Mapping):
            self._fail("empty_runout_close_context_invalid")
        route = self._active_route()
        if (
            pause_context.get("pause_latched") is not True
            or pause_context.get("engaged_route") != route
            or pause_context.get("runout_owner") != "k1_control_cfs_runout_owner"
            or pause_context.get("head_sensor") is not False
            or pause_context.get("after_cutter_sensor") is not False
        ):
            self._fail("empty_runout_close_proof_invalid")
        signal_seq = pause_context.get("runout_signal_seq")
        if isinstance(signal_seq, bool) or not isinstance(signal_seq, int) or signal_seq < 1:
            self._fail("empty_runout_close_signal_invalid")
        ticket_id = self._next_ticket_id("empty-runout-close")
        command = "\n".join([
            "KCTRL_CFS_RUNOUT_RELEASE_V1 ROUTE=%s EFFECT_ID=%s-release"
            % (route, ticket_id),
            "KCTRL_STOCK_CYCLE_EMPTY_END_V1 EFFECT_ID=%s" % ticket_id,
        ])
        self._trace("empty_runout_close_requested", reason=reason, route=route)
        return self._claim(
            "empty_runout_safe_close", command, "normal_end_pending", ticket_id
        )

    def plan_end(self):
        self._require_phase("printing")
        route = self._active_route()
        ticket_id = self._next_ticket_id("normal-end")
        command = (
            "KCTRL_STOCK_CYCLE_END_V1 ROUTE=%s EFFECT_ID=%s "
            "UNLOAD_C=%s MATERIAL_MIN_C=%s MATERIAL_MAX_C=%s"
            % (
                route,
                ticket_id,
                base._format_number(self.job["unload_c"]),
                base._format_number(self.job["material_min_c"]),
                base._format_number(self.job["material_max_c"]),
            )
        )
        return self._claim(
            "normal_end",
            "\n".join(self._intentional_unload_prefix() + [command]),
            "normal_end_pending",
            ticket_id,
        )

    def plan_safe_close(self, reason: str):
        if not isinstance(reason, str) or not reason or len(reason) > 96:
            self._fail("safe_close_reason_invalid")
        if self.state.get("pending_ticket") is not None:
            self._block("safe_close_blocked_by_pending_ticket", uncertain=True)
        if self.state.get("phase") not in SAFE_CLOSE_PHASES:
            self._fail("safe_close_phase_invalid")
        self._trace("safe_close_requested", reason=reason)
        if self.state.get("filament_loaded") is not True:
            self.state["active_route"] = None
            self.state["phase"] = "owner_release_pending"
            self._trace("safe_close_no_filament")
            return {"ticket_id": None, "command": None, "state": self.snapshot()}
        route = self._active_route()
        ticket_id = self._next_ticket_id("safe-close")
        command = (
            "KCTRL_STOCK_CYCLE_END_V1 ROUTE=%s EFFECT_ID=%s "
            "UNLOAD_C=%s MATERIAL_MIN_C=%s MATERIAL_MAX_C=%s"
            % (
                route,
                ticket_id,
                base._format_number(self.job["unload_c"]),
                base._format_number(self.job["material_min_c"]),
                base._format_number(self.job["material_max_c"]),
            )
        )
        return self._claim(
            "safe_close",
            "\n".join(self._intentional_unload_prefix() + [command]),
            "normal_end_pending",
            ticket_id,
        )

    def complete_safe_close(self, ticket_id: str, proof: Mapping[str, Any]):
        return self.complete_end(ticket_id, proof)
