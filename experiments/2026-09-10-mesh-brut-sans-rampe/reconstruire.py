# Rebuild the 11x11 profile from the raw contacts of the four quadrant runs of
# 2026-09-10 (09:35 to 09:52), without the ramp the firmware adds before a
# profile is saved (document 73).
#
#   python reconstruire.py
#
# Reads, from this folder:
#   contacts-bruts.txt         "probe at X,Y is z=" lines of klippy.log, per run
#   matrices-enregistrees.txt  the profiles the firmware saved for the same runs
#   profil-actif-avant.json    the live profile at the time of the rebuild
# Writes:
#   k1_p001_t055_r001_n11x11.etape1.json   half of the way (KCTRL_MESH_APPLY
#                                          refuses a move above 0.15 mm)
#   k1_p001_t055_r001_n11x11.etape2.json   the raw-based profile
#   rapport.txt                            what is printed below
#
# The last contact of each run is kept as-is by the firmware while every other
# point receives the ramp, and in three runs out of five it is 0.10 to 0.19 mm
# above its own neighbours and above the same point measured by another run.
# It is dropped whenever another run covers the same position.

import io, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
PROFILE = "k1_p001_t055_r001_n11x11"
QUADS = ("K1_SUB_SW", "K1_SUB_SE", "K1_SUB_NW", "K1_SUB_NE")
REFERENCE = (150.0, 150.0)
MAX_EDIT_DELTA = 0.15
SCREWS = [("avant-gauche", 18.5, 23.7), ("avant-droit", 276.5, 23.7),
          ("arriere-gauche", 48.5, 273.7), ("arriere-droit", 246.5, 273.7)]
EIGHTH = 0.7 / 8.0

report = []
def say(text=""):
    report.append(text)
    print(text)

# ---------------------------------------------------------------- raw values
runs = {}
cur = None
for line in io.open(os.path.join(HERE, "contacts-bruts.txt"), encoding="utf-8"):
    line = line.strip()
    m = re.match(r"--- window (K1_\w+)", line)
    if m:
        cur = m.group(1)
        runs[cur] = []
        continue
    if line:
        t, x, y, z = line.split()
        runs[cur].append((t, float(x), float(y), float(z)))

saved = {}
cur = None
for line in io.open(os.path.join(HERE, "matrices-enregistrees.txt"), encoding="utf-8"):
    m = re.match(r"--- (K1_\w+) at line", line)
    if m:
        cur = m.group(1)
        saved[cur] = []
        continue
    if cur and re.match(r"^\s*-?\d", line):
        saved[cur].append([float(v) for v in line.split(",")])

def grid_of(run):
    xs = sorted(set(p[1] for p in run))
    ys = sorted(set(p[2] for p in run))
    g = dict(((x, y), z) for _, x, y, z in run)
    return xs, ys, g

say("=== saved minus raw, per run (the firmware ramp)")
for name in ("K1_SCREWS",) + QUADS:
    run = runs[name]
    xs, ys, g = grid_of(run)
    sv = saved[name]
    corr = [[sv[j][i] - g[(x, y)] for i, x in enumerate(xs)] for j, y in enumerate(ys)]
    last, prev = run[-1], run[-2]
    per_row = []
    for j, row in enumerate(corr):
        cells = row[:-1] if j == len(corr) - 1 else row
        per_row.append(sum(cells) / len(cells))
    say("%-10s %d rows  per row: %s  (spread inside a row under %.3f)"
        % (name, len(ys), " ".join("%+.3f" % v for v in per_row),
           max(max(r[:-1]) - min(r[:-1]) for r in corr)))
    say("           last contact X%.0f Y%.0f: raw %+.3f, saved %+.3f, previous contact raw %+.3f"
        % (last[1], last[2], last[3], sv[ys.index(last[2])][xs.index(last[1])], prev[3]))

# ------------------------------------------------------------ rebuild 11x11
cells = {}
dropped = []
for name in QUADS:
    run = runs[name]
    last = run[-1]
    covered = any((last[1], last[2]) in set((p[1], p[2]) for p in runs[o])
                  for o in QUADS if o != name)
    for k, (t, x, y, z) in enumerate(run):
        if k == len(run) - 1 and covered:
            dropped.append("%s X%.0f Y%.0f %+.3f" % (name, x, y, z))
            continue
        cells.setdefault((x, y), []).append((name, z))
say("=== last contacts dropped (another run covers the point): " + "; ".join(dropped))

say("=== agreement of the raw values between runs at the shared points")
for k in sorted(cells):
    vals = cells[k]
    if len(vals) > 1:
        zs = [z for _, z in vals]
        say("   X%3.0f Y%3.0f  %s  spread %.3f"
            % (k[0], k[1], "  ".join("%s %+.3f" % (n[7:], z) for n, z in vals), max(zs) - min(zs)))

placed = dict((k, z) for k, vals in cells.items() for n, z in vals if n == QUADS[0])
for name in QUADS[1:]:
    mine = dict((k, z) for k, vals in cells.items() for n, z in vals if n == name)
    shared = [k for k in mine if k in placed]
    diffs = [placed[k] - mine[k] for k in shared]
    off = sum(diffs) / len(diffs)
    resid = max(abs(d - off) for d in diffs)
    say("=== offset %s %+.4f over %d shared points, residual %.4f" % (name, off, len(shared), resid))
    for k, z in mine.items():
        placed[k] = (placed[k] + z + off) / 2.0 if k in placed else z + off
xs = sorted(set(k[0] for k in placed))
ys = sorted(set(k[1] for k in placed))
assert len(xs) == 11 and len(ys) == 11, (len(xs), len(ys))
ref = placed[REFERENCE]
final = [[round(placed[(x, y)] - ref, 6) for x in xs] for y in ys]
say("=== raw-based 11x11, zero at X150 Y150")
for y, row in zip(ys, final):
    say("y=%3.0f " % y + " ".join("%+.3f" % v for v in row))

live = json.load(io.open(os.path.join(HERE, "profil-actif-avant.json"), encoding="utf-8"))
before = live["profiles"][PROFILE]["points"]
say("=== row means: raw-based, live profile before, move")
for j, y in enumerate(ys):
    say("   y=%3.0f  %+.3f  %+.3f  %+.3f"
        % (y, sum(final[j]) / 11, sum(before[j]) / 11, sum(final[j][i] - before[j][i] for i in range(11)) / 11))
moves = [abs(final[j][i] - before[j][i]) for j in range(11) for i in range(11)]
say("=== largest move %.3f mm, %d point(s) above the %.2f limit of one KCTRL_MESH_APPLY"
    % (max(moves), sum(1 for v in moves if v > MAX_EDIT_DELTA), MAX_EDIT_DELTA))

step1 = [[round(before[j][i] + (final[j][i] - before[j][i]) / 2.0, 6) for i in range(11)] for j in range(11)]
for label, matrix, base in (("etape1", step1, before), ("etape2", final, step1)):
    worst = max(abs(matrix[j][i] - base[j][i]) for j in range(11) for i in range(11))
    assert worst <= MAX_EDIT_DELTA, (label, worst)
    assert matrix[5][5] == 0.0 and base[5][5] == 0.0
    path = os.path.join(HERE, "%s.%s.json" % (PROFILE, label))
    io.open(path, "w", encoding="utf-8", newline="\n").write(json.dumps(
        {"profile": PROFILE, "points": matrix}, indent=1))
    say("=== %s written, largest move %.3f mm" % (os.path.basename(path), worst))

# ------------------------------------------------------------------- screws
def interp(xs, ys, g, x, y):
    i = max(0, min(len(xs) - 2, max(k for k in range(len(xs)) if xs[k] <= x)))
    j = max(0, min(len(ys) - 2, max(k for k in range(len(ys)) if ys[k] <= y)))
    tx = (x - xs[i]) / (xs[i + 1] - xs[i])
    ty = (y - ys[j]) / (ys[j + 1] - ys[j])
    z0 = g[j][i] + tx * (g[j][i + 1] - g[j][i])
    z1 = g[j + 1][i] + tx * (g[j + 1][i + 1] - g[j + 1][i])
    return z0 + ty * (z1 - z0)

sxs, sys_, sg = grid_of(runs["K1_SCREWS"])
rawg = [[sg[(x, y)] for x in sxs] for y in sys_]
for label, gxs, gys, grid in (("K1_SCREWS raw", sxs, sys_, rawg),
                               ("K1_SCREWS saved", sxs, sys_, saved["K1_SCREWS"]),
                               ("11x11 raw-based", xs, ys, final),
                               ("11x11 live before", xs, ys, before)):
    hs = [(n, interp(gxs, gys, grid, x, y)) for n, x, y in SCREWS]
    lo = min(h for _, h in hs)
    say("=== screws from %s: span %.3f mm; " % (label, max(h for _, h in hs) - lo)
        + "  ".join("%s %+.3f visser %.1f/8" % (n, h, (h - lo) / EIGHTH) for n, h in hs))

io.open(os.path.join(HERE, "rapport.txt"), "w", encoding="utf-8", newline="\n").write("\n".join(report) + "\n")
