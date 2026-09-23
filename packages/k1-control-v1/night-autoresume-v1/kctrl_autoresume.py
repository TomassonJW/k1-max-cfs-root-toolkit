#!/usr/bin/env python3
# K1 Control - reprise automatique bornee d'une impression en pause.
# Processus externe a Klipper : aucun module, aucun restart, aucune macro
# touchee. Il fait ce que Thomas fait a l'ecran (RESUME) quand un changement
# de filament rate met l'impression en pause, au plus MAX_ATTEMPTS fois.
import json
import os
import socket
import sys
import time

SOCK = "/tmp/klippy_uds"
LOG = "/tmp/kctrl_autoresume.log"
STOP = "/tmp/kctrl_autoresume.stop"
MAX_ATTEMPTS = 15
PAUSE_STABLE_S = 60      # pause stable, G-code libre, avant d'agir
MIN_GAP_S = 150          # ecart minimal entre deux tentatives
MIN_PRINT_S = 300        # jamais pendant la sequence de depart
POLL_S = 10
WAIT_START_S = 3 * 3600  # attente maximale du debut d'impression

OBJECTS = {
    "print_stats": ["state", "print_duration", "filename", "message"],
    "idle_timeout": ["state"],
    "toolhead": ["homed_axes"],
    "webhooks": ["state"],
    "extruder": ["temperature", "target"],
    "box": ["state", "t_command"],
}


def log(msg):
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n"
    try:
        if os.path.exists(LOG) and os.path.getsize(LOG) > 512 * 1024:
            os.replace(LOG, LOG + ".1")
        with open(LOG, "a") as f:
            f.write(line)
    except Exception:
        pass


def call(method, params, timeout=10.0):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(SOCK)
        s.sendall(json.dumps({"id": 1, "method": method,
                              "params": params}).encode() + b"\x03")
        buf = b""
        while b"\x03" not in buf:
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
        return json.loads(buf.split(b"\x03", 1)[0].decode())
    finally:
        s.close()


def status():
    return call("objects/query", {"objects": OBJECTS})["result"]["status"]


def may_resume(st, ready_since, now, last_attempt, attempts):
    ps = st.get("print_stats", {})
    return (ps.get("state") == "paused"
            and st.get("idle_timeout", {}).get("state") == "Ready"
            and st.get("toolhead", {}).get("homed_axes") == "xyz"
            and float(ps.get("print_duration") or 0) >= MIN_PRINT_S
            and ready_since is not None
            and now - ready_since >= PAUSE_STABLE_S
            and now - last_attempt >= MIN_GAP_S
            and attempts < MAX_ATTEMPTS)


def main():
    if "--once" in sys.argv:
        print(json.dumps(status()))
        return
    armed = "--arm" in sys.argv
    log("start armed=%s pid=%d" % (armed, os.getpid()))
    t0 = time.time()
    seen = False
    attempts = 0
    last_attempt = 0.0
    ready_since = None
    paused_logged = False
    errors = 0
    while True:
        if os.path.exists(STOP):
            log("exit stop_file")
            return
        try:
            st = status()
            errors = 0
        except Exception as e:
            errors += 1
            log("query_error %r" % (e,))
            if errors > 60:
                log("exit too_many_errors")
                return
            time.sleep(POLL_S)
            continue
        now = time.time()
        ps = st.get("print_stats", {})
        state = ps.get("state")
        if st.get("webhooks", {}).get("state") not in (None, "ready"):
            log("exit klipper_not_ready %r" % (st.get("webhooks"),))
            return
        if state in ("printing", "paused"):
            if not seen:
                log("print_seen file=%r" % (ps.get("filename"),))
            seen = True
        elif seen:
            log("exit print_state=%s attempts=%d" % (state, attempts))
            return
        elif now - t0 > WAIT_START_S:
            log("exit no_print_started")
            return
        if state != "paused":
            if paused_logged:
                log("running_again state=%s" % state)
            paused_logged = False
            ready_since = None
            time.sleep(POLL_S)
            continue
        idle = st.get("idle_timeout", {}).get("state")
        if not paused_logged:
            paused_logged = True
            log("pause_seen dur=%.0f msg=%r idle=%s homed=%r extr=%r box=%r"
                % (float(ps.get("print_duration") or 0), ps.get("message"),
                   idle, st.get("toolhead", {}).get("homed_axes"),
                   st.get("extruder"), st.get("box")))
        if idle == "Ready":
            if ready_since is None:
                ready_since = now
        else:
            ready_since = None
        if attempts >= MAX_ATTEMPTS:
            log("exit max_attempts_reached")
            return
        if may_resume(st, ready_since, now, last_attempt, attempts):
            attempts += 1
            last_attempt = now
            ready_since = None
            paused_logged = False
            log("resume_attempt %d/%d" % (attempts, MAX_ATTEMPTS))
            if armed:
                try:
                    r = call("gcode/script", {"script": "RESUME"}, timeout=900)
                    log("resume_reply %r" % (r,))
                except Exception as e:
                    log("resume_call_error %r" % (e,))
            else:
                log("dry_run_no_command")
        time.sleep(POLL_S)


if __name__ == "__main__":
    main()
