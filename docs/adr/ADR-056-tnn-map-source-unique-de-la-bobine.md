# ADR-056 — `Tnn_map` est la seule réponse à « quelle bobine »

Date : 2026-09-02

Statut : **accepté**. Complète l'ADR-055 et en corrige la dernière conséquence.

## Contexte

L'ADR-055 avait posé `KCTRL_SLOT` comme point d'entrée de la sélection, en
écrivant à la fois `Tnn_map` et une variable persistante `kctrl_slot`, et avait
conclu que « la sélection ne passe pas par l'écran de la machine ».

Cette conclusion était fausse sur les deux moitiés. L'écran écrit bien
`Tnn_map`, par `BOX_MODIFY_TN`, après avoir montré à l'opérateur les filaments
du G-code en face des bobines du CFS. Et si `START_PRINT` ne relisait pas cette
table, ce n'est pas parce qu'elle vivait ailleurs : c'est parce que Klipper ne
la publie pas, donc aucune macro ne pouvait la voir.

Le popup n'avait jamais été appelé non plus : dix-neuf impressions sur vingt
sont parties de Fluidd ou de Mainsail, qui n'ont pas ce popup. Voir doc 55.

## Décision

**`Tnn_map` est la source unique. Personne ne stocke la sélection à côté.**

1. Un objet Klipper en lecture seule, `kctrl_slot_map`, publie la table telle
   que le firmware l'écrit. Il ne relit que si le fichier a changé, il n'écrit
   jamais, et il refuse de propager une entrée abîmée.
2. `START_PRINT` résout l'emplacement par `map["T1A"]`. Table illisible : il
   refuse de démarrer. Repartir sur `T1A` en silence est exactement la panne à
   laquelle tout ceci répond.
3. La variable persistante `kctrl_slot` est supprimée. `KCTRL_SLOT` n'écrit plus
   que `Tnn_map`.
4. Le chemin de chargement stock, `BOX_START_PRINT_EXTRUDE_MATERIAL
   START_PRINT=8`, n'est pas repris. Il résoudrait l'emplacement lui-même, mais
   il possède aussi les tentatives, la chauffe et la purge, toutes mesurées et
   refaites ici pour des raisons écrites dans le fichier.

## Conséquences

- Trois écrivains, une table : le popup de l'écran, `BOX_CHECK_MATERIAL_REFILL`
  quand une bobine s'épuise, `KCTRL_SLOT` quand il n'y a pas d'écran. Ils ne
  peuvent plus se contredire.
- Une impression lancée depuis l'écran, l'application ou la page web Creality
  passe par le popup et n'exige rien d'autre. Une impression lancée depuis
  Fluidd ou Mainsail garde la table posée par le dernier qui a décidé, et
  `KCTRL_SLOT` est là pour ces cas.
- `KCTRL_MAP` et `KCTRL_SLOTS` lisent la même source que le démarrage. Ce qui
  est affiché est ce qui sera chargé.
- Le déploiement du module demande un redémarrage du service Klipper, pas un
  `FIRMWARE_RESTART`, et remet le maillage actif sur `default`.
- Les purges du trancheur ne sont pas concernées : elles décrivent des
  changements de couleur, traités par le `cmd_T` stock qui les lit dans le
  fichier tranché. Voir doc 55, section 6.

## Voir aussi

- ADR-055 — sélection et rechargement, complétée ici
- doc 55 — preuves, journaux et chemin du popup
- doc 54 — preuves de la session précédente
