# 100 — Reprise automatique de nuit (ADR-073)

## Ce qui est en service

`packages/k1-control-v1/night-autoresume-v1/kctrl_autoresume.py`, copié dans
`/tmp/kctrl_autoresume.py` de la K1 et lancé le 24 septembre 2026 à 01:01
(horloge K1) avec `--arm`, sous `nohup nice`. Imprimante au repos au lancement ;
aucun restart, aucun fichier Klipper modifié.

Preuves :

- compilation locale et sur la K1 (Python 3.8) ;
- lecture réelle unique : `standby`, Klipper `ready`, CFS `connect` ;
- `tests/test_night_autoresume.py` : 6/6 (règles, une seule reprise après pause
  stable, rien pendant G-code occupé ou moteurs coupés, 15 au plus, mode sec,
  arrêt sur shutdown et fichier d'arrêt) ;
- processus vivant après fermeture de la session SSH.

## Lire le résultat le matin

```sh
ssh k1max-root 'tail -c 4000 /tmp/kctrl_autoresume.log'
```

`pause_seen` donne le message et l'état CFS de chaque pause, `resume_attempt`
et `resume_reply` chaque reprise, `exit` la raison de fin.

## Arrêter

Créer `/tmp/kctrl_autoresume.stop` ; le processus sort au prochain tour.

## Limites

Non prouvé sur un vrai `key837` : la reprise par `RESUME` après ADR-072 n'a pas
encore été observée. Aucune reprise pendant les 300 premières secondes
d'impression ni après coupure moteurs. Une pause manuelle est reprise.
