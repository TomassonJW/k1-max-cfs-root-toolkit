"""Decoupe un journal Klipper en sequences de chargement (une par cmd_T) et
donne, pour chacune, l'heure et le decalage de chaque etape du module CFS de
Creality : coupe, rembobinage, poussee, morsure, tampon, relance, purge.

Usage : python phases.py journal.log
"""
import re
import sys

path = sys.argv[1]
REC = re.compile(r"^\[(\w+)\] \d{4}-\d{2}-\d{2} (\d{2}):(\d{2}):(\d{2}),(\d+) (?:\[[^\]]*\] ){0,2}(.*)$")
MARKS = [
    ("T", re.compile(r"K1 Control: (T\d+) -> filament \d+ \(\w+\) sur (T\d[A-D]), ([^,]*)")),
    ("cmd_T", re.compile(r"cmd_T vtnn=(\w+)")),
    ("tete", re.compile(r"get_fialment_sensor_detect\(\)=(True|False)")),
    ("vers_couteau", re.compile(r"box_action_move_to_cut$")),
    ("coupe", re.compile(r"move_to_cut\(\)=(True|False)")),
    ("rembob_debut", re.compile(r"box_retrude_material 1$")),
    ("recul_E", re.compile(r"extrude = (-[\d.]+), velocity")),
    ("capteur_coupe_0", re.compile(r"\[box\] cut sensor state:0")),
    ("poussee", re.compile(r"box_action\.box_extrude_material\((\w+)\)$")),
    ("stage5", re.compile(r"stage5 ret_state: (\w+)")),
    ("morsure", re.compile(r"extrude_process_stage7 ret: (\w+),(\w+)")),
    ("tampon", re.compile(r"buffer_state: (0x\w+)")),
    ("relance", re.compile(r"auto_retry_process: \w+, auto_retry_(\w+)")),
    ("charge", re.compile(r"box_action_extrude_material\(\w+\) = (True|False)")),
    ("purge", re.compile(r"flush_volume: (\d+), flush_len: (\d+)")),
    ("troncons", re.compile(r"length: (\[[^\]]*\])")),
    ("roue", re.compile(r"current_measuring_wheel = [-\d.]+, diff = ([-\d.]+)")),
    ("purge_E", re.compile(r"extrude = ([\d.]+), velocity: [\[(]([\d.]+)")),
    ("purge_fin", re.compile(r"material_change_flush\(\w+,\w+\) = (True|False)")),
    ("z_restore", re.compile(r"box_action\.z_restore\(\)")),
    ("fait", re.compile(r"K1 Control: (T\d+) fait")),
    ("amorce", re.compile(r"ligne d'amorce")),
    ("code", re.compile(r'"code":"(key\d+)"')),
    ("pause", re.compile(r"do_after_pause: ")),
]
REPEAT = {"tampon", "relance", "purge_E", "code", "stage5", "morsure", "recul_E", "coupe", "poussee",
          "charge", "purge", "troncons", "roue", "purge_fin", "cmd_T"}

segments = []
cur = None
pending_t = None
for line in open(path, encoding="utf-8", errors="replace"):
    m = REC.match(line.rstrip("\n"))
    if not m:
        continue
    lvl, hh, mm, ss, ms, msg = m.groups()
    t = int(hh) * 3600 + int(mm) * 60 + int(ss) + int(ms) / 1000.0
    hms = "%s:%s:%s" % (hh, mm, ss)
    for name, rx in MARKS:
        x = rx.search(msg)
        if not x:
            continue
        if name == "T":
            pending_t = (hms, t, x.groups())
            continue
        if name == "cmd_T":
            cur = {"t0": t, "hms": hms, "label": pending_t[2] if pending_t else None, "ev": []}
            pending_t = None
            segments.append(cur)
        if cur is None:
            continue
        if name not in REPEAT and any(e[0] == name for e in cur["ev"]):
            continue
        cur["ev"].append((name, t - cur["t0"], hms, x.groups()))


def show(ev):
    print("  +%6.1f s %s %-16s %s%s" % (ev[1], ev[2], ev[0], ",".join(ev[3]),
                                         (" x%d" % ev[4]) if ev[4] > 1 else ""))


for s in segments:
    print("=== %s %s" % (s["hms"], s["label"]))
    last = None
    for name, dt, hms, g in s["ev"]:
        if name in ("tampon", "purge_E") and last and last[0] == name and last[3] == g:
            last[4] += 1
            continue
        if last:
            show(last)
        last = [name, dt, hms, g, 1]
    if last:
        show(last)
