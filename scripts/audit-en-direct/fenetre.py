"""Lignes utiles d'un journal Klipper entre deux heures (HH:MM:SS) : bruit du
bus du CFS et du palpeur retire, repetitions regroupees, temperature de buse
tiree des lignes Stats (une valeur quand elle bouge d'un degre ou quand la
cible change).

Usage : python fenetre.py journal.log 22:33:30 22:36:45 [regex de filtre]
"""
import re
import sys

path, start, end = sys.argv[1], sys.argv[2], sys.argv[3]
extra = re.compile(sys.argv[4]) if len(sys.argv) > 4 else None
REC = re.compile(r"^\[(\w+)\] \d{4}-\d{2}-\d{2} (\d{2}:\d{2}:\d{2}),(\d+) (?:\[[^\]]*\] ){0,2}(.*)$")
NOISE = re.compile(
    r"buf_len = |Serial_485|pending_notifications|Tn_data|get next material temp|max_volumetric"
    r"|get material extrusion|objects/query|Error: no response|method:printer\.|method:server\."
    r"|method:machine\.|method:access\.|webhooks|gcode_store|request_rfid|get_rfid|slave addr|get_box_state"
    r"|check_connect|box_heart|heartbeat|get_version|power_loss|filament_rack|sensor_state_check"
    r"|HEART_PROCESS|cmd\[0x|serial_485|cmd_485|online check|Waiting for response|retries = |_bg_thread"
    r"|^count = |^finish$|response is not null|^0x[0-9A-Fa-f]{2} |^uniid|^addr \d+ acked|timeout = |params: 0x"
    r"|^\*+|response.msg|send_data|recv_data|crc|^Stats|CHeck connect|Resetting prediction|^state: OK"
    r"|^mode = |^data_send: |cmd: GET_BOX_STATE|^msg: 0x|^0x\w+, 0x|\[TRI_|\[PRES_|\[SHOW_WAVE|\[STEP_"
    r"|\[AVGS_|\[GET_STEP_CNTS|^loader check|box heart process not enable|Tn_inner_data\[buffer\]")
EXT = re.compile(r"extruder: target=([\d.]+) temp=([\d.]+)")
last_t = None
last_target = None
prev = None
rep = 0


def out(s):
    global prev, rep
    if prev is not None and s[9:] == prev[9:]:
        rep += 1
        return
    if prev is not None:
        print(prev + (" (x%d)" % (rep + 1) if rep else ""))
    prev = s
    rep = 0


for line in open(path, encoding="utf-8", errors="replace"):
    m = REC.match(line.rstrip("\n"))
    if not m:
        continue
    lvl, hms, ms, msg = m.groups()
    if hms < start or hms > end:
        continue
    if msg.startswith("Stats "):
        x = EXT.search(msg)
        if x:
            target, temp = float(x.group(1)), float(x.group(2))
            if last_t is None or abs(temp - last_t) >= 1.0 or target != last_target:
                out("%s buse %.0f C (cible %.0f)" % (hms, temp, target))
                last_t, last_target = temp, target
        continue
    if NOISE.search(msg):
        continue
    if extra is not None and not extra.search(msg):
        continue
    out("%s %s %s" % (hms, lvl[0], msg[:170]))
if prev is not None:
    print(prev + (" (x%d)" % (rep + 1) if rep else ""))
