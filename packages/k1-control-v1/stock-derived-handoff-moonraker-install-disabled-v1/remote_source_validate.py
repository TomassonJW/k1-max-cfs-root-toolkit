#!/usr/bin/env python3
"""Parse les trois sources Python avec le Python cible avant installation."""

import ast
import base64


SOURCES = {
    "geometry": ("__GEOMETRY_B64__", "K1ControlStockGeometryHandoff", "load_config"),
    "core": ("__CORE_B64__", "StockDerivedOrchestrator", None),
    "moonraker": ("__MOONRAKER_B64__", "K1ControlStockCycle", "load_component"),
}

for name, (encoded, expected_class, expected_function) in SOURCES.items():
    text = base64.b64decode(encoded.encode("ascii")).decode("utf-8")
    tree = ast.parse(text, filename=name + ".py")
    classes = [node.name for node in tree.body if isinstance(node, ast.ClassDef)]
    functions = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]
    if expected_class not in classes:
        raise RuntimeError("candidate_class_missing:%s" % name)
    if expected_function is not None and expected_function not in functions:
        raise RuntimeError("candidate_loader_missing:%s" % name)
    for forbidden in (
        "import requests",
        "import subprocess",
        "import serial",
        "from requests",
        "from subprocess",
        "from serial",
    ):
        if forbidden in text:
            raise RuntimeError("candidate_transport_import:%s:%s" % (name, forbidden))

print("REMOTE_STOCK_DERIVED_HANDOFF_MOONRAKER_SOURCE_VALIDATE_OK")
