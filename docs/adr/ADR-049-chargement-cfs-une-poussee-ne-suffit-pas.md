# ADR-049 — Chargement CFS : une poussée ne suffit pas, et l'erreur ne remonte pas

Date : 2026-09-01

Statut : **accepté**, cause mesurée sur la machine, correctif déployé et vérifié
au chargement ; pas encore rejoué depuis un départ d'impression complet

## Contexte

Le 1er septembre 2026 à 21:50, un départ d'impression a été refusé par le garde
`_KCTRL_ASSERT_FILAMENT_ENGAGED` : aucun filament après le cutter. La séquence
de démarrage était pourtant celle qui avait chargé correctement quelques heures
plus tôt, sur le même fichier et la même bobine.

La console porte la vraie cause, en amont du garde :

```
// max_volumetric_speed: 14
// flush_temp: 220
!! {"code":"key836", "msg":"extrude error, maybe there's a blockage between
   the connections and the filament sensor", "values": [1, "A"]}
```

Le CFS 1 emplacement A a poussé pendant soixante-dix-sept secondes, épuisé ses
cinq tentatives internes (`box_extrude_retry_num: 5`), puis **rendu la main sans
faire échouer la séquence**. Tout ce qui suit — extrusion, purge, ligne
d'amorce — se serait déroulé à vide. Seul le garde a arrêté l'impression.

Trois faits ont été établis en rejouant la séquence d'origine à la main.

### L'erreur du CFS se verrouille et rend les appels suivants muets

Un `BOX_EXTRUDE_MATERIAL TNN=T1A` relancé tel quel **ne fait rien** : il rend la
main immédiatement, sans mouvement ni message. Le même appel précédé d'un
`BOX_ERROR_CLEAR` charge normalement.

```
BOX_EXTRUDE_MATERIAL TNN=T1A   ->  tete=False  E=-31.0   (aucun mouvement)
BOX_ERROR_CLEAR
BOX_EXTRUDE_MATERIAL TNN=T1A   ->  tete=True   E=-8.0    (chargé)
```

`BOX_ERROR_CLEAR` appartient donc à l'intérieur de la boucle de réessai, pas
avant elle. La route en place n'appelait qu'une seule poussée.

### Les deux capteurs ne disent pas la même chose

Au moment du refus, `filament_sensor` (jonction arrière) voyait du filament et
`filament_sensor_2` (tête, après cutter) n'en voyait pas. Le filament était
présent jusqu'à la jonction et n'arrivait pas à la tête : exactement le libellé
de `key836`.

Thomas a déplacé le module CFS d'environ un centimètre pendant le diagnostic et
la poussée suivante est passée. **Le geste et l'effacement d'erreur tombent dans
la même minute et ne sont pas départageables.** Un tube pincé en sortie de CFS
explique mieux l'échec initial des cinq tentatives ; le verrou d'erreur explique
pourquoi toute relance restait sans effet. Les deux sont retenus.

### Le CFS laisse le capteur de tête désactivé

Après un chargement réussi, `filament_sensor_2` est mesuré à
`enabled: False`. Le CFS le désactive pour charger et ne le restaure jamais.
L'état survit à un `FIRMWARE_RESTART`. Toute impression démarrée par cette route
tournait donc **sans détection de fin de bobine**, ce qui est incompatible avec
le rechargement automatique visé.

## Décision

Le pas matière du démarrage devient :

```
BOX_CHECK_MATERIAL
_KCTRL_CFS_LOAD TOOL=... ATTEMPT=1..4
_KCTRL_ASSERT_FILAMENT_ENGAGED STAGE=after_cfs_load
BOX_EXTRUDER_EXTRUDE
BOX_MATERIAL_FLUSH
SET_FILAMENT_SENSOR SENSOR=filament_sensor_2 ENABLE=1
```

`BOX_CHECK_MATERIAL` est ajouté parce que les deux chemins de chargement
d'origine, `BOX_LOAD_MATERIAL_WITH_MATERIAL` et
`BOX_LOAD_MATERIAL_WITHOUT_MATERIAL`, l'appellent avant de pousser ; la route
propriétaire l'omettait.

`_KCTRL_CFS_LOAD` lit le capteur de tête **au moment de son rendu**, ce qui rend
toute tentative postérieure à un succès sans effet. Chaque tentative réelle
efface l'erreur du CFS avant de pousser, attend la fin des mouvements et laisse
un quart de seconde au contact pour s'établir.

Quatre tentatives : la mesure montre un succès à la deuxième ; deux de marge
couvrent un tube qui accroche sans exiger d'intervention.

## Conséquences

- Un échec de chargement ne peut plus produire une impression à vide sans que
  quelque chose l'arrête : le garde reste, et la boucle lui donne de quoi
  réussir avant qu'il ne se déclenche.
- La détection de fin de bobine est rétablie à chaque départ. C'est le
  prérequis du rechargement automatique en fin de bobine.
- `key836` reste un signal à surveiller : s'il réapparaît alors que la boucle
  finit par réussir, le chemin mécanique entre CFS et tête accroche et demande
  une inspection, pas un réessai supplémentaire.
- Le correctif est vérifié au niveau du chargement seul. Il **n'a pas encore
  été rejoué depuis un `START_PRINT` complet**.

## Voir aussi

- ADR-040 — cutter : aucun rejeu automatique
- ADR-045 — aucun palpage sans buse nettoyée à la main
- ADR-046 — profil de maillage référé au point de palpage
