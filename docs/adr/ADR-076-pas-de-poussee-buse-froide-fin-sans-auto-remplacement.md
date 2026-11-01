# ADR-076 - Pas de poussée de filament buse froide ; la fin coupe l'auto-remplacement CFS avant la coupe

Date : 31 octobre 2026 (garde), 1er novembre 2026 (fin V5). Statut : accepté ;
garde à froid en service depuis le 31 octobre, fin V5 prête, pas posée.

## Contexte

Le 31 octobre vers 19:01, T1B s'est réellement vidée en cours d'impression et
le relais stock est passé sur T1A, comme prévu. Dès 19:02, le CFS 1 a signalé
T1A en erreur filament (`FILAMENT_ERR`) alors que la bobine était pleine. À la
fin du fichier, pendant la coupe de la fin V4, le firmware a émis `key839`
(« no filament detected at box extrude position ») et lancé sa routine stock
« extrude all material ». La fin V4 a vu l'erreur, s'est arrêtée en échec et a
coupé les chauffes ; elle n'a aucun moyen d'arrêter une routine stock déjà
partie. Creality a commenté dans `extruder.check_move` le refus d'extrusion à
froid de Klipper (`can_extrude`) : la routine a poussé par cycles d'environ
40 s pendant que la buse refroidissait de 159 à 36 °C, jusqu'à l'arrêt
d'urgence de Thomas à 19:16. Le PTFE est sorti de son raccord. Remettre
`auto_refill` à 0 pendant la boucle ne l'a pas arrêtée.

Décision de Thomas le soir même : « Impression finie = retrait de filament, on
en parles pluys! ET SURTOUT, pas de purge si buse froide! »

## Décision

Deux protections séparées, posées dans cet ordre et retirées dans l'ordre
inverse.

Garde à froid : `kctrl_purge_guard.py`, révision `cold-push-guard-v1`. La
couche qui protège déjà le bac enveloppe aussi `extruder.check_move`. Elle
refuse une poussée quand la buse est sous sa température minimale d'extrusion
(170 °C) et qu'aucune consigne ne l'atteint. Un retrait passe toujours ; une
poussée passe buse chaude, ou pendant une chauffe vers une consigne suffisante.
Le refus est une erreur de commande, sans chauffe, mouvement ni arrêt
d'urgence. Il vaut pour tous les chemins, stock compris.

Fin V5 : `kctrl_end.py`, révision `end-no-stock-flush-v5`. Avant toute coupe ou
commande `BOX_*`, la fin lit `box.auto_refill` ; à 1, elle le passe à 0 et
exige deux lectures à 0. Avant chaque effet suivant, elle relit : revenu à 1
(l'écran tactile envoie `BOX_ENABLE_AUTO_REFILL ENABLE=1` à chaque connexion),
elle s'arrête en échec (`auto_refill_reenabled`). `key839` ou « filament
error » pendant la fin donnent l'échec nommé `cfs_filament_error`. Une fin
complète remet l'auto-remplacement, prouvé par deux lectures. Une fin en échec
le laisse coupé ; le départ suivant le remet avant toute chauffe et refuse de
partir s'il ne peut pas le prouver. Une tête déjà vide suit la même règle.

Inchangé : une fin normale vide la tête ; une annulation garde le filament
(ADR-074) et ne touche pas à l'auto-remplacement.

## Conséquences

- Plus de poussée buse froide sans chauffe demandée, quel que soit le chemin.
  Une routine stock qui retente voit chaque essai refusé et compté
  (`cold_refused`) ; l'effet de ce refus sur le moteur du CFS n'est pas
  observé.
- Avec la fin V5, une erreur filament du CFS pendant la fin trouve
  l'auto-remplacement coupé. D'après des notes tierces non officielles, le
  firmware signale alors l'erreur sans lancer de purge ; ce n'est pas observé
  sur la K1.
- Après une fin en échec, le départ reste bloqué jusqu'au redémarrage, comme
  avant. Le redémarrage remet aussi l'auto-remplacement : vu le 31 août, et
  relu à 1 après l'extinction du 31 octobre.
- Retour arrière : fin V5 d'abord, garde ensuite. Chaque installateur vérifie
  la révision de l'autre et refuse l'ordre inverse.
- Les installateurs plus anciens qui épinglent l'empreinte précédente du garde
  (`c90de4c3…` : `cancel-retained-end-v4`, `resume-reload-guard-v1`,
  `retained-start-v1`) refusent désormais au préflight. Ils restent tels quels.
