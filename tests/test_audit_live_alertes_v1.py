"""Alertes de fin d'impression et de sante de Klipper dans l'audit en direct
(document 81).

Le 15 septembre 2026 a 12:03, la fin de l'impression prend dans le module CFS
la branche « extrude all material, last_cmd: T1A » : 80 mm pousses toutes les
40 s, « filament_sensor true » a chaque tour, 25 tours, deux metres, sans que
l'audit ne dise rien. La Pause demandee a 12:19:07 n'est pas appliquee. A
12:19:44 une lecture du journal depuis le PC prend la memoire (94,5 -> 9,8 Mo),
le journal se tait neuf secondes, Klipper s'arrete. La fin normale du 14
septembre va de box_end (22:53:32) a Exiting (22:54:21) en 49 s.

L'audit est rejoue ici sur des lignes synthetiques, en sous-processus, comme
en direct : les memes lignes donnent les memes alertes.
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit-en-direct" / "audit_live.py"


def line(hms, msg, level="INFO", where="gcode:<lambda>:144"):
    return "[%s] 2026-09-15 %s,000 [root] [%s] %s" % (level, hms, where, msg)


def stats(hms, memavail_kb):
    return line(hms, "Stats 286339.9: gcodein=0  mcu: mcu_awake=0.013 sysload=0.62 "
                "cputime=1234.5 memavail=%d print_time=1.0" % memavail_kb,
                where="statistics_ext:generate_stats:68")


def run(lines):
    with tempfile.TemporaryDirectory() as out:
        env = dict(os.environ, AUDIT_OUT=out, PYTHONIOENCODING="utf-8")
        env.pop("AUDIT_CAM", None)
        done = subprocess.run(
            [sys.executable, str(SCRIPT)], input="\n".join(lines) + "\n",
            capture_output=True, text=True, encoding="utf-8", env=env, cwd=out, timeout=120)
    if done.returncode != 0:
        raise AssertionError(done.stderr)
    return done.stdout


LOOP = [
    line("12:03:16", "box_end"),
    line("12:03:20", "extrude all material, last_cmd: T1A"),
    line("12:04:05", "filament_sensor true"),
    line("12:04:45", "filament_sensor true"),
    line("12:05:25", "filament_sensor true"),
    line("12:05:30", "webhooks: method:pause_resume/pause,received {},id:1927713648",
         where="webhooks:_process_request:260"),
    stats("12:05:31", 94000),
    stats("12:05:41", 9800),
    line("12:06:40", "Exiting SD card print", where="virtual_sdcard:work_handler:200"),
]

NORMAL = [
    line("22:53:32", "box_end"),
    line("22:54:05", "filament_sensor false"),
    stats("22:54:19", 94000),
    stats("22:54:20", 94000),
    line("22:54:21", "Exiting SD card print", where="virtual_sdcard:work_handler:200"),
]


class AuditLiveAlertesTests(unittest.TestCase):
    def test_la_boucle_de_fin_est_signalee_des_la_branche_puis_par_troncons(self) -> None:
        out = run(LOOP)
        self.assertIn("12:03:16 fin d'impression : box_end", out)
        self.assertIn("12:03:20 ALERTE fin d'impression : extrude all material sur T1A", out)
        self.assertIn("12:04:05 ALERTE boucle de fin : troncon numero 1, environ 80 mm de T1A", out)
        self.assertIn("12:04:45 ALERTE boucle de fin : troncon numero 2, environ 160 mm", out)
        self.assertNotIn("troncon numero 3", out)
        self.assertIn("12:06:40 box_end -> Exiting en 204 s, 3 troncon(s) pousse(s), branche extrude all material", out)

    def test_la_pause_pendant_la_fin_est_dite_sans_effet(self) -> None:
        out = run(LOOP)
        self.assertIn("12:05:30 Pause demandee pendant box_end : sans effet", out)

    def test_une_fin_trop_longue_est_signalee(self) -> None:
        out = run(LOOP)
        self.assertIn("ALERTE box_end dure depuis", out)

    def test_la_memoire_basse_et_le_journal_muet_sont_signales(self) -> None:
        out = run(LOOP)
        self.assertIn("12:05:41 ALERTE memoire disponible 9 Mo, sous 40 Mo", out)
        self.assertIn("12:05:41 ALERTE journal muet 10 s pendant les Stats", out)

    def test_une_fin_normale_ne_declenche_rien(self) -> None:
        out = run(NORMAL)
        self.assertNotIn("ALERTE", out)
        self.assertIn("22:54:21 box_end -> Exiting en 49 s, 0 troncon(s) pousse(s)", out)

    def test_un_trou_sans_stats_avant_n_est_pas_un_silence(self) -> None:
        # Machine au repos : aucune Stats, des minutes sans rien, pas d'alerte.
        out = run([line("10:00:00", "cmd: GET_FILAMENT_SENSOR_STATE", where="reactor:invoke:48"),
                   line("10:05:00", "cmd: GET_FILAMENT_SENSOR_STATE", where="reactor:invoke:48")])
        self.assertNotIn("journal muet", out)

    def test_filament_useup_a_zero_est_signale_avec_son_hypothese(self) -> None:
        out = run([line("03:45:58", "Tn_data[filament_useup]: 0", where="reactor:invoke:48"),
                   line("12:18:00", "Tn_data[filament_useup]: 1", where="reactor:invoke:48")])
        self.assertIn("03:45:58 CFS : filament_useup passe a 0 ; hypothese du 15 septembre", out)
        self.assertIn("12:18:00 CFS : filament_useup passe a 1", out)
        self.assertNotIn("12:18:00 CFS : filament_useup passe a 1 ;", out)


if __name__ == "__main__":
    unittest.main()
