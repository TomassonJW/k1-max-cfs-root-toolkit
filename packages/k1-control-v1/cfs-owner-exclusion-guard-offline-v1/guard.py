#!/usr/bin/env python3
"""Pure one-shot stock-owner exclusion guard; it cannot dispatch commands."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from adapter import AdapterError, adapt_stable_pair, owner_identity_drift, transition_drift


class Guard:
    def __init__(self, contract: Mapping[str, Any]):
        self.contract = contract
        self._validate_contract()
        self.phase = "idle"
        self.reason_code: Optional[str] = None
        self.saved_value: Optional[int] = None
        self.owner_granted = False
        self.release_required = False
        self.replay_allowed = False
        self.effect_baseline: Optional[Dict[str, Any]] = None
        self.attempts = {"disable": 0, "restore": 0}
        self.pending_intent: Optional[Dict[str, Any]] = None
        self.journal = []

    def _validate_contract(self) -> None:
        if not isinstance(self.contract, Mapping) or self.contract.get("contract_id") != "cfs-owner-exclusion-guard-offline-v1":
            raise ValueError("contract_invalid")
        if self.contract.get("schema") != 1 or self.contract.get("authority") != "offline_only":
            raise ValueError("contract_authority_invalid")
        boundaries = self.contract.get("boundaries")
        if not isinstance(boundaries, Mapping) or not boundaries or not all(
            value is False for value in boundaries.values()
        ):
            raise ValueError("contract_boundary_invalid")
        snapshot = self.contract.get("snapshot")
        if not isinstance(snapshot, Mapping) or snapshot.get("stable_reads") != 2:
            raise ValueError("contract_snapshot_invalid")
        intents = self.contract.get("reviewed_intents")
        if not isinstance(intents, Mapping):
            raise ValueError("contract_intents_invalid")
        disable = intents.get("disable_stock_auto_refill")
        restore = intents.get("restore_stock_auto_refill")
        if not isinstance(disable, Mapping) or disable != {
            "command": "BOX_ENABLE_AUTO_REFILL ENABLE=0",
            "dispatchable": False,
            "maximum_attempts": 1,
        }:
            raise ValueError("contract_disable_intent_invalid")
        if not isinstance(restore, Mapping) or restore != {
            "command_template": "BOX_ENABLE_AUTO_REFILL ENABLE={saved_value}",
            "allowed_saved_values": [0, 1],
            "dispatchable": False,
            "maximum_attempts": 1,
        }:
            raise ValueError("contract_restore_intent_invalid")

    def _intent(self, operation: str, command: str) -> Dict[str, Any]:
        return {"operation": operation, "command": command, "dispatchable": False, "maximum_attempts": 1}

    def _pair(self, reads: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
        return adapt_stable_pair(self.contract, reads)

    def _block(self, code: str, unknown: bool = False) -> Dict[str, Any]:
        self.phase = "blocked_unknown" if unknown else "blocked_safe"
        self.reason_code = code
        self.owner_granted = False
        self.pending_intent = None
        self.replay_allowed = False
        self.journal.append({"event": "blocked", "reason_code": code})
        return self.result()

    def _post(self, reads: Sequence[Mapping[str, Any]]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        try:
            snapshot = self._pair(reads)
        except (AdapterError, TypeError, KeyError) as exc:
            return None, self._block(getattr(exc, "code", "post_snapshot_invalid"), unknown=True)
        if self.effect_baseline is None:
            return None, self._block("effect_baseline_missing", unknown=True)
        drift = transition_drift(self.effect_baseline, snapshot)
        identity = owner_identity_drift(self.effect_baseline, snapshot)
        if identity:
            return None, self._block("owner_identity_changed", unknown=True)
        if drift:
            return None, self._block("non_target_state_changed", unknown=True)
        return snapshot, None

    def prepare_acquire(self, reads: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
        if self.phase != "idle":
            return self._block("acquire_replay_forbidden")
        try:
            snapshot = self._pair(reads)
        except (AdapterError, TypeError, KeyError) as exc:
            return self._block(getattr(exc, "code", "pre_snapshot_invalid"))
        self.saved_value = snapshot["stock_auto_refill"]
        self.effect_baseline = deepcopy(snapshot)
        if self.saved_value == 0:
            self.phase = "owner_granted"
            self.owner_granted = True
            self.release_required = False
            self.journal.append({"event": "already_excluded"})
            return self.result()
        self.attempts["disable"] = 1
        self.phase = "disable_pending"
        self.release_required = True
        self.pending_intent = self._intent("disable_stock_auto_refill", "BOX_ENABLE_AUTO_REFILL ENABLE=0")
        return self.result()

    def observe_disable(self, outcome: str, reads: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
        if self.phase != "disable_pending":
            return self._block("disable_retry_forbidden", unknown=self.release_required)
        self.pending_intent = None
        snapshot, blocked = self._post(reads)
        if blocked is not None:
            return blocked
        assert snapshot is not None and self.saved_value is not None
        observed = snapshot["stock_auto_refill"]
        if outcome == "accepted" and observed == 0:
            self.phase = "owner_granted"
            self.owner_granted = True
            self.reason_code = None
            return self.result()
        if outcome == "rejected" and observed == self.saved_value:
            self.phase = "closed_safe_ko"
            self.reason_code = "disable_rejected"
            self.release_required = False
            return self.result()
        if outcome == "unknown" and observed == 0 and self.saved_value == 1:
            self.phase = "rollback_pending"
            self.reason_code = "disable_outcome_unknown_effect_observed"
            self.attempts["restore"] = 1
            self.pending_intent = self._intent("restore_stock_auto_refill", "BOX_ENABLE_AUTO_REFILL ENABLE=1")
            return self.result()
        if outcome == "unknown" and observed == self.saved_value:
            self.phase = "closed_safe_ko"
            self.reason_code = "disable_outcome_unknown_no_effect_observed"
            self.release_required = False
            return self.result()
        return self._block("disable_result_not_proven", unknown=True)

    def recover_disable(self, reads: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
        if self.phase != "blocked_unknown" or self.attempts["disable"] != 1 or self.saved_value is None:
            return self._block("disable_recovery_not_available", unknown=True)
        snapshot, blocked = self._post(reads)
        if blocked is not None:
            return blocked
        assert snapshot is not None
        if snapshot["stock_auto_refill"] == self.saved_value:
            self.phase = "closed_safe_ko"
            self.reason_code = "disable_recovered_at_saved_value"
            self.release_required = False
        elif snapshot["stock_auto_refill"] == 0 and self.saved_value == 1:
            self.phase = "rollback_pending"
            self.reason_code = "disable_recovered_at_disabled_value"
            self.attempts["restore"] = 1
            self.pending_intent = self._intent("restore_stock_auto_refill", "BOX_ENABLE_AUTO_REFILL ENABLE=1")
        return self.result()

    def prepare_release(self, reads: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
        if self.phase != "owner_granted" or not self.owner_granted or self.saved_value is None:
            return self._block("release_not_available", unknown=self.release_required)
        snapshot, blocked = self._post(reads)
        if blocked is not None:
            return blocked
        assert snapshot is not None
        if snapshot["stock_auto_refill"] != 0:
            return self._block("owner_exclusion_lost", unknown=True)
        self.owner_granted = False
        if self.saved_value == 0:
            self.phase = "closed_safe"
            self.release_required = False
            return self.result()
        self.attempts["restore"] = 1
        self.phase = "restore_pending"
        self.pending_intent = self._intent("restore_stock_auto_refill", "BOX_ENABLE_AUTO_REFILL ENABLE=1")
        return self.result()

    def observe_restore(self, outcome: str, reads: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
        if self.phase not in {"restore_pending", "rollback_pending"}:
            return self._block("restore_retry_forbidden", unknown=True)
        self.pending_intent = None
        snapshot, blocked = self._post(reads)
        if blocked is not None:
            return blocked
        assert snapshot is not None and self.saved_value is not None
        if snapshot["stock_auto_refill"] == self.saved_value:
            self.phase = "closed_safe" if outcome == "accepted" else "closed_safe_ko"
            self.reason_code = None if outcome == "accepted" else "restore_outcome_unqualified_saved_value_observed"
            self.release_required = False
            return self.result()
        return self._block("restore_result_not_proven", unknown=True)

    def recover_restore(self, reads: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
        if self.phase != "blocked_unknown" or self.attempts["restore"] != 1 or self.saved_value is None:
            return self._block("restore_recovery_not_available", unknown=True)
        snapshot, blocked = self._post(reads)
        if blocked is not None:
            return blocked
        assert snapshot is not None
        if snapshot["stock_auto_refill"] == self.saved_value:
            self.phase = "closed_safe_ko"
            self.reason_code = "restore_recovered_at_saved_value"
            self.release_required = False
        return self.result()

    def result(self) -> Dict[str, Any]:
        return {
            "phase": self.phase,
            "reason_code": self.reason_code,
            "saved_stock_auto_refill": self.saved_value,
            "owner_granted": self.owner_granted,
            "release_required": self.release_required,
            "replay_allowed": self.replay_allowed,
            "attempts": deepcopy(self.attempts),
            "pending_intent": deepcopy(self.pending_intent),
            "journal": deepcopy(self.journal),
            "printer_connection": False,
            "gcode_sent": False,
            "physical_action": False,
            "deployment_candidate": False
        }
