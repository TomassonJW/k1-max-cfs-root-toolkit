#!/usr/bin/env python3
"""Matrice pure de la gate physique directe T1A, sans connexion K1."""


def prepare_clear(head, after_cutter, owner_phase):
    if head != after_cutter:
        return "blocked_sensor_mismatch"
    if owner_phase != "idle":
        return "blocked_owner_not_idle"
    if not head:
        return "already_clear"
    return "reconcile_then_unload_once"


def transition(action, phase, head, after_cutter):
    if action == "load":
        if phase != "idle" or head or after_cutter:
            return "blocked"
        return "loaded"
    if action == "unload":
        if phase != "loaded" or not head or not after_cutter:
            return "blocked"
        return "idle"
    return "blocked"


def run():
    checks = [
        ("prepare_clear_empty", prepare_clear(False, False, "idle") == "already_clear"),
        ("prepare_clear_loaded", prepare_clear(True, True, "idle") == "reconcile_then_unload_once"),
        ("prepare_clear_head_only", prepare_clear(True, False, "idle") == "blocked_sensor_mismatch"),
        ("prepare_clear_after_only", prepare_clear(False, True, "idle") == "blocked_sensor_mismatch"),
        ("prepare_clear_busy", prepare_clear(False, False, "loading") == "blocked_owner_not_idle"),
        ("load_clear", transition("load", "idle", False, False) == "loaded"),
        ("load_head_present", transition("load", "idle", True, False) == "blocked"),
        ("load_after_present", transition("load", "idle", False, True) == "blocked"),
        ("load_wrong_phase", transition("load", "loaded", False, False) == "blocked"),
        ("unload_loaded", transition("unload", "loaded", True, True) == "idle"),
        ("unload_missing_head", transition("unload", "loaded", False, True) == "blocked"),
        ("unload_missing_after", transition("unload", "loaded", True, False) == "blocked"),
        ("unload_wrong_phase", transition("unload", "idle", True, True) == "blocked"),
        ("unknown_action", transition("retry", "idle", False, False) == "blocked"),
        ("normal_cycle", transition("unload", transition("load", "idle", False, False), True, True) == "idle"),
    ]
    return [
        {"id": name, "status": "OK" if passed else "KO"}
        for name, passed in checks
    ]


if __name__ == "__main__":
    results = run()
    for item in results:
        print("%s %s" % (item["status"], item["id"]))
    ok_count = sum(1 for item in results if item["status"] == "OK")
    print("CFS_DIRECT_OWNER_PHYSICAL_LOAD_UNLOAD_V1 %d/%d" % (ok_count, len(results)))
    raise SystemExit(0 if ok_count == len(results) else 1)
