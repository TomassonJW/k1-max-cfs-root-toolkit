#!/usr/bin/env python3
"""Run every offline stock-unload scenario without printer access."""

from __future__ import annotations

import argparse
from copy import deepcopy
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys
from typing import Any, Dict, List

HERE = Path(__file__).resolve().parent


def _load(name: str, filename: str) -> Any:
    spec = spec_from_file_location(name, HERE / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load %s" % filename)
    module = module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_controller = _load("cfs_stock_unload_guard_controller_runtime", "controller.py")
_fake_api = _load("cfs_stock_unload_guard_fake_api_runtime", "fake_api.py")
StockUnloadGuard = _controller.StockUnloadGuard
FakePrinterApi = _fake_api.FakePrinterApi


def _expand(sequence: List[Dict[str, Any]], starting: Dict[str, Any]) -> List[Dict[str, Any]]:
    state = deepcopy(starting)
    expanded = []
    for patch in sequence:
        state.update(deepcopy(patch))
        expanded.append(deepcopy(state))
    return expanded


def _scenario(defaults: Dict[str, Any], raw: Dict[str, Any]) -> Dict[str, Any]:
    result = deepcopy(defaults)
    result.update({key: deepcopy(value) for key, value in raw.items() if key not in {"initial", "after_stock", "after_cleanup"}})
    initial = deepcopy(defaults["initial"])
    initial.update(deepcopy(raw.get("initial", {})))
    result["initial"] = initial
    result["after_stock"] = _expand(raw.get("after_stock", []), initial)
    cleanup_start = result["after_stock"][-1] if result["after_stock"] else initial
    result["after_cleanup"] = _expand(raw.get("after_cleanup", []), cleanup_start)
    return result


def run(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    results = []
    for raw in payload["scenarios"]:
        scenario = _scenario(payload["defaults"], raw)
        api = FakePrinterApi(scenario)
        result = StockUnloadGuard(api, max_polls=3, cleanup_polls=3).run(scenario["expected_route"])
        passed = [result.verdict, result.code] == scenario["expected"] and result.stock_command_count <= 1 and result.heater_shutdown_count <= 1
        results.append({"id": scenario["id"], "passed": passed, "expected": scenario["expected"], "actual": [result.verdict, result.code], "commands": list(api.commands)})
    return {"verdict": "OK" if all(item["passed"] for item in results) else "KO", "passed": sum(1 for item in results if item["passed"]), "total": len(results), "results": results}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", type=Path, default=HERE / "scenarios.json")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    summary = run(args.scenarios)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("CFS_STOCK_UNLOAD_GUARD_V1_%s %d/%d" % (summary["verdict"], summary["passed"], summary["total"]))
    return 0 if summary["verdict"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
