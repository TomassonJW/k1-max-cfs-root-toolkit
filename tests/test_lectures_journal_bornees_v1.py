"""Les lectures du journal de la machine sont bornees (document 81).

Le 15 septembre 2026 a 12:19:44, un `tail -n 600000 klippy.log | grep` lance
depuis le PC a fait tomber la memoire disponible de la K1 Max de 94,5 a 9,8 Mo.
Le journal s'est tu neuf secondes, la buse a ete lue a 0 C, et Klipper s'est
arrete en pleine fin d'impression. Un `tail -n` relit le fichier depuis la fin
en memoire ; sur un journal de 500 Mo, c'est la machine qui tombe.

Regle, pour tout script du depot qui lit klippy.log sur la machine :

- le journal n'est ouvert que par `dd if=... bs=1048576 skip=N` (fenetre en
  octets depuis la fin), `wc -c` (sa taille), `stat`, ou `tail -n 0 -F`
  (suivi sans relecture) ; jamais par `tail -n N`, `grep`, `cat`, `awk`, `sed`
  sur le fichier lui-meme ;
- chaque `dd` tourne sous `nice -n 19` ;
- la fenetre est reduite quand une impression tourne (`printing|paused`) ;
- avant tout `tail -n N`, les lignes sont coupees (`cut -c1-W`) et N x W ne
  depasse pas 4 Mo.
"""

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOG = "klippy.log"
SEARCH_DIRS = ("scripts", "packages")
EXTENSIONS = {".sh", ".ps1", ".py"}
MAX_TAIL_BYTES = 4 * 1024 * 1024
WINDOW_SCRIPTS = (
    ROOT / "scripts" / "run-k1-control-cfs-read-only-audit-v1.ps1",
    ROOT / "packages" / "k1-control-v1" / "clean-and-reference-v1"
    / "capture_recent_cfs_history_read_only.ps1",
    ROOT / "scripts" / "audit-en-direct" / "purges.sh",
    ROOT / "scripts" / "audit-en-direct" / "bus.sh",
)

ALLOWED = (
    # une affectation : L=/usr/.../klippy.log, LOG_PATH = "/usr/.../klippy.log"
    re.compile(r"""^\s*\$?\w+\s*=\s*["']?/?[\w./-]*klippy\.log["']?\s*$"""),
    re.compile(r"\bwc -c\b"),
    re.compile(r"\bstat -c\b"),
    re.compile(r"\btail -n 0 -F\b"),
    re.compile(r"\bdd if=\S*klippy\.log"),
)
DD = re.compile(r"\bdd if=")
TAIL_N = re.compile(r"\btail -n (\d+)\b")
CUT_W = re.compile(r"\bcut -c1-(\d+)\b")


def readers():
    found = []
    for base in SEARCH_DIRS:
        for path in sorted((ROOT / base).rglob("*")):
            if path.suffix in EXTENSIONS and path.is_file():
                text = path.read_text(encoding="utf-8", errors="replace")
                if LOG in text:
                    found.append((path, text))
    return found


def statements(text):
    """Lignes du script, les continuations (antislash final) recollees."""
    out = []
    buf = ""
    for raw in text.splitlines():
        line = raw.rstrip()
        buf = (buf + " " + line.strip()) if buf else line
        if buf.endswith("\\"):
            buf = buf[:-1]
            continue
        out.append(buf)
        buf = ""
    if buf:
        out.append(buf)
    return out


def is_comment(statement):
    return statement.strip().startswith("#")


class LecturesJournalBorneesTests(unittest.TestCase):
    def test_les_scripts_a_fenetre_sont_presents(self) -> None:
        for path in WINDOW_SCRIPTS:
            self.assertTrue(path.is_file(), path)
            self.assertIn("dd if=", path.read_text(encoding="utf-8"), path)

    def test_le_journal_n_est_ouvert_que_par_une_fenetre(self) -> None:
        for path, text in readers():
            for statement in statements(text):
                if LOG not in statement or is_comment(statement):
                    continue
                self.assertTrue(
                    any(rule.search(statement) for rule in ALLOWED),
                    "%s ouvre klippy.log sans fenetre : %s" % (path.relative_to(ROOT), statement.strip()[:160]))

    def test_chaque_fenetre_est_en_basse_priorite_et_en_octets(self) -> None:
        for path, text in readers():
            for statement in statements(text):
                if not DD.search(statement) or is_comment(statement):
                    continue
                where = "%s : %s" % (path.relative_to(ROOT), statement.strip()[:160])
                self.assertIn("nice -n 19", statement, where)
                self.assertIn("bs=1048576", statement, where)
                self.assertIn("skip=", statement, where)

    def test_la_fenetre_se_reduit_pendant_une_impression(self) -> None:
        for path, text in readers():
            if "dd if=" in text:
                self.assertIn("printing|paused", text, path.relative_to(ROOT))

    def test_tout_tail_n_est_precede_d_une_coupe_et_pese_moins_de_4_mo(self) -> None:
        for path, text in readers():
            for statement in statements(text):
                if is_comment(statement) or ("dd if=" not in statement and LOG not in statement):
                    continue
                tail = TAIL_N.search(statement)
                if not tail or int(tail.group(1)) == 0:
                    continue
                where = "%s : %s" % (path.relative_to(ROOT), statement.strip()[:160])
                cut = CUT_W.search(statement)
                self.assertIsNotNone(cut, "tail -n sans cut -c1-W, " + where)
                self.assertLess(cut.start(), tail.start(), "le cut vient apres le tail, " + where)
                self.assertLessEqual(
                    int(tail.group(1)) * int(cut.group(1)), MAX_TAIL_BYTES,
                    "tail -n %s x %s caracteres depasse 4 Mo, %s" % (tail.group(1), cut.group(1), where))

    def test_le_suivi_en_direct_ne_relit_rien(self) -> None:
        text = (ROOT / "scripts" / "audit-en-direct" / "audit-live.sh").read_text(encoding="utf-8")
        self.assertIn("tail -n 0 -F", text)

    def test_les_regles_reconnaissent_un_tail_n_direct(self) -> None:
        # Le script qui a fait planter Klipper le 15 septembre, tel quel.
        bad = "tail -n 600000 /usr/data/printer_data/logs/klippy.log | grep -E 'BOX_'"
        self.assertFalse(any(rule.search(bad) for rule in ALLOWED))
        good = 'nice -n 19 dd if="$L" bs=1048576 skip="$SKIP" 2>/dev/null | cut -c1-600 | tail -n 5000'
        self.assertIn("nice -n 19", good)
        tail, cut = TAIL_N.search(good), CUT_W.search(good)
        self.assertLessEqual(int(tail.group(1)) * int(cut.group(1)), MAX_TAIL_BYTES)


if __name__ == "__main__":
    unittest.main()
