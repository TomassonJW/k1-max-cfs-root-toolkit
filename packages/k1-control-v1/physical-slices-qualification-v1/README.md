# Goal 3 — registre de complétude physique

Ce paquet ne crée aucun Goal ni aucune nouvelle autorité. Il matérialise les
sept exigences déjà contenues dans `GOALS.md`, le contrat du cycle et le plan
hors imprimante. Le projet reste limité à quatre Goals.

Statut actuel : **Goal 3 en cours ; deux exigences sur sept sont passées**.
CLEAN-MOTION-V1 est clos OK. L'identifiant historique
`AUTOMATIC_CLEAN_AND_FINAL_REFERENCE` reste visible, mais sa résolution est le
rejet physique du nettoyage automatique et l'adoption du nettoyage manuel
obligatoire. Les actions automatiques sont bloquées et la référence finale
n'est pas présentée comme exécutée. L'exigence CFS est maintenant à `2/4` :
`EMPTY_LOAD_T1A` et `KEEP_CORRECT_T1A` sont passés. Le prochain effet physique
reste bloqué par le diagnostic du Z à fenêtre thermique comparable.

Le registre est entièrement local. Il ne contient aucun connecteur K1, aucune
commande G-code, aucune pose, aucun restart et aucun effet physique. Son
vérificateur refuse de déclarer le Goal 3 terminé tant qu'une seule des sept
exigences n'est pas `PASSED` avec sa preuve physique.

Dans l'exigence CFS courante, le départ possédé a conservé `T1A`, exécuté la
purge visible et terminé deux couches sous verdict humain positif. Le Z accepté
`−0,04 mm` a toutefois nécessité un réglage humain à `−0,19 mm`. La calibration
avait stabilisé le plateau `200 s`, contrairement à ce départ. Cette différence
doit être isolée avant une recalibration ou une nouvelle impression. La fin de
test a coupé les chauffes et libéré les moteurs, mais n'a ni parqué la tête ni
présenté le plateau ; elle ne qualifie pas la future séquence de fin.

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
