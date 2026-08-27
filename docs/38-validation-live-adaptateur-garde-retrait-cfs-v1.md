# Validation live de l'adaptateur du garde de retrait CFS V1

Date : 2026-08-27

Mission :
`G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-ADAPTER-LIVE-READ-ONLY-V1`

Verdict : **OK en lecture seule ; production fermée**.

## Ce qui a été fait

Le collecteur a lu deux fois les mêmes objets Moonraker et calculé avant puis
après les empreintes de `printer.cfg`, `box.cfg` et `gcode_macro.cfg`. La
capture brute est privée et ignorée par Git.

Le validateur local exige la forme exacte connue. Il reconstruit ensuite une
réponse minimale qui ne contient que les valeurs utiles. Les numéros de série
`sn` et les `uuid` sont donc retirés avant l'appel à l'adaptateur. Un nouveau
champ dans l'état, dans `box` ou dans une unité CFS provoque un arrêt au lieu
d'être ignoré silencieusement.

## Résultat réel

Les deux lectures sont identiques : Klipper est prêt, l'impression est au
repos, `T1/T2` sont connectés, aucune route n'est engagée, la commande CFS est
vide, le segment après cutter reste détecté et les deux cibles thermiques sont
à zéro. Les trois empreintes sont inchangées.

Les tests ciblés du garde, du mapping et des deux adaptateurs obtiennent
`61/61`. La suite complète exécute `443` tests, dont `440` verts et `3` ignorés
connus.

La réponse réelle a aussi confirmé que les unités non provisionnées `T3/T4`
utilisent la chaîne exacte `None`, et non `disconnect`. L'adaptateur accepte
maintenant cette seule valeur réelle comme unité inactive ; toute autre valeur
inconnue reste refusée.

## Limites

`StockUnloadGuard.run` n'a été ni importé ni appelé. Aucun G-code, chauffage,
mouvement, retrait, fichier distant, service ou restart n'a été produit.
L'état reste `BLOCKED_NO_ENGAGED_ROUTE`, sans transport ni candidat de pose.

La prochaine étape proposée est un transport entièrement hors imprimante,
testé sur des réponses synthétiques ou enregistrées. Elle ne donnera encore
aucune autorité de connexion ou de retrait.
