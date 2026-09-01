# K1 Control - merge four probed quadrants into one referenced 11x11 profile
#
# PRTouch V2 raises past 36 contacts inside one sequence, so a real 11x11 is
# acquired as four bounded 6x6 quadrants that share the centre row and the
# centre column (ADR-013). This module stitches them back together.
#
# Two things make the result trustworthy and neither can be done from Jinja:
#
#   - each quadrant may carry its own constant vertical bias, so the shared
#     junction is used to estimate one additive offset per quadrant before the
#     matrices are merged, and the residual spread is reported;
#   - the merged matrix is normalised to zero at the Z reference point (ADR-046)
#     before being written, because this bed_mesh build has no
#     zero_reference_position and applies a stored profile as-is. A profile that
#     is not zero at the probing point silently shifts every print.
#
# The profile is written straight into the autosave block of printer.cfg rather
# than through SAVE_CONFIG, which on this machine would also commit unrelated
# pending state that must never be persisted.

import os

REFERENCE_XY = (150.0, 150.0)
QUADRANTS = ("K1_SUB_SW", "K1_SUB_SE", "K1_SUB_NW", "K1_SUB_NE")
MAX_JUNCTION_SPREAD = 0.05


class KctrlMesh:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object("gcode")
        self.gcode.register_command(
            "KCTRL_MESH_MERGE", self.cmd_KCTRL_MESH_MERGE,
            desc="Merge the four acquired quadrants into one referenced profile")
        self.gcode.register_command(
            "KCTRL_MESH_SHOW", self.cmd_KCTRL_MESH_SHOW,
            desc="Print a stored mesh profile as a readable map")

    # ---------------------------------------------------------------- helpers
    def _profiles(self):
        bed_mesh = self.printer.lookup_object("bed_mesh", None)
        if bed_mesh is None:
            raise self.gcode.error("K1 Control: no bed_mesh on this printer")
        return bed_mesh.get_status(None).get("profiles", {})

    def _grid(self, profiles, name):
        prof = profiles.get(name)
        if prof is None:
            raise self.gcode.error(
                "K1 Control: quadrant %s is missing; run KCTRL_MESH_ACQUIRE first"
                % name)
        params = prof["mesh_params"]
        points = prof["points"]
        return {
            "min_x": float(params["min_x"]), "max_x": float(params["max_x"]),
            "min_y": float(params["min_y"]), "max_y": float(params["max_y"]),
            "nx": int(params["x_count"]), "ny": int(params["y_count"]),
            "points": points,
        }

    @staticmethod
    def _axis(lo, hi, count):
        if count < 2:
            return [lo]
        step = (hi - lo) / (count - 1)
        return [lo + step * i for i in range(count)]

    # ------------------------------------------------------------------ merge
    def _collect(self, profiles):
        # Gather every probed point of every quadrant, keyed by rounded position
        # so the shared row and column line up exactly.
        per_quadrant = {}
        for name in QUADRANTS:
            g = self._grid(profiles, name)
            if g["nx"] * g["ny"] > 36:
                raise self.gcode.error(
                    "K1 Control: quadrant %s holds %d contacts, over the 36 limit"
                    % (name, g["nx"] * g["ny"]))
            xs = self._axis(g["min_x"], g["max_x"], g["nx"])
            ys = self._axis(g["min_y"], g["max_y"], g["ny"])
            cells = {}
            for j, y in enumerate(ys):
                for i, x in enumerate(xs):
                    cells[(round(x, 3), round(y, 3))] = float(g["points"][j][i])
            per_quadrant[name] = cells
        return per_quadrant

    def _debias(self, per_quadrant):
        # One additive offset per quadrant, estimated on the points it shares
        # with the quadrants already placed. The first quadrant defines the
        # reference frame and keeps an offset of zero.
        placed = dict(per_quadrant[QUADRANTS[0]])
        counts = dict((k, 1) for k in placed)
        offsets = {QUADRANTS[0]: 0.0}
        spreads = []
        for name in QUADRANTS[1:]:
            cells = per_quadrant[name]
            shared = [k for k in cells if k in placed]
            if not shared:
                raise self.gcode.error(
                    "K1 Control: quadrant %s shares no point with the others" % name)
            diffs = [placed[k] - cells[k] for k in shared]
            offset = sum(diffs) / len(diffs)
            spread = max(diffs) - min(diffs)
            spreads.append((name, len(shared), offset, spread))
            if spread > MAX_JUNCTION_SPREAD:
                raise self.gcode.error(
                    "K1 Control: quadrant %s disagrees with its neighbours by "
                    "%.4f mm over %d shared points, above the %.2f mm limit; "
                    "the acquisition is not trustworthy, run it again"
                    % (name, spread, len(shared), MAX_JUNCTION_SPREAD))
            offsets[name] = offset
            for k, v in cells.items():
                corrected = v + offset
                if k in placed:
                    n = counts[k]
                    placed[k] = (placed[k] * n + corrected) / (n + 1)
                    counts[k] = n + 1
                else:
                    placed[k] = corrected
                    counts[k] = 1
        return placed, offsets, spreads

    def _matrix(self, placed):
        xs = sorted(set([k[0] for k in placed]))
        ys = sorted(set([k[1] for k in placed]))
        matrix = []
        for y in ys:
            row = []
            for x in xs:
                if (x, y) not in placed:
                    raise self.gcode.error(
                        "K1 Control: the merged grid has a hole at X%.1f Y%.1f"
                        % (x, y))
                row.append(placed[(x, y)])
            matrix.append(row)
        return xs, ys, matrix

    @staticmethod
    def _reference_value(xs, ys, matrix):
        rx, ry = REFERENCE_XY
        try:
            i = xs.index(round(rx, 3))
            j = ys.index(round(ry, 3))
        except ValueError:
            return None
        return matrix[j][i]

    # ------------------------------------------------------------ persistence
    def _config_path(self):
        start_args = self.printer.get_start_args()
        path = start_args.get("config_file")
        if not path or not os.path.exists(path):
            raise self.gcode.error("K1 Control: cannot locate printer.cfg")
        return path

    def _write_profile(self, name, matrix, params):
        path = self._config_path()
        handle = open(path, "r")
        try:
            lines = handle.read().split("\n")
        finally:
            handle.close()
        header = "#*# [bed_mesh %s]" % name
        # Drop any previous block for this profile, then append a fresh one.
        out = []
        skipping = False
        for line in lines:
            stripped = line.strip()
            if stripped == header:
                skipping = True
                continue
            if skipping:
                if stripped.startswith("#*# [") or not stripped.startswith("#*#"):
                    skipping = False
                else:
                    continue
            out.append(line)
        while out and out[-1].strip() == "":
            out.pop()
        block = [header, "#*# version = 1", "#*# points ="]
        for row in matrix:
            block.append("#*# \t" + ", ".join(["%.6f" % v for v in row]))
        for key, value in params:
            block.append("#*# %s = %s" % (key, value))
        out.extend(block)
        out.append("")
        tmp = path + ".kctrl-tmp"
        handle = open(tmp, "w")
        try:
            handle.write("\n".join(out))
        finally:
            handle.close()
        os.rename(tmp, path)
        return path

    # --------------------------------------------------------------- commands
    def cmd_KCTRL_MESH_MERGE(self, gcmd):
        band = gcmd.get_int("BED_TEMP", minval=0, maxval=150)
        plate = gcmd.get_int("PLATE", 1, minval=1, maxval=99)
        probe_rev = gcmd.get_int("PROBE_REV", 1, minval=1, maxval=99)

        profiles = self._profiles()
        per_quadrant = self._collect(profiles)
        placed, offsets, spreads = self._debias(per_quadrant)
        xs, ys, matrix = self._matrix(placed)

        if len(xs) != 11 or len(ys) != 11:
            raise self.gcode.error(
                "K1 Control: the merge produced a %dx%d grid, expected 11x11"
                % (len(xs), len(ys)))

        reference = self._reference_value(xs, ys, matrix)
        if reference is None:
            raise self.gcode.error(
                "K1 Control: the grid has no point at the X%.0f Y%.0f reference; "
                "an odd point count on a centred interval is required (ADR-046)"
                % REFERENCE_XY)
        matrix = [[v - reference for v in row] for row in matrix]

        flat = [v for row in matrix for v in row]
        name = "k1_p%03d_t%03d_r%03d_n%02dx%02d" % (
            plate, band, probe_rev, len(xs), len(ys))
        params = [
            ("x_count", len(xs)), ("y_count", len(ys)),
            ("mesh_x_pps", 2), ("mesh_y_pps", 2),
            ("algo", "bicubic"), ("tension", 0.2),
            ("min_x", "%.1f" % xs[0]), ("max_x", "%.1f" % xs[-1]),
            ("min_y", "%.1f" % ys[0]), ("max_y", "%.1f" % ys[-1]),
        ]
        path = self._write_profile(name, matrix, params)

        for qname, shared, offset, spread in spreads:
            gcmd.respond_info(
                "K1 Control: %s aligned on %d shared points, bias %+.4f mm, "
                "spread %.4f mm" % (qname, shared, offset, spread))
        gcmd.respond_info(
            "K1 Control: %s merged, 121 real contacts, zero at X%.0f Y%.0f "
            "(shifted by %+.4f mm), range %+.4f .. %+.4f mm"
            % (name, REFERENCE_XY[0], REFERENCE_XY[1], -reference,
               min(flat), max(flat)))
        gcmd.respond_info(
            "K1 Control: written into %s. Restart to load it."
            % os.path.basename(path))

    def cmd_KCTRL_MESH_SHOW(self, gcmd):
        name = gcmd.get("PROFILE")
        profiles = self._profiles()
        if name not in profiles:
            raise self.gcode.error("K1 Control: no profile named %s" % name)
        g = self._grid(profiles, name)
        xs = self._axis(g["min_x"], g["max_x"], g["nx"])
        ys = self._axis(g["min_y"], g["max_y"], g["ny"])
        gcmd.respond_info("Y\\X   " + " ".join(["%7.0f" % x for x in xs]))
        for j in range(len(ys) - 1, -1, -1):
            gcmd.respond_info(
                "%5.0f " % ys[j]
                + " ".join(["%+7.3f" % v for v in g["points"][j]]))


def load_config(config):
    return KctrlMesh(config)
