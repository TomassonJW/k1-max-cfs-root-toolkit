"""Atomically migrate the legacy composite state marker without changing evidence."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict


def migrate(path: Path) -> Dict[str, Any]:
    target = Path(path)
    value = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("Composite state is not an object")
    if value.get("version") == 1 and "schema" not in value:
        return value
    if value.get("schema") != 1 or "version" in value:
        raise RuntimeError("Unsupported composite state marker")
    migrated = dict(value)
    migrated.pop("schema", None)
    migrated["version"] = 1
    temporary = target.with_suffix(target.suffix + ".migration-next")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(migrated, stream, sort_keys=True, separators=(",", ":"))
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(str(temporary), str(target))
    return migrated


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: migrate_composite_state.py STATE_PATH")
    value = migrate(Path(sys.argv[1]))
    print("MIGRATE_COMPOSITE_STATE_OK version=%s" % value["version"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
