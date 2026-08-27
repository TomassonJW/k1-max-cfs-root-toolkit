"""Summarize only CFS effect markers and timestamps from a private capture."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Dict, Iterable, List


EVENTS = {
    "stock_unload": re.compile(r"BOX_QUIT_MATERIAL|RETRUDE_PROCESS", re.I),
    "stock_load": re.compile(r"BOX_EXTRUDE_MATERIAL|EXTRUDE_PROCESS", re.I),
    "tool_or_refill": re.compile(r"BOX_(START|CHANGE|REFILL)|material_auto_refill|cmd_T ", re.I),
    "mapping_change": re.compile(r"BOX_MODIFY_TN|tnn_map|last_tnn|last_cmd:", re.I),
}
SAFE_MARKERS = (
    "BOX_QUIT_MATERIAL",
    "BOX_EXTRUDE_MATERIAL",
    "RETRUDE_PROCESS",
    "EXTRUDE_PROCESS",
    "BOX_START",
    "BOX_CHANGE",
    "BOX_REFILL",
    "material_auto_refill",
    "cmd_T ",
    "BOX_MODIFY_TN",
    "tnn_map",
    "last_tnn",
    "last_cmd:",
)
CONTEXT_MARKERS = (
    "webhooks",
    "gcode/script",
    "timeout",
    "error",
    "finished",
    "request",
    "response",
    "stage",
)
TIMESTAMP = re.compile(r"(?P<stamp>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?)")
ROUTE = re.compile(r"\bT[1-4][A-D]\b")


class HistoryError(ValueError):
    pass


def _marked(lines: Iterable[str], name: str) -> List[str]:
    values = list(lines)
    begin = "=== %s_BEGIN ===" % name
    end = "=== %s_END ===" % name
    if values.count(begin) != 1 or values.count(end) != 1:
        raise HistoryError("capture_block_invalid:%s" % name)
    start = values.index(begin) + 1
    stop = values.index(end)
    return values[start:stop]


def _hashes(lines: Iterable[str]) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for line in lines:
        parts = line.split(None, 1)
        if len(parts) == 2 and len(parts[0]) == 64:
            result[parts[1].strip()] = parts[0].lower()
    return result


def analyze(path: Path, cutoff: str = "2026-08-27 00:16:16") -> Dict[str, object]:
    lines = path.read_text(encoding="utf-8-sig", errors="strict").splitlines()
    if "CFS_HISTORY_READ_ONLY_OK" not in lines:
        raise HistoryError("terminal_marker_missing")
    before = _hashes(_marked(lines, "HASHES_BEFORE"))
    after = _hashes(_marked(lines, "HASHES_AFTER"))
    if before != after or len(before) != 3:
        raise HistoryError("configuration_hashes_changed_or_incomplete")

    history = _marked(lines, "CFS_HISTORY")
    counts: Counter[str] = Counter()
    latest: Dict[str, str] = {}
    after_cutoff: Counter[str] = Counter()
    safe_records = []
    for line_index, line in enumerate(history):
        stamp_match = TIMESTAMP.search(line)
        stamp = stamp_match.group("stamp").replace(",", ".") if stamp_match else None
        for event, pattern in EVENTS.items():
            if pattern.search(line):
                counts[event] += 1
                if stamp:
                    latest[event] = max(latest.get(event, stamp), stamp)
                    if stamp >= cutoff:
                        after_cutoff[event] += 1
                safe_records.append(
                    {
                        "event": event,
                        "timestamp": stamp,
                        "markers": [marker.strip() for marker in SAFE_MARKERS if marker.lower() in line.lower()],
                        "context": [marker for marker in CONTEXT_MARKERS if marker.lower() in line.lower()],
                        "routes_on_line": sorted(set(ROUTE.findall(line))),
                        "routes_within_five_lines": sorted(
                            {
                                route
                                for nearby in history[max(0, line_index - 5) : line_index + 6]
                                for route in ROUTE.findall(nearby)
                            }
                        ),
                        "line_sha256": hashlib.sha256(line.encode("utf-8")).hexdigest(),
                    }
                )

    return {
        "schema": 1,
        "status": "CFS_HISTORY_READ_ONLY_OK",
        "cutoff": cutoff,
        "event_counts_all_retained_log": dict(sorted(counts.items())),
        "event_counts_at_or_after_cutoff": dict(sorted(after_cutoff.items())),
        "latest_event_timestamps": dict(sorted(latest.items())),
        "safe_event_records": safe_records,
        "history_sha256": hashlib.sha256("\n".join(history).encode("utf-8")).hexdigest(),
        "configuration_hashes_unchanged": True,
        "identity_fields_exported": False,
        "printer_effect": False,
    }


def main(argv=None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) not in (1, 2):
        print("usage: analyze_recent_cfs_history.py <capture> [cutoff]", file=sys.stderr)
        return 2
    try:
        result = analyze(Path(arguments[0]), arguments[1] if len(arguments) == 2 else "2026-08-27 00:16:16")
    except Exception as exc:
        print(json.dumps({"status": "CFS_HISTORY_KO", "error": "%s:%s" % (type(exc).__name__, exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    print(result["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
