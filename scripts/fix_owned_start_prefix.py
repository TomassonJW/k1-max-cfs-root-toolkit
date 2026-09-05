"""Repair the observed G28/T0 prefix without changing printer commands.

This only removes the two commands immediately before the first START_PRINT.
All bytes from START_PRINT onward remain identical, including later tool
changes, purge volumes, the part, and END_PRINT. A nonzero initial tool is
refused: the installed START_PRINT resolves the first logical filament only.
No network access, printer control, or in-place G-code rewrite lives here.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path


def repair_prefix(data):
    """Return (prefix, removed line numbers); accept only the observed T0 case."""
    lines = data.splitlines(keepends=True)
    commands = []
    for index, line in enumerate(lines):
        command = line.split(b";", 1)[0].strip()
        if not command:
            continue
        if command.split()[0] == b"START_PRINT":
            if b"EXTRUDER_TEMP=" not in command or b"BED_TEMP=" not in command:
                raise ValueError("START_PRINT temperatures are missing")
            break
        commands.append((index, command))
    else:
        raise ValueError("No START_PRINT in the bounded prefix")
    # Reject another startup path, rather than quietly removing its geometry.
    harmless = (b"M73", b"M106", b"M107", b"EXCLUDE_OBJECT_DEFINE")
    if len(commands) >= 2 and [x[1] for x in commands[-2:]] == [b"G28", b"T0"]:
        earlier, removed = commands[:-2], commands[-2:]
    else:
        earlier, removed = commands, []
    if any(command.split()[0] not in harmless for _, command in earlier):
        raise ValueError("Unrecognised commands before START_PRINT; manual review required")
    indices = {i for i, _ in removed}
    result = b"".join(line for i, line in enumerate(lines) if i not in indices)
    return result, [i + 1 for i, _ in removed]


def write_gcode_copy(source, output, before_publish=None):
    """Stream a separate copy; hashes prove the complete remainder is unchanged.

    before_publish is an optional final idle-state check supplied by the
    deployment caller. It runs after copying, before the new file is published.
    The original is never written. An interrupted .partial is kept for review.
    """
    source, output = Path(source), Path(output)
    partial = output.with_name(output.name + ".partial")
    if source.resolve() == output.resolve() or output.exists() or partial.exists():
        raise ValueError("Source, destination or partial already exists; no overwrite")
    source_hash, output_hash = hashlib.sha256(), hashlib.sha256()
    remainder_hash = hashlib.sha256()
    with source.open("rb") as reader:
        before = os.fstat(reader.fileno())
        prefix = reader.read(256 * 1024)
        repaired, removed = repair_prefix(prefix)
        if not removed:
            raise ValueError("The file already has the owned start; no copy needed")
        marker = next(line for line in prefix.splitlines(keepends=True)
                      if line.split(b";", 1)[0].strip().startswith(b"START_PRINT "))
        old_tail = prefix[prefix.index(marker):]
        new_tail = repaired[repaired.index(marker):]
        if old_tail != new_tail:
            raise ValueError("The payload after START_PRINT changed")
        remainder_hash.update(old_tail)
        source_hash.update(prefix)
        output_hash.update(repaired)
        with partial.open("xb") as writer:
            writer.write(repaired)
            while True:
                chunk = reader.read(1024 * 1024)
                if not chunk:
                    break
                source_hash.update(chunk)
                output_hash.update(chunk)
                remainder_hash.update(chunk)
                writer.write(chunk)
            writer.flush()
            os.fsync(writer.fileno())
        after = os.fstat(reader.fileno())
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError("Source changed during copying; partial retained")
    with partial.open("rb") as reader:
        verified_hash = hashlib.sha256()
        for chunk in iter(lambda: reader.read(1024 * 1024), b""):
            verified_hash.update(chunk)
    if verified_hash.digest() != output_hash.digest():
        raise ValueError("Written copy hash mismatch; partial retained")
    if before_publish is not None:
        before_publish()
    # link() fails if a destination appeared concurrently; it never overwrites.
    os.link(str(partial), str(output))
    partial.unlink()
    return {"source": str(source), "output": str(output),
            "removed_lines": removed, "removed_bytes": len(prefix) - len(repaired),
            "source_sha256": source_hash.hexdigest(),
            "output_sha256": output_hash.hexdigest(),
            "unchanged_from_start_print_sha256": remainder_hash.hexdigest()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--apply", action="store_true", help="Create a separate copy")
    args = parser.parse_args()
    if args.apply:
        result = write_gcode_copy(args.source, args.output)
    else:
        with args.source.open("rb") as source:
            _, removed = repair_prefix(source.read(256 * 1024))
        result = {"mode": "plan", "removed_lines": removed, "output": str(args.output)}
    print(json.dumps(result, indent=2))
