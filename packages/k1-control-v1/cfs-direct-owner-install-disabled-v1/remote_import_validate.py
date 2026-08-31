#!/usr/bin/env python3
"""Compile et importe le payload exact dans le Python Klipper distant."""

import base64
import json
import sys
import types


payloads = json.loads(base64.b64decode("__PAYLOAD_JSON_B64__").decode("ascii"))
required = {"init", "protocol", "owner", "runtime_adapter", "component"}
if set(payloads) != required:
    raise RuntimeError("payload_keys_invalid")

for name, encoded in payloads.items():
    source = base64.b64decode(encoded).decode("utf-8")
    compile(source, name + ".py", "exec")

klippy = types.ModuleType("klippy")
klippy.__path__ = []
extras = types.ModuleType("klippy.extras")
extras.__path__ = []
package_name = "klippy.extras.k1_control_cfs_direct"
package = types.ModuleType(package_name)
package.__path__ = []
sys.modules["klippy"] = klippy
sys.modules["klippy.extras"] = extras
sys.modules[package_name] = package


def execute(name, key, package_value):
    module = types.ModuleType(name)
    module.__file__ = key + ".py"
    module.__package__ = package_value
    sys.modules[name] = module
    source = base64.b64decode(payloads[key]).decode("utf-8")
    exec(compile(source, module.__file__, "exec"), module.__dict__)
    return module


init_source = base64.b64decode(payloads["init"]).decode("utf-8")
exec(compile(init_source, "__init__.py", "exec"), package.__dict__)
protocol = execute(package_name + ".protocol", "protocol", package_name)
package.protocol = protocol
owner = execute(package_name + ".owner", "owner", package_name)
package.owner = owner
adapter = execute(
    package_name + ".runtime_adapter", "runtime_adapter", package_name
)
package.runtime_adapter = adapter
component = execute(
    "klippy.extras.k1_control_cfs_direct_owner",
    "component",
    "klippy.extras",
)

if component.OWNER_NAME != "k1_control_direct":
    raise RuntimeError("owner_name_invalid")
if len(component.STOCK_EFFECT_COMMANDS) != 19:
    raise RuntimeError("stock_effect_surface_count_invalid")
print("REMOTE_CFS_DIRECT_OWNER_IMPORT_OK files=5 stock_entries=19")
