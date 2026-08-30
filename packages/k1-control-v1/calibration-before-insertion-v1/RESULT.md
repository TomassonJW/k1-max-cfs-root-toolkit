# Résultat

Statut : `CLOSED_OK_RULE_FROZEN_PREFLIGHT_CLOSED_NO_EFFECT`.

La remarque physique est désormais une règle durable du projet, ADR-034 la
porte et R3 est fermé avant toute pose. Le préflight strictement en lecture
seule a confirmé les gestes manuels côté état observable, sans prétendre prouver
la propreté microscopique de la buse.

État observé : Klippy prêt, impression `standby`, chauffes demandées à zéro,
`T1A` engagé, aucune commande CFS, Z accepté `−0,04 mm`, configurations stables.
Le profil actif est toutefois `default` en `6 × 6` ; le meilleur `11 × 11`
existe encore mais n'est pas actif.

Aucun G-code, chauffage, mouvement, extrusion, ordre CFS, fichier distant,
service, pose ou impression n'a été exécuté. La prochaine gate séparée doit
seulement restaurer et relire le `11 × 11`, sans palpation ni autre effet.
