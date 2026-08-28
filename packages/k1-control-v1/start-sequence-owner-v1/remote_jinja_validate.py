from __future__ import print_function

import base64
import re

from jinja2 import Environment


CONFIG_BASE64 = "__CONFIG_BASE64__"
text = base64.b64decode(CONFIG_BASE64.encode("ascii")).decode("utf-8")
environment = Environment(
    block_start_string="{%",
    block_end_string="%}",
    variable_start_string="{",
    variable_end_string="}",
)
bodies = re.findall(r"^gcode:\n((?:^  .*\n?)*)", text, flags=re.MULTILINE)
if len(bodies) != 13:
    raise RuntimeError("start owner section count is incomplete: %d" % len(bodies))
for body in bodies:
    environment.parse(body)
print("REMOTE_START_OWNER_JINJA_PARSE_OK sections=%d" % len(bodies))
