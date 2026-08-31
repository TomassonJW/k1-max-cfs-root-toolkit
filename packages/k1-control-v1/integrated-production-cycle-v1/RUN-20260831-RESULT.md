# Résultat réel du cycle intégré — 31 août 2026

Statut : **CLOSED_KO_STOCK_CFS_OWNER_BLOCKED**

## Résultat utile

Le cycle intégré n'a pas atteint le nettoyage manuel, la référence Z, le
chargement, la purge ni l'impression. Il s'est fermé sans retry pendant la
tentative de réassociation du filament physique déclaré `T1A`.

La primitive stock a :

- respecté d'abord la demande de chauffe K1 Control à `190 °C` ;
- référencé X/Y et déplacé la tête vers le parc stock ;
- annoncé `max_volumetric_speed: 14` puis `flush_temp: 220` ;
- porté la buse au-dessus de `220 °C` malgré le contrat à `190 °C` ;
- échoué avec `retrude error, failed to exit connections` ;
- laissé les deux routes CFS vides et les deux capteurs de filament actifs ;
- vidé le mesh actif.

Le garde a ensuite mis les cibles à zéro et refusé toute reprise. Le `11 × 11`
a été restauré une fois, sans mouvement. Cette observation confirme la preuve
historique de `docs/29-audit-box-wrapper-et-adaptateur-cfs-v1.md` ; le candidat
n'aurait pas dû appeler cette primitive avant sa qualification isolée.

## Confinement retenu

- `authority_mode: offline` sur le Moonraker K1 Control dédié ;
- API : `effects_enabled: false` ;
- cycle Klipper revenu à `idle` après chargement des macros neutralisées ;
- les entrées de réassociation, chargement, retrait et fin refusent désormais
  avant tout effet CFS stock ;
- backup exact :
  `/usr/data/k1-control-v1/backups/20260831-integrated-cycle-stock-owner-ko-containment/` ;
- macro neutralisée distante :
  `97fe159a3e4105512f8a349539d224f42cd28617dbb9a6dfa403195b7e68f998` ;
- configuration Moonraker confinée :
  `aae7130b39b3676d32f4ebd6677c83824bd596f6db8e4c28c90992677ec183a0`.

## État final vérifié

- Klipper `ready`, impression `standby`, aucun fichier actif ;
- buse `30,89 °C`, cible `0 °C` ;
- plateau `27,66 °C`, cible `0 °C` ;
- axes libérés ;
- `k1_p001_t055_r001_n11x11` actif ;
- Z accepté `−0,04 mm` intact ;
- CFS `T1` et `T2` connectés, aucune route, aucune commande active ;
- filament toujours vu par les deux capteurs ;
- caméra fraîche : tête haute, plateau dégagé, image nette.

La chauffe en présence de filament a pu laisser un nouveau résidu sur la buse.
Aucune future référence de contact ne peut donc réutiliser l'ancien constat de
propreté : un nettoyage frais sera obligatoire juste avant la référence Z et
avant toute insertion suivante.

## Suite autorisable

Une nouvelle gate intégrée est interdite. Le choix produit est désormais réel :

1. construire un propriétaire CFS borné qui ne délègue ni température ni
   géométrie aux grandes primitives stock ; ou
2. accepter temporairement le bouton officiel comme frontière humaine de
   chargement/retrait.

L'autonomie demandée impose l'option 1. Elle doit d'abord produire une preuve
hors imprimante du protocole exact, puis qualifier séparément un chargement et
un retrait uniques avant de revenir au cycle complet.
