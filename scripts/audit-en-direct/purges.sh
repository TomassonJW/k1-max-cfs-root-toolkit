#!/bin/sh
# Lecture seule, sur la machine : pour chaque chargement du journal courant,
# longueur de purge demandee par le fichier, troncons reellement pousses, roue
# de mesure du CFS, relances. Environ une minute sur un journal de 500 Mo.
#   ssh k1max-root 'sh -s' < purges.sh
L=/usr/data/printer_data/logs/klippy.log
grep -E "flush_volume: |length: \[|current_measuring_wheel|cmd_T flush_count|material_change_flush\(.*\)$|auto_retry_process|buffer is always full|cmd_T vtnn=" "$L" \
  | sed -E 's/^\[[A-Z]+\] [0-9-]+ ([0-9:]+),[0-9]+ \[root\] \[[^]]*\] /\1 /' \
  | sed -E 's/last_measuring_wheel = [-0-9.]+, current_measuring_wheel = [-0-9.]+, //' \
  | cut -c1-150
