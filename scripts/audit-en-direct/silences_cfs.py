"""Silences d'un CFS sur le bus : pour chaque question envoyee a un CFS, la
trame qui l'a precedee sur le fil, l'ecart entre les deux, et si le CFS a
repondu. Sert a verifier la cause des pauses key831 (document 80), avant et
apres un correctif.

Extraction sur la machine, en lecture seule et en basse priorite, depuis un
dossier hors du depot (le journal extrait n'entre jamais dans le depot) :

  ssh k1max-root 'cd /usr/data/printer_data/logs && nice -n 19 grep -F
    -e "retries = " -e "Serial_485: got" klippy.log | cut -c1-230' > bus.txt

Usage : python silences_cfs.py bus.txt [--addr=2] [--cmd=0a] [--detail]
  --addr   adresse du CFS questionne (2 par defaut)
  --cmd    commande questionnee, en hexadecimal (0a = etat du CFS, par defaut)
  --detail liste chaque silence
"""
import ast
import re
import sys
from collections import Counter
from datetime import datetime

REC = re.compile(r"^\[\w+\] (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d{3}) ")
TX = re.compile(r"retries = \d+, cmd = ((?:0x[0-9a-f]+ ?)+)")
RX = re.compile(r"Serial_485: got \{'#msgid': \d+, '#msg': (b'(?:[^'\\]|\\.)*'|b\"(?:[^\"\\]|\\.)*\")")
HEAD = 0xF7
GAPS = (10, 30, 60, 100, 300, 1000)


def crc8(data):
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


def read(path):
    events = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = REC.match(line)
            if not m:
                continue
            t = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S,%f")
            tx = TX.search(line)
            if tx and "get response" not in line:
                events.append((t, "tx", bytes(int(v, 16) for v in tx.group(1).split())))
                continue
            rx = RX.search(line)
            if rx:
                try:
                    events.append((t, "rx", ast.literal_eval(rx.group(1))))
                except (SyntaxError, ValueError):
                    pass
    return events


def gap_label(ms):
    for limit in GAPS:
        if ms < limit:
            return "< %4d ms" % limit
    return ">= 1 s   "


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    addr, cmd = 2, 0x0A
    for a in sys.argv[1:]:
        if a.startswith("--addr="):
            addr = int(a.split("=", 1)[1])
        elif a.startswith("--cmd="):
            cmd = int(a.split("=", 1)[1], 16)
    detail = "--detail" in sys.argv
    events = read(args[0])

    bad_crc = 0
    f7_frames = Counter()
    for _, kind, raw in events:
        if kind == "rx" and len(raw) > 5:
            if crc8(raw[2:-1]) != raw[-1]:
                bad_crc += 1
            elif raw[-1] == HEAD:
                f7_frames["CFS %d, commande %02x, reponse %s" % (raw[1], raw[4], raw[5:-1].hex(" "))] += 1

    table = Counter()
    per_hour = Counter()
    for i, (t, kind, raw) in enumerate(events):
        if kind != "tx" or len(raw) < 4 or raw[0] != addr or raw[3] != cmd or i == 0:
            continue
        prev_t, prev_kind, prev_raw = events[i - 1]
        gap = (t - prev_t).total_seconds() * 1000
        after_f7 = prev_kind == "rx" and len(prev_raw) > 5 and prev_raw[-1] == HEAD
        answered = False
        for t2, kind2, raw2 in events[i + 1:]:
            if (t2 - t).total_seconds() > 1.1:
                break
            if kind2 == "rx" and len(raw2) > 4 and raw2[1] == addr and raw2[4] == cmd:
                answered = True
                break
        table[(after_f7, gap_label(gap), answered)] += 1
        if not answered:
            per_hour[(t.strftime("%Y-%m-%d %H h"), after_f7 and gap < 300)] += 1
            if detail:
                if prev_kind == "rx":
                    what = "reponse CFS %d cmd %02x finie par %02x" % (prev_raw[1], prev_raw[4], prev_raw[-1])
                else:
                    what = "question " + prev_raw.hex(" ")
                print("%s silence, %4d ms apres : %s" % (t.strftime("%H:%M:%S.%f")[:-3], gap, what))

    print("Questions au CFS %d (commande %02x), selon la trame precedente et l'ecart :" % (addr, cmd))
    print("  %-38s %-10s %8s %8s" % ("trame precedente", "ecart", "repond", "muet"))
    for after_f7 in (True, False):
        for label in ["< %4d ms" % g for g in GAPS] + [">= 1 s   "]:
            ok = table[(after_f7, label, True)]
            ko = table[(after_f7, label, False)]
            if ok or ko:
                name = "reponse d'un CFS finie par F7" if after_f7 else "autre"
                print("  %-38s %-10s %8d %8d" % (name, label, ok, ko))
    print("Silences par heure (dont apres une trame finie par F7, a moins de 300 ms) :")
    for hour in sorted({h for h, _ in per_hour}):
        print("  %s : %d (%d)" % (hour, per_hour[(hour, True)] + per_hour[(hour, False)], per_hour[(hour, True)]))
    print("Reponses finies par F7, par contenu :")
    for name, n in f7_frames.most_common():
        print("  %s : %d" % (name, n))
    print("Reponses au CRC faux : %d" % bad_crc)


if __name__ == "__main__":
    main()
