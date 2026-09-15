#!/bin/sh
# Lecture seule, sur la machine : trames du bus RS-485 (questions aux CFS et
# reponses) pour silences_cfs.py (document 80). La sortie reste hors du depot.
#   ssh k1max-root 'sh -s' < bus.sh > bus.txt
#   ssh k1max-root 'WIN=128 sh -s' < bus.sh > bus.txt   (plus large, au repos)
#
# Lecture bornee (document 81, meme regle que purges.sh) : fenetre en octets
# depuis la fin du journal, 64 Mo au repos et 3 Mo si une impression tourne,
# basse priorite, lignes coupees avant tout filtre.
L=/usr/data/printer_data/logs/klippy.log
STATE=$(curl 'http://127.0.0.1:7125/printer/objects/query?print_stats=state' 2>/dev/null | sed -n 's/.*"state": *"\([a-z]*\)".*/\1/p')
case "$STATE" in printing|paused) WIN=3 ;; *) WIN=${WIN:-64} ;; esac
SIZE=$(wc -c < "$L" 2>/dev/null || echo 0)
SKIP=$((SIZE / 1048576 - WIN)); [ "$SKIP" -lt 0 ] && SKIP=0
echo "# fenetre ${WIN} Mo (etat ${STATE:-inconnu}), a partir du Mo ${SKIP}"
nice -n 19 dd if="$L" bs=1048576 skip="$SKIP" 2>/dev/null \
  | cut -c1-230 \
  | grep -a -F -e "retries = " -e "Serial_485: got"
