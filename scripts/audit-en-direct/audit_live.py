"""Audit en direct d'une impression (document 79, section 7).

Lit le journal Klipper sur l'entree standard (ssh ... tail -F), en garde une
copie complete, prend des images de la webcam, resume chaque changement de
couleur sur une ligne et signale tout de suite les anomalies. Chaque ligne de
sortie devient une notification : la sortie reste courte. Horloge : celle du
journal, pour que le rejeu d'un extrait donne les memes resultats qu'en direct.

Lecture seule : n'envoie rien a l'imprimante.

Variables d'environnement :
  AUDIT_OUT     dossier de sortie (defaut : ./audit du dossier courant)
  AUDIT_CAM     URL d'image de la webcam ; sans elle, aucune image
                (audit-live.sh la deduit de l'alias ssh)

Rejeu : AUDIT_OUT=rejeu python audit_live.py < extrait.log
"""
import os
import re
import sys
import threading
import time
import urllib.request

OUT = os.environ.get("AUDIT_OUT") or os.path.join(os.getcwd(), "audit")
IMG = os.path.join(OUT, "img")
os.makedirs(IMG, exist_ok=True)
CAM = os.environ.get("AUDIT_CAM")

sys.stdin.reconfigure(encoding="utf-8", errors="replace")
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

REC = re.compile(r"^\[(\w+)\] \d{4}-\d{2}-\d{2} (\d{2}):(\d{2}):(\d{2}),\d+ (?:\[[^\]]*\] ){0,2}(.*)$")
T_BEGIN = re.compile(r"K1 Control: (T\d+) -> filament (\d+) \(([^)]*)\) sur (T\d[A-D]), ([^,]*)")
T_DONE = re.compile(r"K1 Control: (T\d+) fait, filament a la tete")
CMD_T = re.compile(r"cmd_T vtnn=(\w+)")
CODE = re.compile(r'"code":"(key\d+)"(?:, "msg":"([^"]*)")?')
RETRY = re.compile(r"auto_retry_process: (\w+), (auto_retry_\w+)")
URGENT = re.compile(
    r"do_after_pause|printing to pause|runout event|alarm not re-armed"
    r"|K1 Control \[|le firmware a mis|termine sans filament|Exiting SD card print"
    r"|Starting SD card print|K1 Control start:|ligne d.amorce|CFS attempt"
    r"|Starting Klippy|Transition to shutdown|[Ss]hutdown|Internal error"
    r"|Lost communication|Timer too close|purge manuelle|method:pause_resume/"
    r"|'script': '(?:PAUSE|RESUME|CANCEL_PRINT)")

journal = open(os.path.join(OUT, "journal.log"), "a", encoding="utf-8", errors="replace")
tsv_path = os.path.join(OUT, "changements.tsv")
new_tsv = not os.path.exists(tsv_path)
tsv = open(tsv_path, "a", encoding="utf-8")
if new_tsv:
    tsv.write("debut\tfin\tduree_s\tT\tfilament\templacement\tbobine\tcmd_T\trelances\tcodes\tpauses\talarme_off\talarme_on\tissue\n")
    tsv.flush()

recent = {}
window = []
suppressed = 0
current = None
in_start = False
day = 0
last_sec = None
now = 0
totals = {"changes": 0, "retries": 0, "codes": [], "pauses": 0}


def snap(label, delays):
    if not CAM:
        return

    def run():
        t0 = time.time()
        for d in delays:
            wait = t0 + d - time.time()
            if wait > 0:
                time.sleep(wait)
            name = "%s-%s.jpg" % (time.strftime("%H%M%S"), label)
            try:
                data = urllib.request.urlopen(CAM, timeout=8).read()
                with open(os.path.join(IMG, name), "wb") as f:
                    f.write(data)
            except Exception:
                pass
    threading.Thread(target=run, daemon=True).start()


def notify(text, key=None, every=0):
    global suppressed
    if key is not None:
        last = recent.get(key)
        if last is not None and now - last < every:
            return
        recent[key] = now
    while window and now - window[0] > 60:
        window.pop(0)
    if len(window) >= 15:
        suppressed += 1
        return
    if suppressed:
        print("(%d evenements non notifies, voir journal.log)" % suppressed)
        suppressed = 0
    window.append(now)
    print(text[:240])
    journal.flush()


def close_change(hms, issue, end=None):
    global current
    c = current
    current = None
    if c is None:
        return
    dur = int((now if end is None else end) - c["t0"])
    totals["retries"] += c["retries"]
    totals["pauses"] += c["pauses"]
    for k in c["codes"]:
        if k not in totals["codes"]:
            totals["codes"].append(k)
    row = [c["start"], hms, str(dur), c["name"], c["logical"], c["slot"], c["spool"], c["cmd_t"],
           str(c["retries"]), ",".join(c["codes"]) or "-", str(c["pauses"]),
           "oui" if c["off"] else "non", "oui" if c["on"] else "non", issue]
    tsv.write("\t".join(row) + "\n")
    tsv.flush()
    odd = []
    if c["retries"]:
        odd.append("relances " + ",".join(c["retry_kinds"]))
    if c["codes"]:
        odd.append("codes " + ",".join(c["codes"]))
    if c["pauses"]:
        odd.append("PAUSE x%d" % c["pauses"])
    if not c["start_kind"] and not (c["off"] and c["on"]):
        odd.append("alarme off=%s on=%s" % (c["off"], c["on"]))
    notify("%s %s%s -> %s (%s) : %d s, %s, %s" % (
        c["start"], "depart " if c["start_kind"] else "", c["name"], c["slot"], c["spool"], dur, issue,
        "; ".join(odd) if odd else "sans relance ni code"))


notify("audit en direct : flux ouvert a " + time.strftime("%H:%M:%S"))
count = 0
for raw in sys.stdin:
    line = raw.rstrip("\r\n")
    journal.write(line + "\n")
    count += 1
    if count % 200 == 0:
        journal.flush()
    m = REC.match(line)
    if not m:
        if "Traceback" in line:
            notify("Traceback dans le journal, voir journal.log", "tb", 30)
        continue
    level, hh, mm, ss, msg = m.groups()
    hms = "%s:%s:%s" % (hh, mm, ss)
    sec = int(hh) * 3600 + int(mm) * 60 + int(ss)
    if last_sec is not None and sec < last_sec - 43200:
        day += 86400
    last_sec = sec
    now = day + sec

    b = T_BEGIN.search(msg)
    if b:
        if current is not None and current.get("done_at") is not None:
            close_change(current["done_hms"], "fait", current["done_at"])
        elif current is not None:
            close_change(hms, "coupe par le changement suivant")
        totals["changes"] += 0 if in_start else 1
        current = {"name": b.group(1), "logical": b.group(3), "slot": b.group(4),
                   "spool": b.group(5).strip(), "start": hms, "t0": now, "cmd_t": "-",
                   "retries": 0, "retry_kinds": [], "codes": [], "pauses": 0, "last_pause": -99,
                   "off": False, "on": False, "start_kind": in_start}
        snap("%s-%s" % (b.group(1), b.group(4)), [0, 15, 40, 70, 100, 140, 190, 250])
        continue

    if current is not None:
        x = CMD_T.search(msg)
        if x:
            current["cmd_t"] = x.group(1)
        x = CODE.search(msg)
        if x and x.group(1) not in current["codes"]:
            current["codes"].append(x.group(1))
        x = RETRY.search(msg)
        if x:
            current["retries"] += 1
            current["retry_kinds"].append(x.group(2).replace("auto_retry_", ""))
        if "do_after_pause" in msg and now - current["last_pause"] > 5:
            current["pauses"] += 1
            current["last_pause"] = now
        if "runout alarm off during" in msg:
            current["off"] = True
        if "runout alarm on again after" in msg:
            current["on"] = True
        if T_DONE.search(msg):
            # The alarm comes back after "fait" (rearm_runout waits for M400).
            current["done_at"] = now
            current["done_hms"] = hms
            if not current["off"]:
                close_change(hms, "fait", now)
            continue
        if current.get("done_at") is not None and (current["on"] or now - current["done_at"] > 20):
            close_change(current["done_hms"], "fait", current["done_at"])

    if "K1 Control start:" in msg:
        in_start = True
        snap("depart", [0, 60, 120, 180, 240, 300, 360, 420, 480])
    elif "ligne d'amorce" in msg:
        snap("amorce", [0, 10, 25])
    elif "do_after_pause" in msg:
        snap("pause", [0, 30])
    elif RETRY.search(msg):
        snap("relance", [0, 10, 25])
    elif "Exiting SD card print" in msg:
        snap("fin", [0, 60])

    c = CODE.search(msg)
    r = RETRY.search(msg)
    u = URGENT.search(msg)
    if c:
        notify("%s %s %s" % (hms, c.group(1), c.group(2) or msg), c.group(1), 120)
    elif r:
        notify("%s relance Creality %s sur %s" % (hms, r.group(2), r.group(1)), r.group(2), 30)
    elif u:
        notify("%s %s" % (hms, msg), u.group(0), 30)

    if current is not None:
        if "le firmware a mis" in msg:
            close_change(hms, "PAUSE du firmware")
        elif "termine sans filament" in msg:
            close_change(hms, "SANS FILAMENT, pause")
        elif current["start_kind"] and "ligne d'amorce" in msg:
            close_change(hms, "depart jusqu'a la ligne d'amorce")
        elif "K1 Control [" in msg:
            close_change(hms, "DEPART ARRETE")
        elif "Exiting SD card print" in msg:
            close_change(hms, "fin d'impression pendant le changement")
    if "ligne d'amorce" in msg or "K1 Control [" in msg or "Exiting SD card print" in msg:
        in_start = False
    if "Exiting SD card print" in msg:
        notify("%s bilan : %d changement(s), %d relance(s) Creality, codes %s, %d pause(s) ; detail dans changements.tsv" % (
            hms, totals["changes"], totals["retries"], ",".join(totals["codes"]) or "aucun", totals["pauses"]))
        totals = {"changes": 0, "retries": 0, "codes": [], "pauses": 0}

journal.flush()
notify("audit en direct : flux ferme a " + time.strftime("%H:%M:%S"))
