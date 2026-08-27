#!/usr/bin/env python3
"""Run the deterministic offline transport matrix through the real guard."""

from __future__ import annotations

from copy import deepcopy
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys
from typing import Any, Dict, Mapping, Optional, Sequence


PACKAGE = Path(__file__).resolve().parent


def _load(name: str, path: Path):
    spec = spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("module_load_failed:%s" % path)
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


transport = _load("cfs_guard_offline_transport", PACKAGE / "transport.py")
fake_endpoint = _load("cfs_guard_offline_endpoint", PACKAGE / "fake_endpoint.py")
adapter = _load(
    "cfs_guard_offline_adapter",
    PACKAGE.parent / "cfs-stock-unload-guard-adapter-offline-v1" / "adapter.py",
)
guard = _load(
    "cfs_guard_offline_controller",
    PACKAGE.parent / "cfs-stock-unload-guard-v1" / "controller.py",
)


def raw_state(
    *,
    route: Optional[str] = "T1A",
    active_command: str = "",
    extruder_target_c: float = 0.0,
    bed_target_c: float = 0.0,
    print_state: str = "standby",
    connected_units: Sequence[str] = ("T1", "T2"),
    toolhead_present: bool = True,
) -> Dict[str, Any]:
    units: Dict[str, Dict[str, str]] = {}
    for unit_name in ("T1", "T2", "T3", "T4"):
        connected = unit_name in connected_units
        filament = "None"
        if route and route.startswith(unit_name):
            filament = route[-1]
        units[unit_name] = {
            "state": "connect"
            if connected
            else ("None" if unit_name in {"T3", "T4"} else "disconnect"),
            "filament": filament,
        }
    box: Dict[str, Any] = {
        "state": "connect" if connected_units else "disconnect",
        "t_command": active_command,
    }
    box.update(units)
    return {
        "result": {
            "status": {
                "print_stats": {"state": print_state},
                "extruder": {"target": extruder_target_c},
                "heater_bed": {"target": bed_target_c},
                "box": box,
                "filament_switch_sensor filament_sensor": {
                    "enabled": True,
                    "filament_detected": toolhead_present,
                },
            }
        }
    }


def query(payload: Mapping[str, Any], elapsed_s: float = 0.05) -> Dict[str, Any]:
    return {
        "operation": "query",
        "command": None,
        "elapsed_s": elapsed_s,
        "payload": deepcopy(dict(payload)),
    }


def command(
    name: str,
    *,
    elapsed_s: float = 0.1,
    payload: Optional[Mapping[str, Any]] = None,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    event: Dict[str, Any] = {
        "operation": "command",
        "command": name,
        "elapsed_s": elapsed_s,
    }
    if error is None:
        event["payload"] = dict(payload or {"result": "ok"})
    else:
        event["error"] = error
    return event


def success_events(*, exact_deadlines: bool = False) -> list[Dict[str, Any]]:
    query_time = 2.0 if exact_deadlines else 0.05
    stock_time = 150.0 if exact_deadlines else 0.1
    cleanup_time = 15.0 if exact_deadlines else 0.1
    return [
        query(raw_state(), query_time),
        command(transport.STOCK_UNLOAD_COMMAND, elapsed_s=stock_time),
        query(raw_state(active_command="RETRUDE_PROCESS", extruder_target_c=220)),
        query(raw_state(route=None, extruder_target_c=220)),
        command(transport.HEATER_SHUTDOWN_COMMAND, elapsed_s=cleanup_time),
        query(raw_state(route=None)),
    ]


def _guard_result(events: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    endpoint = fake_endpoint.ScriptedEndpoint(events)
    api = transport.OfflineGuardTransport(endpoint, adapter.adapt_query_response)
    result = guard.StockUnloadGuard(api, max_polls=2, cleanup_polls=2).run("T1A")
    return {
        "verdict": result.verdict,
        "code": result.code,
        "primary_error": result.primary_error,
        "cleanup_error": result.cleanup_error,
        "stock_count": result.stock_command_count,
        "cleanup_count": result.heater_shutdown_count,
        "route_clear_observed": result.route_clear_observed,
        "heater_shutdown_verified": result.heater_shutdown_verified,
        "toolhead_filament_present_after": result.toolhead_filament_present_after,
        "attempted_commands": list(api.attempted_commands),
        "endpoint_commands": sum(
            1 for call in endpoint.calls if call["operation"] == "command"
        ),
        "journal": api.journal_dicts(),
        "remaining_events": endpoint.remaining,
    }


def _direct_result(
    events: Sequence[Mapping[str, Any]], actions: Sequence[str]
) -> Dict[str, Any]:
    endpoint = fake_endpoint.ScriptedEndpoint(events)
    api = transport.OfflineGuardTransport(endpoint, adapter.adapt_query_response)
    code = None
    try:
        for action in actions:
            api.run_gcode(action)
    except transport.TransportFailure as exc:
        code = exc.code
    return {
        "transport_code": code,
        "endpoint_commands": sum(
            1 for call in endpoint.calls if call["operation"] == "command"
        ),
        "attempted_commands": list(api.attempted_commands),
        "journal": api.journal_dicts(),
        "remaining_events": endpoint.remaining,
    }


def run_one(scenario_id: str) -> Dict[str, Any]:
    if scenario_id == "success_route_clear_and_targets_zero":
        return _guard_result(success_events())
    if scenario_id == "exact_deadlines_are_accepted":
        return _guard_result(success_events(exact_deadlines=True))
    if scenario_id == "http_ok_without_unload_effect":
        return _guard_result(
            [
                query(raw_state()),
                command(transport.STOCK_UNLOAD_COMMAND),
                query(raw_state(extruder_target_c=220)),
                query(raw_state(extruder_target_c=220)),
                command(transport.HEATER_SHUTDOWN_COMMAND),
                query(raw_state()),
            ]
        )
    if scenario_id == "http_ok_without_cleanup_effect":
        return _guard_result(
            [
                query(raw_state()),
                command(transport.STOCK_UNLOAD_COMMAND),
                query(raw_state(route=None, extruder_target_c=220)),
                command(transport.HEATER_SHUTDOWN_COMMAND),
                query(raw_state(route=None, extruder_target_c=220)),
                query(raw_state(route=None, extruder_target_c=220)),
            ]
        )
    if scenario_id == "stock_timeout_no_retry_cleanup_once":
        return _guard_result(
            [
                query(raw_state()),
                command(transport.STOCK_UNLOAD_COMMAND, elapsed_s=150.001),
                command(transport.HEATER_SHUTDOWN_COMMAND),
                query(raw_state()),
            ]
        )
    if scenario_id == "stock_connection_loss_no_retry_cleanup_once":
        return _guard_result(
            [
                query(raw_state()),
                command(transport.STOCK_UNLOAD_COMMAND, error="connection_lost"),
                command(transport.HEATER_SHUTDOWN_COMMAND),
                query(raw_state()),
            ]
        )
    if scenario_id == "poll_timeout_cleanup_once":
        return _guard_result(
            [
                query(raw_state()),
                command(transport.STOCK_UNLOAD_COMMAND),
                query(raw_state(extruder_target_c=220), elapsed_s=2.001),
                command(transport.HEATER_SHUTDOWN_COMMAND),
                query(raw_state()),
            ]
        )
    if scenario_id == "cleanup_timeout_no_retry":
        return _guard_result(
            [
                query(raw_state()),
                command(transport.STOCK_UNLOAD_COMMAND),
                query(raw_state(route=None, extruder_target_c=220)),
                command(transport.HEATER_SHUTDOWN_COMMAND, elapsed_s=15.001),
            ]
        )
    if scenario_id == "schema_drift_refused_before_command":
        return _guard_result([query({"result": {"status": {}}})])
    if scenario_id == "duplicate_stock_rejected":
        return _direct_result(
            [command(transport.STOCK_UNLOAD_COMMAND)],
            [transport.STOCK_UNLOAD_COMMAND, transport.STOCK_UNLOAD_COMMAND],
        )
    if scenario_id == "duplicate_cleanup_rejected":
        return _direct_result(
            [
                command(transport.STOCK_UNLOAD_COMMAND),
                command(transport.HEATER_SHUTDOWN_COMMAND),
            ],
            [
                transport.STOCK_UNLOAD_COMMAND,
                transport.HEATER_SHUTDOWN_COMMAND,
                transport.HEATER_SHUTDOWN_COMMAND,
            ],
        )
    if scenario_id == "unsupported_command_rejected":
        return _direct_result([], ["M104 S0"])
    if scenario_id == "cleanup_before_stock_rejected":
        return _direct_result([], [transport.HEATER_SHUTDOWN_COMMAND])
    raise KeyError("scenario_unknown:%s" % scenario_id)


def _matches(
    result: Mapping[str, Any], expected: Mapping[str, Any]
) -> tuple[bool, str]:
    for key, wanted in expected.items():
        if key == "primary_prefix":
            actual = result.get("primary_error")
            if not isinstance(actual, str) or not actual.startswith(str(wanted)):
                return False, "primary_error expected prefix %r got %r" % (
                    wanted,
                    actual,
                )
        elif key == "cleanup_prefix":
            actual = result.get("cleanup_error")
            if not isinstance(actual, str) or not actual.startswith(str(wanted)):
                return False, "cleanup_error expected prefix %r got %r" % (
                    wanted,
                    actual,
                )
        elif result.get(key) != wanted:
            return False, "%s expected %r got %r" % (
                key,
                wanted,
                result.get(key),
            )
    return True, "expected bounded outcome observed"


def run(path: Path = PACKAGE / "scenarios.json") -> Dict[str, Any]:
    matrix = json.loads(path.read_text(encoding="utf-8"))
    contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
    declared = [item["id"] for item in matrix["scenarios"]]
    if declared != contract["required_scenarios"]:
        raise RuntimeError("scenario_contract_mismatch")
    results = []
    for scenario in matrix["scenarios"]:
        actual = run_one(scenario["id"])
        passed, detail = _matches(actual, scenario["expected"])
        results.append(
            {
                "id": scenario["id"],
                "passed": passed,
                "detail": detail,
                "result": actual,
            }
        )
    passed = sum(item["passed"] for item in results)
    return {
        "verdict": "OK" if passed == len(results) else "KO",
        "passed": passed,
        "total": len(results),
        "results": results,
        "printer_connection": False,
        "gcode_sent": False,
        "deployment_candidate": False,
    }


def main() -> int:
    summary = run()
    for item in summary["results"]:
        print(
            "%s %s: %s"
            % ("OK" if item["passed"] else "KO", item["id"], item["detail"])
        )
    print("TOTAL %d/%d" % (summary["passed"], summary["total"]))
    return 0 if summary["verdict"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
