#!/usr/bin/env python3
"""Create the integrated two-layer gate from the already qualified Orca body."""

from __future__ import annotations

import argparse
from pathlib import Path


OLD_START = (
    "KCTRL_JOB_BEGIN_KEEP_CORRECT_V1 BED=55 PROBE_NOZZLE=140 FIRST_NOZZLE=190 "
    "PLATE=1 PROBE_REV=1 NOZZLE_ID=1 CONFIG_ID=1 X_COUNT=11 Y_COUNT=11"
)
OLD_END = "\n".join((
    "KCTRL_START_ABORT_V1",
    "KCTRL_CLEAR_MANUAL_NOZZLE_CLEAN_V1",
    "M107 P1",
    "M107 P2",
    "M84",
))


def build(source: Path, destination: Path) -> None:
    text = source.read_text(encoding="utf-8")
    executable_start = "\n%s\n" % OLD_START
    executable_end = "\n%s\n" % OLD_END
    if text.count(executable_start) != 1:
        raise RuntimeError("old_start_not_unique")
    if text.count(executable_end) != 1:
        raise RuntimeError("old_end_not_unique")
    result = text.replace(executable_start, "\nKCTRL_CYCLE_JOB_ASSERT_V1\n", 1)
    result = result.replace(executable_end, "\nKCTRL_CYCLE_END_V1\n", 1)
    had_final_newline = result.endswith("\n")
    result = "\n".join(line.rstrip() for line in result.splitlines())
    if had_final_newline:
        result += "\n"
    destination.write_text(result, encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    build(args.source, args.destination)


if __name__ == "__main__":
    main()
