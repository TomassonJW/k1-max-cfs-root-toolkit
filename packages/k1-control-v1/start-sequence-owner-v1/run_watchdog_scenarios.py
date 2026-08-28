from __future__ import annotations

import json
from pathlib import Path

from watchdog_model import WatchdogSnapshot, evaluate


PACKAGE = Path(__file__).resolve().parent


def run() -> dict[str, object]:
    scenarios = json.loads((PACKAGE / "watchdog-scenarios.json").read_text(encoding="utf-8"))
    results = []
    for scenario in scenarios:
        result = evaluate(WatchdogSnapshot(**scenario["snapshot"]))
        if result["action"] != scenario["action"]:
            raise ValueError("scenario_failed:%s" % scenario["id"])
        if result["action"] == "ABORT" and not result["turn_off_heaters"]:
            raise ValueError("abort_without_heater_shutdown:%s" % scenario["id"])
        results.append({"id": scenario["id"], "action": result["action"], "status": "OK"})
    return {"status": "START_OWNER_WATCHDOG_SCENARIOS_OK", "passed": len(results), "results": results}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
