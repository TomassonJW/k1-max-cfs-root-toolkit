# ADR-066 — Le départ s'arrête net sur une pause ; deux tentatives de chargement au lieu de quatre

Date : 2026-09-14

Statut : **acceptée** (accord de Thomas le 14 septembre au soir) ; écrite et
testée hors machine ; installée le 14 septembre à 22:16 (Klipper redémarré
machine à l'arrêt, démarrage sans erreur, contrôle essayé à vide sans effet) ;
premier départ réel le 14 septembre à 22:30 passé sans arrêt, CFS sans erreur ;
l'arrêt sur une vraie pause reste à observer (document 79, section 9.5).

Amende ADR-049 (quatre tentatives). Corrige les deux défauts de notre départ
relevés par le document 79, section 5.

## Contexte

Journaux du 14 septembre 2026 :

- **Départ de 18:14.** Le changement d'outil abandonne à 18:18:56 (`key836`)
  et met l'impression en pause. Nos quatre tentatives poussent quand même ;
  chacune finit sur une nouvelle pause (18:20:19, 18:21:42, 18:23:02,
  18:24:25). L'annulation demandée à 18:23:58 n'aboutit qu'à 18:24:57.
- **Départ de 18:30.** Le changement abandonne à 18:36:22 (`key845`, buse
  bouchée pendant la purge) et rend la main à 18:36:35. Notre première
  tentative pousse encore (`key840` à 18:36:52, `key836` à 18:38:52), puis la
  ligne d'amorce est tracée à 18:39:33.

Le module CFS compilé ne publie aucune erreur : l'objet `box` porte
`filament`, `state`, `auto_refill`, `enable`, `filament_useup`,
`same_material`, `T1` à `T4`, `cut_pos`, `t_command`, `custom_command_result`
(lus vers 21:45), rien d'autre. Quand il abandonne, il écrit « error: printing
to pause » et met en pause : `pause_resume.is_paused` est le seul signal
lisible depuis une macro. Une relance qu'il gagne ne met pas en pause (20:35:41
et 20:47:06). Du 9 au 14 septembre, chaque tentative au-delà de la première a
suivi une pause du module (9 septembre 18:03:11 et 18:04:36 ; 14 septembre
18:20:24, 18:21:48, 18:23:08).

## Décision

1. `_KCTRL_ASSERT_CFS_OK` lit la pause à trois endroits de `START_PRINT` :
   juste après le changement d'outil (`after_tool_change`), après les
   tentatives (`after_cfs_load`), après la dernière chauffe et avant les
   contrôles de filament et la ligne d'amorce (`before_prime`). Sur pause :
   fenêtre de chargement fermée, buse et plateau à 0, fenêtre Z du départ
   fermée, `CLEAR_PAUSE`, puis l'erreur « K1 Control [étape]: impression mise
   en pause pendant le depart … ». L'impression finit en erreur.
2. Deux tentatives de chargement au lieu de quatre. Elles ne tournent plus
   qu'après un changement d'outil qui laisse la tête vide sans pause, cas
   absent des journaux du 9 au 14 septembre ; une tentative ratée coûte environ
   80 secondes.

Deux contraintes du rendu Jinja fixent la forme. `START_PRINT` est rendu en
entier avant sa première commande : la pause est donc lue dans une macro à
part. `action_raise_error` lève au rendu : l'erreur vient d'une seconde macro,
`_KCTRL_START_STOPPED`, sans quoi aucune commande d'arrêt ne tournerait.

Les chauffes sont coupées parce que `idle_timeout` vaut 99999999 s sur cette
machine. La pause est effacée parce que le départ est fini : une pause que
personne ne peut reprendre ment sur l'état de la machine.

## Conséquences

- Rejoués avec la règle, le départ de 18:14 s'arrête vers 18:19 au lieu de
  18:24:57, et celui de 18:30 à 18:36:35, sans ligne d'amorce.
- **On ne reprend plus un départ interrompu.** Le 14 septembre, Thomas a repris
  celui de 18:30 à 18:55, et l'impression a fini. Désormais : vérifier le
  filament, puis relancer l'impression depuis le début.
- Une pause demandée depuis l'interface pendant le départ l'arrête aussi,
  comme celle du 10 septembre à 10:11. Rien n'est encore sur le plateau ;
  avant, le départ allait quand même jusqu'à sa ligne d'amorce.
- `BOX_ERROR_CLEAR` reste dans `_KCTRL_CFS_LOAD`. Les tentatives ne tournent
  plus après une pause : il n'efface que le verrou d'un chargement raté sans
  alerte.
- Vérifié hors machine : 12 tests
  (`tests/test_owned_start_stops_on_cfs_pause_v1.py`), suite complète verte.
- **Inconnu :** un nouveau départ juste après un arrêt en erreur n'a pas été
  rejoué sur la machine. `virtual_sdcard.py` de la machine ne lit pas la
  pause, et `START_PRINT` fait `CLEAR_PAUSE` avant son changement d'outil.

## Voir aussi

- ADR-049 — chargement CFS : une poussée ne suffit pas
- ADR-065 — alarme de fin de bobine coupée pendant un changement d'outil
- Document 79 — audit des séquences de départ et de changement
- Document 70 — départ et chargement CFS
