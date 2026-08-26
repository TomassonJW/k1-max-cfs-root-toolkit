# Audit CFS en lecture seule V1

Date : 2026-08-26
Statut : audit clos OK ; reprise physique bloquée en sécurité

## Résultat utile

La K1 détecte actuellement une présence de filament, mais ne permet pas de
relier cette présence à un outil logique, un CFS, un slot physique et un débit
à la buse. Le classement sûr est donc `engaged_unknown`.

Ce verdict ne dit pas que le filament est absent, coincé ou mal chargé. Il dit
que les preuves disponibles en lecture seule ne suffisent pas à choisir une
route ni à promettre une extrusion.

## Méthode

La capture privée `20260826-final-cfs-read-only-audit-v1` a lu :

- l'état Moonraker/Klipper et la liste des objets ;
- les deux objets `filament_switch_sensor` ;
- l'objet propriétaire `box` et les deux unités CFS ;
- `box.cfg`, les deux sections capteurs de `printer.cfg` et les données
  persistantes CFS ;
- les transitions déjà présentes dans les journaux ;
- les empreintes de la configuration avant et après la collecte.

Le collecteur n'expose aucun endpoint G-code. Il n'a envoyé ni chauffe, ni
homing, ni mouvement, ni chargement, ni coupe, ni purge, ni restart, et n'a
écrit aucun fichier distant.

## Ce que prouvent les capteurs

`filament_sensor` est activé et vaut vrai. Sa broche est `!PC15`.
`filament_sensor_2` est désactivé et vaut faux. Sa broche est
`^!nozzle_mcu:PA10`, et `box.cfg` le déclare comme capteur utilisé par le
composant `box`.

Ces noms et associations logicielles sont exacts. Leur position physique
précise dans le chemin filament ne l'est pas : elle n'est donc pas inventée.
Comme le second capteur est désactivé, sa valeur fausse ne constitue pas une
preuve d'absence. Les deux valeurs ne sont pas traitées comme une contradiction
ou une panne sans qualification physique de leurs rôles.

## Mapping CFS et identité

Les CFS `T1` et `T2` sont connectés et leurs slots `A..D` ont des fiches
matière. Ces fiches sont un inventaire déclaré, pas une preuve du filament
réellement engagé.

L'historique montre qu'un outil logique peut changer de route vers un autre
slot physique. Le mapping est donc dynamique. Au moment de l'audit :

- `box.t_command` est vide ;
- aucune unité ne publie de filament actif ;
- `tn_data.json` ne contient que les données de slots ;
- aucune clé courante `tnn_map`, `last_cmd` ou `last_tnn` n'établit une route.

Une ancienne route lue dans un journal ne peut pas devenir une route actuelle.

## Règles de décision

| État | Preuve minimale | Action sûre |
|---|---|---|
| `absent_confirmed` | absence concordante sur tous les capteurs qualifiés et aucune route active | permettre seulement la préparation d'un chargement futur |
| `engaged_known` | présence, identité et route courantes concordantes | conserver le filament ; purge de preuve encore obligatoire |
| `engaged_unknown` | présence sans identité ou route courante suffisante | arrêter avant toute extrusion et demander une résolution explicite |
| `transitioning` | chargement, retrait, coupe ou changement réellement en cours | attendre une fin bornée ou appliquer la récupération dédiée |
| `fault` | incohérence sur des capteurs qualifiés, CFS déconnecté ou transition échouée | couper les chauffes si elles sont actives et exiger un diagnostic |

La purge visible n'est jamais déduite d'un de ces états. Elle reste une preuve
physique séparée du débit à la buse.

## Gate suivante

La reprise de `MESH-EDGE-DIAGNOSTIC-V1` n'est pas autorisée par cet audit. Une
future mission physique doit, juste avant toute extrusion :

1. confirmer Thomas présent et le plateau réellement libre ;
2. résoudre explicitement le matériau, l'outil logique et le CFS/slot physique ;
3. vérifier la température compatible avec le matériau réel ;
4. obtenir une petite purge visible ;
5. arrêter sans motif si la purge n'est pas visible.

Cette future mission exige une nouvelle demande ou un nouveau GO avant toute
action K1.
