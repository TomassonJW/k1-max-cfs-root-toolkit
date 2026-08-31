#!/usr/bin/env python3
"""Parse hors installation le composant candidat avec le Python de la K1."""

import ast
import base64


SOURCE_B64 = "__SOURCE_B64__"
source = base64.b64decode(SOURCE_B64.encode("ascii"))
text = source.decode("utf-8")
tree = ast.parse(text, filename="k1_control_stock_cycle_owner.py")
classes = [node.name for node in tree.body if isinstance(node, ast.ClassDef)]
functions = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]
if "K1ControlStockCycleOwner" not in classes or "load_config" not in functions:
    raise RuntimeError("candidate_shape_invalid")
for forbidden in ("import requests", "import subprocess", "import serial"):
    if forbidden in text:
        raise RuntimeError("candidate_transport_import:%s" % forbidden)
print("REMOTE_STOCK_DERIVED_CYCLE_SOURCE_VALIDATE_OK")
