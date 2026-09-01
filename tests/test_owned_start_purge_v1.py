"""What the purge over the bin must actually push, rendered not read.

The stock flush is sized by box.cfg and leaves a thin strand hanging from the
nozzle instead of a ball that drops into the bin; that strand is then dragged
into the first layer. The extra purge is owned here, so its length has to be
provably the length that is commanded - a Jinja slip in a print start macro
only ever surfaces at the moment a print starts, with the plate hot.

Klipper renders macros with single braces as its variable delimiters, so the
same environment is used here rather than an approximation of it.
"""

import os
import re

import jinja2
import pytest

CONFIG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "packages", "k1-control-v1", "owned-start-print-v2",
    "k1-control-owned-start-print-v2.cfg")

# Klipper: jinja2.Environment('{%', '%}', '{', '}')
ENV = jinja2.Environment("{%", "%}", "{", "}", extensions=["jinja2.ext.do"])


def config_text():
    with open(CONFIG, encoding="utf-8") as handle:
        return handle.read()


def section(name):
    """Return the gcode: body of one [gcode_macro NAME] section."""
    text = config_text()
    start = text.index("[gcode_macro %s]" % name)
    end = text.find("\n[", start + 1)
    block = text[start:end if end != -1 else len(text)]
    body = block.split("\ngcode:\n", 1)[1]
    return "\n".join(line[2:] if line.startswith("  ") else line
                     for line in body.splitlines())


def variables(name):
    text = config_text()
    start = text.index("[gcode_macro %s]" % name)
    end = text.find("\n[", start + 1)
    block = text[start:end if end != -1 else len(text)]
    found = {}
    for key, value in re.findall(r"^variable_(\w+):\s*(.+)$", block, re.M):
        found[key] = float(value) if re.match(r"^-?[\d.]+$", value.strip()) else value
    return found


def commands(name):
    """The section body with comments and blank lines dropped.

    A comment naming a macro is not a call to it, and an ordering assertion that
    cannot tell them apart proves nothing.
    """
    kept = [line.strip() for line in section(name).splitlines()]
    return chr(10).join(line for line in kept
                        if line and not line.startswith("#"))


def render(name, params, extra_status=None):
    conf = variables(name)
    status = {"gcode_macro %s" % name: type("V", (), conf)()}
    status.update(extra_status or {})
    responses = []
    return ENV.from_string(section(name)).render(
        params={k: str(v) for k, v in params.items()},
        printer=status,
        action_respond_info=lambda text: responses.append(text) or "",
    ), responses


def extruded(rendered):
    return sum(float(value)
               for value in re.findall(r"^\s*G1 E([\d.]+) F", rendered, re.M))


# ------------------------------------------------------------------- the length
def test_the_default_purge_is_pushed_in_full():
    # The whole point is the amount. If the slicing loses a remainder, the ball
    # is short and nothing says so.
    rendered, _ = render("_KCTRL_PURGE_BALL", {"TEMP": 190})
    assert extruded(rendered) == pytest.approx(
        variables("_KCTRL_PURGE_BALL")["purge_mm"], abs=1e-6)


@pytest.mark.parametrize("length", [30, 61, 119, 300, 421, 1000])
def test_any_length_is_pushed_in_full(length):
    rendered, _ = render("_KCTRL_PURGE_BALL", {"TEMP": 190, "LEN": length})
    assert extruded(rendered) == pytest.approx(length, abs=1e-3)


def test_the_default_is_at_least_three_times_the_stock_flush():
    # box.cfg declares box_need_clean_length: 140 on this machine and the
    # operator judged the result on the plate: it needs three to four times
    # more before the strand balls up and lets go.
    total = variables("_KCTRL_PURGE_BALL")["purge_mm"] + 140.0
    assert total >= 3 * 140.0


def test_a_zero_length_purges_nothing():
    rendered, _ = render("_KCTRL_PURGE_BALL", {"TEMP": 190, "LEN": 0})
    assert "G1 E" not in rendered
    # The comment naming it is not a call to it.
    assert not re.search(r"^\s*BOX_GO_TO_EXTRUDE_POS", rendered, re.M)


# -------------------------------------------------------------- the temperature
def test_the_purge_waits_on_the_gcode_temperature():
    # "JAMAIS que le CFS controle cette putain de temperature": this purge is
    # the one on the route whose temperature is ours, and it must be reached
    # before any filament moves, not merely requested.
    rendered, _ = render("_KCTRL_PURGE_BALL", {"TEMP": 245})
    assert "M109 S245" in rendered
    assert rendered.index("M109 S245") < rendered.index("G1 E")


def test_the_head_is_placed_over_the_bin_before_extruding():
    # 300 mm extruded at the wrong place is not a mistake worth risking on the
    # assumption that the previous macro left the head where we think.
    rendered, _ = render("_KCTRL_PURGE_BALL", {"TEMP": 190})
    assert rendered.index("BOX_GO_TO_EXTRUDE_POS") < rendered.index("G1 E")


def test_the_purge_is_relative_and_waited_on():
    rendered, _ = render("_KCTRL_PURGE_BALL", {"TEMP": 190})
    assert "M83" in rendered and rendered.index("M83") < rendered.index("G1 E")
    assert re.search(r"^\s*M400", rendered, re.M)
    assert rendered.rindex("M400") > rendered.rindex("G1 E")


def test_the_operator_is_told_what_was_pushed():
    _, responses = render("_KCTRL_PURGE_BALL", {"TEMP": 190, "LEN": 420})
    assert responses and "420" in responses[0]


# ------------------------------------------------------------------- the order
def test_the_stock_flush_stays_last_over_the_bin():
    # Whatever BOX_MATERIAL_FLUSH does at the end of its routine to detach the
    # blob is what has always worked here. Our purge grows the ball, the stock
    # one is still what lets it go.
    start = commands("START_PRINT")
    assert start.index("_KCTRL_PURGE_BALL") < start.index("BOX_MATERIAL_FLUSH")


def test_the_length_is_not_handed_to_the_stock_macro():
    # box.cfg declares box_need_clean_length_max: 140, so a LEN above it could
    # be clamped without a word. A silently clamped purge is the worst kind:
    # nothing reports it and the defect only shows up on the plate.
    start = commands("START_PRINT")
    flush = [line for line in start.splitlines() if "BOX_MATERIAL_FLUSH" in line]
    assert flush and all("LEN" not in line for line in flush)
