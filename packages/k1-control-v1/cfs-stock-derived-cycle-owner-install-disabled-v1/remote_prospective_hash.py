#!/usr/bin/env python3
"""Calcule sans écriture le hash de printer.cfg après ajout de l'include."""

from hashlib import sha256
import json
from pathlib import Path


PATH = Path("/usr/data/printer_data/config/printer.cfg")
BASELINE = "55b73da92aee86e9645ec8f8ebf3726bffc261d4530b642af52b91cbb89b9479"
NEEDLE = b"[include k1-control-cfs-direct-owner-disabled-v1.cfg]\n"
LINE = b"[include k1-control-stock-derived-cycle-owner-disabled-v1.cfg]\n"

data = PATH.read_bytes()
actual = sha256(data).hexdigest()
if actual != BASELINE:
    raise RuntimeError("printer_cfg_baseline_drift:%s" % actual)
if data.count(NEEDLE) != 1 or LINE in data:
    raise RuntimeError("printer_cfg_include_boundary_invalid")
candidate = data.replace(NEEDLE, NEEDLE + LINE, 1)
print(json.dumps({
    "baseline_sha256": actual,
    "prospective_sha256": sha256(candidate).hexdigest(),
    "bytes_before": len(data),
    "bytes_after": len(candidate),
}, sort_keys=True, separators=(",", ":")))
print("REMOTE_STOCK_DERIVED_CYCLE_PROSPECTIVE_HASH_OK")
