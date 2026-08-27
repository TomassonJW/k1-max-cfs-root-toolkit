#!/usr/bin/env python3
"""Run the redacted K1 query adapter scenarios without printer access."""

from __future__ import annotations

import argparse
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys
from typing import Any, Dict


HERE = Path(__file__).resolve().parent


def _load_adapter() -> Any:
    spec = spec_from_file_location(
        "cfs_stock_unload_guard_adapter_runtime", HERE / "adapter.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load adapter.py")
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_adapter = _load_adapter()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def run(manifest_path: Path) -> Dict[str, Any]:
    manifest = _load_json(manifest_path)
    results = []
    for scenario in manifest["scenarios"]:
        fixture = manifest_path.parent / scenario["fixture"]
        payload = _load_json(fixture)
        actual = None
        error = None
        try:
            actual = _adapter.adapt_query_response(payload)
        except _adapter.AdapterInputError as exc:
            error = exc.code
        passed = actual == scenario.get("expected_snapshot") and error == scenario.get(
            "expected_error"
        )
        results.append(
            {
                "id": scenario["id"],
                "passed": passed,
                "expected_error": scenario.get("expected_error"),
                "actual_error": error,
            }
        )
    return {
        "verdict": "OK" if all(item["passed"] for item in results) else "KO",
        "passed": sum(1 for item in results if item["passed"]),
        "total": len(results),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", type=Path, default=HERE / "scenarios.json")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    summary = run(args.scenarios)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            "CFS_STOCK_UNLOAD_GUARD_ADAPTER_OFFLINE_V1_%s %d/%d"
            % (summary["verdict"], summary["passed"], summary["total"])
        )
    return 0 if summary["verdict"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
