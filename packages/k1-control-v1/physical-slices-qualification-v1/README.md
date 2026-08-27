# Goal 3 — registre de complétude physique

Ce paquet ne crée aucun Goal ni aucune nouvelle autorité. Il matérialise les
sept exigences déjà contenues dans `GOALS.md`, le contrat du cycle et le plan
hors imprimante. Le projet reste limité à quatre Goals.

Statut actuel : **Goal 3 en cours ; D1 et D2 acceptés ; D3 de CLEAN-MOTION
techniquement vert, verdict humain `D3 OK` encore absent ; aucune tranche
physique complète passée**.

Le registre est entièrement local. Il ne contient aucun connecteur K1, aucune
commande G-code, aucune pose, aucun restart et aucun effet physique. Son
vérificateur refuse de déclarer le Goal 3 terminé tant qu'une seule des sept
exigences n'est pas `PASSED` avec sa preuve physique.

La frontière est explicite : la bascule Orca/K1 Control, le redémarrage à froid,
les trois impressions de production et la clôture finale appartiennent au Goal
4. Ils ne peuvent pas servir à masquer une qualification physique manquante du
Goal 3 et ne justifient pas non plus un cinquième Goal.

Commande locale :

```powershell
python.exe packages/k1-control-v1/physical-slices-qualification-v1/verify_completion.py
```

Résultat attendu aujourd'hui : `GOAL3_LEDGER_OK_IN_PROGRESS`.
