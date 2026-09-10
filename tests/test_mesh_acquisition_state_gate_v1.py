"""The measuring macros refuse a print in progress, not a print that is over.

After a print finishes, print_stats.state reads "complete" until the next file
is loaded, and after an abort it reads "cancelled". On 2026-09-10 at 11:43 the
operator ran KCTRL_BED_SCREWS six times right after the calibration square and
was refused six times with "requires standby": the gate was written as an
equality on "standby", so the one moment the measurement is wanted - straight
after a bad first layer - was the moment it was refused. What the gate protects
against is probing during a print or under a pause; those two states are named,
and every other state is allowed.
"""

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE = os.path.join(ROOT, "packages", "k1-control-v1", "mesh-acquisition-v2")
FILES = {
    "k1-control-mesh-acquisition-v2.cfg": ["KCTRL_MESH_ACQUIRE"],
    "k1-control-mesh-reference-v2.cfg": ["KCTRL_BED_SCREWS", "KCTRL_MESH_SAVE_AS_REF", "KCTRL_Z_REPEAT"],
}
REFUSED = '{% if printer.print_stats.state|string in ["printing", "paused"] %}'


def section(text, name):
    start = text.index("[gcode_macro %s]" % name)
    end = text.find("\n[", start + 1)
    return text[start:end if end != -1 else len(text)]


def test_each_measuring_macro_names_the_two_states_it_refuses():
    for filename, macros in FILES.items():
        text = open(os.path.join(PACKAGE, filename), encoding="utf-8").read()
        for macro in macros:
            body = section(text, macro)
            assert REFUSED in body, (filename, macro)


def test_no_measuring_macro_demands_standby_any_more():
    for filename in FILES:
        text = open(os.path.join(PACKAGE, filename), encoding="utf-8").read()
        assert not re.search(r'print_stats\.state\|string\s*!=\s*"standby"', text), filename
        assert "requires standby" not in text, filename


def test_the_refusal_says_what_it_refuses():
    for filename, macros in FILES.items():
        text = open(os.path.join(PACKAGE, filename), encoding="utf-8").read()
        for macro in macros:
            body = section(text, macro)
            gate = body.index(REFUSED)
            message = body[gate:gate + 300]
            assert "print is in progress or paused" in message, (filename, macro)
