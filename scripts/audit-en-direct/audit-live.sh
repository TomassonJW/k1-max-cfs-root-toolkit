#!/bin/bash
# Sur le PC (Git Bash), pas sur la machine. Suit klippy.log de la machine et le
# passe a audit_live.py ; se reconnecte si le flux coupe. Lecture seule. A lancer
# depuis un dossier hors du depot : les sorties (journal complet, images) vont
# dans ./audit (ou $AUDIT_OUT) et ne se versionnent pas.
#   PYTHON  interpreteur (defaut : py -3.10)
#   HOST    alias ssh de la machine (defaut : k1max-root)
HERE="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${PYTHON:-py -3.10}"
HOST="${HOST:-k1max-root}"
OUT="${AUDIT_OUT:-$PWD/audit}"
mkdir -p "$OUT"
export AUDIT_OUT="$OUT"
if [ -z "$AUDIT_CAM" ]; then
  addr="$(ssh -G "$HOST" 2>/dev/null | awk '$1 == "hostname" { print $2; exit }')"
  [ -n "$addr" ] && export AUDIT_CAM="http://$addr:8080/?action=snapshot"
fi
fails=0
while true; do
  t0=$(date +%s)
  ssh -o ConnectTimeout=15 -o ServerAliveInterval=30 -o ServerAliveCountMax=6 "$HOST" \
    "tail -n 0 -F /usr/data/printer_data/logs/klippy.log" 2>>"$OUT/ssh-err.log" \
    | $PYTHON -u "$HERE/audit_live.py"
  if [ $(( $(date +%s) - t0 )) -gt 60 ]; then fails=0; else fails=$((fails + 1)); fi
  if [ $fails -le 1 ] || [ $((fails % 10)) -eq 0 ]; then
    echo "$(date +%H:%M:%S) flux du journal coupe (echecs de suite : $fails) : $(tail -n 1 "$OUT/ssh-err.log" 2>/dev/null | cut -c1-120)"
  fi
  sleep $(( fails > 3 ? 60 : 10 ))
done
