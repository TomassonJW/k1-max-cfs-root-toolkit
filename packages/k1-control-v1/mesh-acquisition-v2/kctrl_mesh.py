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

import json
import os
import time

REFERENCE_XY = (150.0, 150.0)
QUADRANTS = ("K1_SUB_SW", "K1_SUB_SE", "K1_SUB_NW", "K1_SUB_NE")
MAX_JUNCTION_SPREAD = 0.05
# Largest correction one edit command may apply. Hand tuning on a printed square
# resolves hundredths; a tenth is already a different bed. Anything larger is a
# typo, and a typo that reaches the first layer costs a print.
MAX_EDIT_DELTA = 0.15

# The operator describes the bed in plain words - front edge, right edge, back
# right corner - and both languages are accepted because that is how the
# corrections arrive.
EDGES = {
    "front": "front", "avant": "front",
    "back": "back", "arriere": "back", "fond": "back",
    "left": "left", "gauche": "left",
    "right": "right", "droit": "right", "droite": "right",
}
CORNERS = {
    "front_left": (0, 0), "avant_gauche": (0, 0),
    "front_right": (1, 0), "avant_droit": (1, 0),
    "back_left": (0, 1), "arriere_gauche": (0, 1),
    "back_right": (1, 1), "arriere_droit": (1, 1),
}


class KctrlMesh:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object("gcode")
        # Bed screw geometry. The pitch is what converts a height error into a
        # fraction of a turn; M4 is 0.7 mm per revolution. The positions are
        # configurable because a published coordinate that is 20 mm off costs
        # 0.05 mm of correction on a bed tilted by 0.7 mm end to end, which is
        # the same size as the error being chased.
        self.screw_pitch = config.getfloat("screw_pitch", 0.7, above=0.)
        self.screws = []
        for index in range(1, 9):
            raw = config.get("screw%d" % index, None)
            if raw is None:
                continue
            name = config.get("screw%d_name" % index, "screw%d" % index)
            parts = raw.split(",")
            if len(parts) != 2:
                raise config.error(
                    "K1 Control: screw%d must be 'x,y'" % index)
            self.screws.append((name, float(parts[0]), float(parts[1])))
        self.gcode.register_command(
            "KCTRL_MESH_MERGE", self.cmd_KCTRL_MESH_MERGE,
            desc="Merge the four acquired quadrants into one referenced profile")
        self.gcode.register_command(
            "KCTRL_MESH_SHOW", self.cmd_KCTRL_MESH_SHOW,
            desc="Print a stored mesh profile as a readable map")
        self.gcode.register_command(
            "KCTRL_SCREWS_REPORT", self.cmd_KCTRL_SCREWS_REPORT,
            desc="Turn a probed grid into a per screw correction in eighths of a turn")
        self.gcode.register_command(
            "KCTRL_MESH_EDIT", self.cmd_KCTRL_MESH_EDIT,
            desc="Shift an edge, a corner or one point of a stored mesh profile")
        self.gcode.register_command(
            "KCTRL_MESH_UNDO", self.cmd_KCTRL_MESH_UNDO,
            desc="Revert the last KCTRL_MESH_EDIT")
        self.gcode.register_command(
            "KCTRL_MESH_APPLY", self.cmd_KCTRL_MESH_APPLY,
            desc="Apply a whole edited matrix from a JSON file, keeping a backup")
        # One step of history is enough for hand tuning: the operator judges a
        # correction on the next printed square, not three commands later.
        self._undo = None

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
            # The offset itself is removed by the merge, so what qualifies the
            # acquisition is what survives it: the largest residual deviation
            # from that offset. Comparing the raw range instead would reject a
            # sound acquisition, since a symmetric range is about twice the
            # deviation it comes from.
            residual = max([abs(d - offset) for d in diffs])
            spreads.append((name, len(shared), offset, residual))
            if residual > MAX_JUNCTION_SPREAD:
                raise self.gcode.error(
                    "K1 Control: quadrant %s still disagrees with its neighbours "
                    "by %.4f mm over %d shared points once its bias is removed, "
                    "above the %.2f mm limit; the acquisition is not trustworthy, "
                    "run it again"
                    % (name, residual, len(shared), MAX_JUNCTION_SPREAD))
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

    def _write_profile(self, name, matrix, params, drop=()):
        path = self._config_path()
        handle = open(path, "r")
        try:
            lines = handle.read().split("\n")
        finally:
            handle.close()
        header = "#*# [bed_mesh %s]" % name
        # Drop the previous block for this profile and every working profile
        # named in drop, then append a fresh one. The quadrants are scaffolding:
        # once merged they are noise in the user's profile list.
        headers = set([header])
        for other in drop:
            headers.add("#*# [bed_mesh %s]" % other)
        out = []
        skipping = False
        for line in lines:
            stripped = line.strip()
            if stripped in headers:
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
        # The file is rewritten without the quadrants; drop them from memory too
        # so they disappear from the profile list without waiting for a restart.
        path = self._write_profile(name, matrix, params, drop=QUADRANTS)
        for quadrant in QUADRANTS:
            self.gcode.run_script_from_command(
                "BED_MESH_PROFILE REMOVE=%s" % quadrant)

        for qname, shared, offset, residual in spreads:
            gcmd.respond_info(
                "K1 Control: %s aligned on %d shared points, bias %+.4f mm "
                "removed, residual %.4f mm" % (qname, shared, offset, residual))
        gcmd.respond_info(
            "K1 Control: %s merged, 121 real contacts, zero at X%.0f Y%.0f "
            "(shifted by %+.4f mm), range %+.4f .. %+.4f mm"
            % (name, REFERENCE_XY[0], REFERENCE_XY[1], -reference,
               min(flat), max(flat)))
        gcmd.respond_info(
            "K1 Control: written into %s. Restart to load it."
            % os.path.basename(path))

    @staticmethod
    def _interpolate(xs, ys, points, x, y):
        # Bilinear read of the probed grid. Returns None outside it rather than
        # extrapolating, because an extrapolated screw height is a guess and a
        # guess here turns into a wrong number of turns.
        if x < xs[0] or x > xs[-1] or y < ys[0] or y > ys[-1]:
            return None
        i = 0
        while i < len(xs) - 2 and x > xs[i + 1]:
            i += 1
        j = 0
        while j < len(ys) - 2 and y > ys[j + 1]:
            j += 1
        fx = 0.0 if xs[i + 1] == xs[i] else (x - xs[i]) / (xs[i + 1] - xs[i])
        fy = 0.0 if ys[j + 1] == ys[j] else (y - ys[j]) / (ys[j + 1] - ys[j])
        low = points[j][i] + fx * (points[j][i + 1] - points[j][i])
        high = points[j + 1][i] + fx * (points[j + 1][i + 1] - points[j + 1][i])
        return low + fy * (high - low)

    @staticmethod
    def _fit_plane(samples):
        # Least squares fit of z = a*x + b*y + c over the probed points. Solved
        # with the normal equations; a 3x3 system does not warrant more.
        n = float(len(samples))
        sx = sum([p[0] for p in samples])
        sy = sum([p[1] for p in samples])
        sz = sum([p[2] for p in samples])
        sxx = sum([p[0] * p[0] for p in samples])
        syy = sum([p[1] * p[1] for p in samples])
        sxy = sum([p[0] * p[1] for p in samples])
        sxz = sum([p[0] * p[2] for p in samples])
        syz = sum([p[1] * p[2] for p in samples])
        m = [[sxx, sxy, sx], [sxy, syy, sy], [sx, sy, n]]
        v = [sxz, syz, sz]
        # Gaussian elimination with partial pivoting.
        for col in range(3):
            pivot = max(range(col, 3), key=lambda r: abs(m[r][col]))
            if abs(m[pivot][col]) < 1e-12:
                return None
            m[col], m[pivot] = m[pivot], m[col]
            v[col], v[pivot] = v[pivot], v[col]
            for row in range(col + 1, 3):
                factor = m[row][col] / m[col][col]
                for k in range(col, 3):
                    m[row][k] -= factor * m[col][k]
                v[row] -= factor * v[col]
        out = [0.0, 0.0, 0.0]
        for col in range(2, -1, -1):
            acc = v[col] - sum([m[col][k] * out[k] for k in range(col + 1, 3)])
            out[col] = acc / m[col][col]
        return out

    def cmd_KCTRL_SCREWS_REPORT(self, gcmd):
        name = gcmd.get("PROFILE", "K1_SCREWS")
        if not self.screws:
            raise self.gcode.error(
                "K1 Control: no screw position configured; add screw1..screwN "
                "to the [kctrl_mesh] section")
        profiles = self._profiles()
        g = self._grid(profiles, name)
        xs = self._axis(g["min_x"], g["max_x"], g["nx"])
        ys = self._axis(g["min_y"], g["max_y"], g["ny"])
        samples = []
        for j, y in enumerate(ys):
            for i, x in enumerate(xs):
                samples.append((x, y, float(g["points"][j][i])))

        plane = self._fit_plane(samples)
        if plane is None:
            raise self.gcode.error("K1 Control: the probed grid is degenerate")
        a, b, c = plane
        residuals = [abs(z - (a * x + b * y + c)) for x, y, z in samples]
        rms = (sum([r * r for r in residuals]) / len(residuals)) ** 0.5
        worst = max(residuals)

        gcmd.respond_info(
            "K1 Control: plane fitted on %d contacts, residual RMS %.4f mm, "
            "worst %.4f mm" % (len(samples), rms, worst))
        if worst > 0.05:
            gcmd.respond_info(
                "K1 Control: WARNING the bed departs from a plane by %.3f mm. "
                "The screws set a plane and cannot correct that part; expect a "
                "floor on what levelling can achieve." % worst)

        # The screw height is read from the probed grid, never from the fitted
        # plane. On a bed that departs from a plane the least squares surface
        # passes well away from the corners and can even reverse the ranking of
        # two screws, which sends the adjustment the wrong way. The plane is
        # kept only to quantify the warp.
        heights = []
        for nm, x, y in self.screws:
            z = self._interpolate(xs, ys, g["points"], x, y)
            if z is None:
                raise self.gcode.error(
                    "K1 Control: screw %s at X%.1f Y%.1f falls outside the "
                    "probed grid; widen MESH_MIN and MESH_MAX" % (nm, x, y))
            heights.append((nm, x, y, z))
        highest = max([h[3] for h in heights])
        lowest = min([h[3] for h in heights])
        pitch = self.screw_pitch
        gcmd.respond_info(
            "K1 Control: screw heights span %.4f mm; M%s pitch %.2f mm, so one "
            "eighth of a turn is %.4f mm"
            % (highest - lowest, "4" if abs(pitch - 0.7) < 1e-6 else "?",
               pitch, pitch / 8.0))
        # On this machine tightening moves the bed away from the nozzle, so the
        # all-tightening answer is the one that brings every screw down to the
        # lowest. That is the block Thomas acts on; the reverse is printed only
        # for the case where a screw has no travel left.
        eighth = pitch / 8.0
        gcmd.respond_info("K1 Control: VISSER (eloigne le plateau) - a faire")
        for nm, x, y, z in sorted(heights, key=lambda h: -h[3]):
            delta = z - lowest
            turns = delta / eighth
            verdict = "ne pas toucher" if turns < 0.4 else "visser %.1f huitiemes" % turns
            gcmd.respond_info(
                "   %-16s X%-5.0f Y%-5.0f  %+.4f mm  ->  %s"
                % (nm, x, y, z, verdict))
        gcmd.respond_info("K1 Control: DEVISSER (rapproche le plateau) - variante inverse")
        for nm, x, y, z in sorted(heights, key=lambda h: h[3]):
            delta = highest - z
            turns = delta / eighth
            verdict = "ne pas toucher" if turns < 0.4 else "devisser %.1f huitiemes" % turns
            gcmd.respond_info(
                "   %-16s X%-5.0f Y%-5.0f  %+.4f mm  ->  %s"
                % (nm, x, y, z, verdict))


    # ------------------------------------------------------------------- edits
    def _live_profile(self, name):
        # bed_mesh.get_status returns the profile manager's own dictionary, so
        # the point rows can be corrected in place. That matters: several edits
        # are applied in a row before a single reload, and reading the file back
        # between them would lose everything but the last one.
        profiles = self._profiles()
        prof = profiles.get(name)
        if prof is None:
            raise self.gcode.error("K1 Control: no profile named %s" % name)
        rows = prof.get("points")
        if not rows or not hasattr(rows[0], "__len__"):
            raise self.gcode.error(
                "K1 Control: profile %s does not expose editable points" % name)
        # config.getlists parses the stored matrix into a tuple of tuples, so a
        # freshly loaded profile is immutable and no edit could be written into
        # it. Promote it to lists once, in the live dictionary, so this and
        # every later edit lands on the same mutable rows. bed_mesh only ever
        # reads them, so the change of container is invisible to it.
        if not isinstance(rows, list) or not isinstance(rows[0], list):
            prof["points"] = [list(row) for row in rows]
        return prof, prof["points"]

    @staticmethod
    def _stored_params(prof):
        mp = prof["mesh_params"]
        order = ("x_count", "y_count", "mesh_x_pps", "mesh_y_pps",
                 "algo", "tension", "min_x", "max_x", "min_y", "max_y")
        out = []
        for key in order:
            value = mp[key]
            if key in ("min_x", "max_x", "min_y", "max_y"):
                out.append((key, "%.1f" % float(value)))
            elif key in ("x_count", "y_count", "mesh_x_pps", "mesh_y_pps"):
                out.append((key, int(value)))
            else:
                out.append((key, value))
        return out

    def _select(self, gcmd, nx, ny, xs, ys):
        ring = gcmd.get_int("RING", 0, minval=0)
        if ring * 2 >= min(nx, ny):
            raise self.gcode.error(
                "K1 Control: ring %d does not exist on a %dx%d grid"
                % (ring, nx, ny))
        lo_i, hi_i = ring, nx - 1 - ring
        lo_j, hi_j = ring, ny - 1 - ring

        edge = gcmd.get("EDGE", None)
        corner = gcmd.get("CORNER", None)
        col = gcmd.get_int("COL", None)
        row = gcmd.get_int("ROW", None)
        px = gcmd.get_float("X", None)
        py = gcmd.get_float("Y", None)

        given = [n for n, v in (("EDGE", edge), ("CORNER", corner),
                                ("COL/ROW", col if col is not None else row),
                                ("X/Y", px if px is not None else py))
                 if v is not None]
        if len(given) != 1:
            raise self.gcode.error(
                "K1 Control: give exactly one of EDGE, CORNER, COL+ROW or X+Y "
                "(received %s)" % (", ".join(given) if given else "none"))

        if edge is not None:
            key = edge.strip().lower()
            if key not in EDGES:
                raise self.gcode.error(
                    "K1 Control: EDGE must be one of %s"
                    % ", ".join(sorted(set(EDGES))))
            side = EDGES[key]
            # An edge excludes its two corners unless asked otherwise, because
            # a corner and the edge beside it are judged separately on the
            # printed square and rarely need the same correction.
            with_corners = gcmd.get_int("WITH_CORNERS", 0, minval=0, maxval=1)
            pad = 0 if with_corners else 1
            if side in ("front", "back"):
                j = lo_j if side == "front" else hi_j
                cells = [(i, j) for i in range(lo_i + pad, hi_i + 1 - pad)]
            else:
                i = lo_i if side == "left" else hi_i
                cells = [(i, j) for j in range(lo_j + pad, hi_j + 1 - pad)]
            label = "%s edge, ring %d%s" % (
                side, ring, "" if pad else ", corners included")
            return cells, label

        if corner is not None:
            key = corner.strip().lower().replace("-", "_").replace(" ", "_")
            if key not in CORNERS:
                raise self.gcode.error(
                    "K1 Control: CORNER must be one of %s"
                    % ", ".join(sorted(set(CORNERS))))
            right, back = CORNERS[key]
            i = hi_i if right else lo_i
            j = hi_j if back else lo_j
            return [(i, j)], "%s corner, ring %d" % (key, ring)

        if col is not None or row is not None:
            if col is None or row is None:
                raise self.gcode.error("K1 Control: COL and ROW go together")
            if not (0 <= col < nx) or not (0 <= row < ny):
                raise self.gcode.error(
                    "K1 Control: COL must be 0..%d and ROW 0..%d"
                    % (nx - 1, ny - 1))
            return [(col, row)], "point col %d row %d" % (col, row)

        if px is None or py is None:
            raise self.gcode.error("K1 Control: X and Y go together")
        i = min(range(nx), key=lambda k: abs(xs[k] - px))
        j = min(range(ny), key=lambda k: abs(ys[k] - py))
        step_x = (xs[-1] - xs[0]) / max(1, nx - 1)
        step_y = (ys[-1] - ys[0]) / max(1, ny - 1)
        if abs(xs[i] - px) > step_x / 2.0 or abs(ys[j] - py) > step_y / 2.0:
            raise self.gcode.error(
                "K1 Control: X%.0f Y%.0f is outside the grid" % (px, py))
        return [(i, j)], "point nearest X%.0f Y%.0f" % (px, py)

    @staticmethod
    def _delta(gcmd):
        raw = gcmd.get_float("DELTA", None)
        closer = gcmd.get_float("CLOSER", None)
        further = gcmd.get_float("FURTHER", None)
        given = [v for v in (raw, closer, further) if v is not None]
        if len(given) != 1:
            raise ValueError
        if raw is not None:
            return raw
        # A positive mesh value lifts the toolhead, so it moves the nozzle away
        # from the plate. CLOSER and FURTHER exist so a correction read off a
        # printed square - "this edge sits 0.02 too close" - is typed as it was
        # observed, with no sign to get wrong.
        if closer is not None:
            return -abs(closer)
        return abs(further)

    def cmd_KCTRL_MESH_EDIT(self, gcmd):
        bed_mesh = self.printer.lookup_object("bed_mesh", None)
        if bed_mesh is None:
            raise self.gcode.error("K1 Control: no bed_mesh on this printer")
        active = bed_mesh.get_status(None).get("profile_name")
        name = gcmd.get("PROFILE", active)
        if not name or name in ("default", "None"):
            raise self.gcode.error(
                "K1 Control: PROFILE is required and cannot be the default mesh")
        try:
            delta = self._delta(gcmd)
        except ValueError:
            raise self.gcode.error(
                "K1 Control: give exactly one of DELTA, CLOSER or FURTHER. "
                "CLOSER lowers the nozzle where the layer sits too high, "
                "FURTHER lifts it where the nozzle digs in")
        if abs(delta) > MAX_EDIT_DELTA:
            raise self.gcode.error(
                "K1 Control: %+.3f mm is beyond the %.2f mm limit of one edit"
                % (delta, MAX_EDIT_DELTA))
        if delta == 0.0:
            raise self.gcode.error("K1 Control: a zero correction changes nothing")

        prof, points = self._live_profile(name)
        g = self._grid(self._profiles(), name)
        xs = self._axis(g["min_x"], g["max_x"], g["nx"])
        ys = self._axis(g["min_y"], g["max_y"], g["ny"])
        cells, label = self._select(gcmd, g["nx"], g["ny"], xs, ys)

        # The profile is zero at the probing point and every print depends on
        # that (ADR-046). Editing the reference cell would silently move the
        # whole bed instead of one zone; the Z offset is the lever for that.
        rx, ry = REFERENCE_XY
        for i, j in cells:
            if abs(xs[i] - rx) < 1e-6 and abs(ys[j] - ry) < 1e-6:
                raise self.gcode.error(
                    "K1 Control: X%.0f Y%.0f is the Z reference and stays at "
                    "zero; shift the whole bed with KCTRL_Z_SAVE instead"
                    % (rx, ry))
        for i, j in cells:
            after = points[j][i] + delta
            if after < -2.0 or after > 2.0:
                raise self.gcode.error(
                    "K1 Control: X%.0f Y%.0f would reach %+.3f mm, outside the "
                    "-2..2 mm limit" % (xs[i], ys[j], after))

        if gcmd.get_int("PREVIEW", 0, minval=0, maxval=1):
            gcmd.respond_info(
                "K1 Control: preview only, %d point(s) of %s would move %+.3f mm"
                % (len(cells), label, delta))
            for i, j in cells:
                gcmd.respond_info(
                    "   X%-5.0f Y%-5.0f  %+.4f  ->  %+.4f"
                    % (xs[i], ys[j], points[j][i], points[j][i] + delta))
            return

        self._undo = (name, [list(r) for r in points])
        for i, j in cells:
            points[j][i] = points[j][i] + delta
        self._persist(name, prof, points, active)

        flat = [v for row in points for v in row]
        gcmd.respond_info(
            "K1 Control: %s, %d point(s) moved %+.3f mm (%s)"
            % (label, len(cells), delta,
               "nozzle further from the plate" if delta > 0
               else "nozzle closer to the plate"))
        gcmd.respond_info(
            "K1 Control: %s now spans %+.4f .. %+.4f mm, still zero at X%.0f Y%.0f"
            % (name, min(flat), max(flat), rx, ry))

    def cmd_KCTRL_MESH_UNDO(self, gcmd):
        if self._undo is None:
            raise self.gcode.error(
                "K1 Control: nothing to undo in this session")
        name, saved = self._undo
        bed_mesh = self.printer.lookup_object("bed_mesh", None)
        active = bed_mesh.get_status(None).get("profile_name")
        prof, points = self._live_profile(name)
        for j, row in enumerate(saved):
            for i, value in enumerate(row):
                points[j][i] = value
        self._persist(name, prof, points, active)
        self._undo = None
        gcmd.respond_info(
            "K1 Control: %s restored to its state before the last edit" % name)

    def _persist(self, name, prof, points, active):
        self._write_profile(name, points, self._stored_params(prof))
        # Reloading is what makes the correction visible on the next layer
        # instead of after a restart. Only the active profile is reloaded; a
        # profile edited while another one prints stays on disk until it is
        # loaded on purpose.
        if active == name:
            self.gcode.run_script_from_command(
                "BED_MESH_PROFILE LOAD=%s" % name)


    # ------------------------------------------------------- whole matrix apply
    def _backup(self, name, prof, points):
        # A hand edited mesh is judgement, not measurement: it cannot be
        # reprobed. Every apply therefore leaves the previous matrix on disk
        # before overwriting it, next to printer.cfg so a restore never depends
        # on this session still being alive.
        folder = os.path.join(
            os.path.dirname(self._config_path()), "kctrl-mesh-backups")
        if not os.path.isdir(folder):
            os.makedirs(folder)
        stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
        path = os.path.join(folder, "%s-%s.json" % (name, stamp))
        payload = {
            "profile": name,
            "saved_at": stamp,
            "mesh_params": dict(prof["mesh_params"]),
            "points": [list(row) for row in points],
        }
        handle = open(path, "w")
        try:
            handle.write(json.dumps(payload, indent=1, sort_keys=True))
        finally:
            handle.close()
        return path

    def cmd_KCTRL_MESH_APPLY(self, gcmd):
        source = gcmd.get("FILE")
        if not os.path.exists(source):
            raise self.gcode.error("K1 Control: no file at %s" % source)
        handle = open(source, "r")
        try:
            payload = json.loads(handle.read())
        except ValueError as exc:
            raise self.gcode.error(
                "K1 Control: %s is not readable JSON (%s)" % (source, exc))
        finally:
            handle.close()

        name = payload.get("profile")
        incoming = payload.get("points")
        if not name or not isinstance(incoming, list):
            raise self.gcode.error(
                "K1 Control: the file must hold a profile name and a points matrix")
        if name in ("default", "None"):
            raise self.gcode.error(
                "K1 Control: the default mesh is not an editable profile")

        bed_mesh = self.printer.lookup_object("bed_mesh", None)
        if bed_mesh is None:
            raise self.gcode.error("K1 Control: no bed_mesh on this printer")
        active = bed_mesh.get_status(None).get("profile_name")
        prof, points = self._live_profile(name)

        if len(incoming) != len(points) or any(
                not isinstance(row, list) or len(row) != len(points[0])
                for row in incoming):
            raise self.gcode.error(
                "K1 Control: the matrix is %s, the profile expects %dx%d"
                % (("%dx%d" % (len(incoming), len(incoming[0])))
                   if incoming and isinstance(incoming[0], list) else "malformed",
                   len(points[0]), len(points)))

        g = self._grid(self._profiles(), name)
        xs = self._axis(g["min_x"], g["max_x"], g["nx"])
        ys = self._axis(g["min_y"], g["max_y"], g["ny"])
        rx, ry = REFERENCE_XY

        changed = 0
        largest = 0.0
        for j, row in enumerate(incoming):
            for i, raw in enumerate(row):
                try:
                    value = float(raw)
                except (TypeError, ValueError):
                    raise self.gcode.error(
                        "K1 Control: X%.0f Y%.0f holds %r, which is not a number"
                        % (xs[i], ys[j], raw))
                if value < -2.0 or value > 2.0:
                    raise self.gcode.error(
                        "K1 Control: X%.0f Y%.0f would reach %+.3f mm, outside "
                        "the -2..2 mm limit" % (xs[i], ys[j], value))
                move = value - points[j][i]
                if abs(move) < 1e-9:
                    continue
                # The profile is zero at the probing point and every print
                # depends on it (ADR-046). Moving it would shift the whole bed
                # under the guise of one point; KCTRL_Z_SAVE is that lever.
                if abs(xs[i] - rx) < 1e-6 and abs(ys[j] - ry) < 1e-6:
                    raise self.gcode.error(
                        "K1 Control: X%.0f Y%.0f is the Z reference and stays "
                        "at zero" % (rx, ry))
                if abs(move) > MAX_EDIT_DELTA:
                    raise self.gcode.error(
                        "K1 Control: X%.0f Y%.0f moves by %+.3f mm, beyond the "
                        "%.2f mm limit of one edit"
                        % (xs[i], ys[j], move, MAX_EDIT_DELTA))
                changed += 1
                largest = max(largest, abs(move))

        if not changed:
            gcmd.respond_info("K1 Control: %s already holds these values, "
                              "nothing written" % name)
            return

        backup = self._backup(name, prof, points)
        self._undo = (name, [list(r) for r in points])
        for j, row in enumerate(incoming):
            for i, raw in enumerate(row):
                points[j][i] = float(raw)
        self._persist(name, prof, points, active)

        flat = [v for row in points for v in row]
        gcmd.respond_info(
            "K1 Control: %s updated, %d point(s) changed, largest move %.3f mm"
            % (name, changed, largest))
        gcmd.respond_info(
            "K1 Control: range %+.4f .. %+.4f mm, zero kept at X%.0f Y%.0f"
            % (min(flat), max(flat), rx, ry))
        gcmd.respond_info(
            "K1 Control: previous matrix saved as %s" % os.path.basename(backup))

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
