# Goal 3 — registre de complétude physique

Ce paquet ne crée aucun Goal ni aucune nouvelle autorité. Il matérialise les
sept exigences déjà contenues dans `GOALS.md`, le contrat du cycle et le plan
hors imprimante. Le projet reste limité à quatre Goals.

Statut actuel : **Goal 3 en cours ; deux exigences sur sept sont passées**.
CLEAN-MOTION-V1 est clos OK. L'identifiant historique
`AUTOMATIC_CLEAN_AND_FINAL_REFERENCE` reste visible, mais sa résolution est le
rejet physique du nettoyage automatique et l'adoption du nettoyage manuel
obligatoire. Les actions automatiques sont bloquées et la référence finale
n'est pas présentée comme exécutée. La prochaine exigence est la qualification
des états CFS et de leurs températures.

Le registre est entièrement local. Il ne contient aucun connecteur K1, aucune
commande G-code, aucune pose, aucun restart et aucun effet physique. Son
vérificateur refuse de déclarer le Goal 3 terminé tant qu'une seule des sept
exigences n'est pas `PASSED` avec sa preuve physique.

Dans l'exigence CFS courante, `EMPTY_LOAD_T1A` est passé. Le premier
`KEEP_CORRECT_T1A` est KO avec arrêt sûr : le départ Orca historique a laissé
le mesh `default`, puis l'annulation a laissé l'état interne `cancelled/T0`
malgré des chauffes à zéro. Thomas a annoncé qu'il allait éteindre la K1. La reprise unique est
un préflight à froid en lecture seule ; aucun retry implicite.

La frontière est explicite : la bascule Orca/K1 Control, le redémarrage à froid,
les trois impressions de production et la clôture finale appartiennent au Goal
4. Ils ne peuvent pas servir à masquer une qualification physique manquante du
Goal 3 et ne justifient pas non plus un cinquième Goal.

Commande locale :

```powershell
python.exe packages/k1-control-v1/physical-slices-qualification-v1/verify_completion.py
```

Résultat attendu aujourd'hui : `GOAL3_LEDGER_OK_IN_PROGRESS`, avec
`passed=2`, `remaining=5` et zéro effet déclaré par ce registre local.
