# ADR-011 — Adaptateur `probe_count` pour `prtouch_v3`

Date : 2026-08-23

Statut : accepté puis complété par PRTOUCH-BED-MESH-V2 après XS3002

## Contexte

La première campagne réelle `9 × 9` lancée depuis K1 Control a chauffé,
stabilisé et parcouru la première grille, puis s'est arrêtée sans matrice avec
`Le mesh ne contient pas le nombre de lignes attendu.` Les chauffes ont été
coupées, le Z accepté `−0,04 mm` et le profil `6 × 6` sont restés intacts.

L'audit du firmware exact montre que la commande `BED_MESH_CALIBRATE` est
remplacée par le module propriétaire Creality
`prtouch_v3_wrapper.cpython-38-mipsel-linux-gnu.so`. Contrairement au
`bed_mesh.py` amont présent sur la machine, ce wrapper construit son parcours à
partir de `[bed_mesh] probe_count` chargé au démarrage de Klipper. La K1 avait
toujours `6,6` chargé : transmettre `PROBE_COUNT=9,9` dans le G-code ne suffisait
donc pas. Le wrapper indique en outre que son parcours spiralé exige une matrice
carrée impaire ; le `6 × 6` stock reste un cas déjà prouvé sur cette machine.

Cette preuve invalide l'hypothèse de l'ADR-010 selon laquelle la seule extension
du serveur et de l'interface rendait les grandes matrices exécutables.

## Options examinées

1. Revenir à `6 × 6` seulement. Refusé : cela contredit les quatre niveaux du
   produit et la demande explicite d'aller jusqu'à `15 × 15`.
2. Contourner `prtouch_v3` et appeler directement le moteur `bed_mesh` amont.
   Refusé : cela supprimerait les protections et le parcours propres au capteur
   Creality exact.
3. Modifier manuellement `printer.cfg` et redémarrer entre chaque niveau.
   Refusé comme procédure opérateur : ce ne serait pas autonome et multiplierait
   les risques de saisie.
4. Ajouter un adaptateur Moonraker borné qui commute atomiquement le seul
   `probe_count`, redémarre Klipper avant toute chauffe, vérifie la valeur chargée
   et restaure la valeur précédente après coupure des chauffes. Retenu.

## Décision

Un composant séparé enveloppe uniquement le backend de calibration K1 Control.
Au premier `BED_MESH_CLEAR` de la phase `preparing`, après création du backup
exact et avant préchauffe :

- il refuse toute matrice non revue ;
- il exige que `printer.cfg` et la valeur chargée par Klipper correspondent ;
- il remplace atomiquement l'unique ligne `probe_count` de `[bed_mesh]` ;
- il redémarre seulement Klipper ;
- il attend le runtime Z, le chemin borné, les chauffes et l'état `standby` ;
- il relit le `probe_count` réellement chargé avant de laisser la campagne
  continuer.

Après `TURN_OFF_HEATERS`, que le niveau soit annulé, rejeté ou terminé, il
restaure atomiquement le `probe_count` précédent et vérifie le redémarrage. Un
redémarrage du Moonraker dédié au milieu d'une session reconstruit cet état à
partir du backup exact de la campagne.

Les matrices physiques retenues sont `6 × 6`, `9 × 9`, `11 × 11` et `15 × 15`.
Les petites matrices carrées impaires `3 × 3` et `5 × 5` restent compatibles.
Le `4 × 4`, non conforme à la contrainte observée du wrapper spiralé, a été
retiré par le delta statique `PRTOUCH-PRESETS-V1` installé et validé.

La seconde preuve réelle a montré que `algorithm` appartient à la même frontière
de démarrage que `probe_count` : `9,9 + lagrange` arrête Klipper avec XS3002
avant chauffe. La révision V2 applique donc la décision au couple atomique
`probe_count + algorithm`, vérifie les deux valeurs chargées et restaure les deux
depuis le backup exact.

## Conséquences

- le changement de matrice implique un redémarrage Klipper avant chauffe ;
- la pose du composant ne modifie pas `printer.cfg` et redémarre seulement le
  Moonraker K1 Control ;
- l'exécution modifie temporairement une seule ligne, toujours après backup ;
- aucun mouvement, chauffage ou G-code n'est envoyé tant que la valeur chargée
  n'est pas prouvée ;
- la campagne réelle `9/11/15/6` doit être reprise depuis zéro sous un nouveau
  protocole, sans considérer l'essai vide `1/6` comme une mesure exploitable.
