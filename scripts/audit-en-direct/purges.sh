#!/bin/sh
# Lecture seule, sur la machine : pour chaque chargement de la fenetre lue,
# longueur de purge demandee par le fichier, troncons reellement pousses, roue
# de mesure du CFS, relances.
#   ssh k1max-root 'sh -s' < purges.sh
#   ssh k1max-root 'WIN=96 sh -s' < purges.sh    (fenetre plus large, au repos)
#
# Lecture bornee (document 81 : le 15 septembre 2026, un tail -n sur klippy.log
# a fait planter Klipper en pleine fin d'impression) : fenetre en octets depuis
# la fin du journal, 32 Mo au repos et 3 Mo si une impression tourne, basse
# priorite, lignes coupees avant tout filtre. 32 Mo couvrent environ deux
# heures d'impression. tests/test_lectures_journal_bornees_v1.py l'impose.
L=/usr/data/printer_data/logs/klippy.log
STATE=$(curl 'http://127.0.0.1:7125/printer/objects/query?print_stats=state' 2>/dev/null | sed -n 's/.*"state": *"\([a-z]*\)".*/\1/p')
case "$STATE" in printing|paused) WIN=3 ;; *) WIN=${WIN:-32} ;; esac
SIZE=$(wc -c < "$L" 2>/dev/null || echo 0)
SKIP=$((SIZE / 1048576 - WIN)); [ "$SKIP" -lt 0 ] && SKIP=0
echo "# fenetre ${WIN} Mo (etat ${STATE:-inconnu}), a partir du Mo ${SKIP}"
nice -n 19 dd if="$L" bs=1048576 skip="$SKIP" 2>/dev/null \
  | cut -c1-600 \
  | grep -a -E "flush_volume: |length: \[|current_measuring_wheel|cmd_T flush_count|material_change_flush\(.*\)$|auto_retry_process|buffer is always full|cmd_T vtnn=" \
  | sed -E 's/^\[[A-Z]+\] [0-9-]+ ([0-9:]+),[0-9]+ \[root\] \[[^]]*\] /\1 /' \
  | sed -E 's/last_measuring_wheel = [-0-9.]+, current_measuring_wheel = [-0-9.]+, //' \
  | cut -c1-150
