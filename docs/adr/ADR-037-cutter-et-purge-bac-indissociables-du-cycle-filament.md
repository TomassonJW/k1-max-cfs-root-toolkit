# ADR-037 — Cutter et purge bac indissociables du cycle filament

Date : 2026-08-31

Statut : **acceptée ; ADR-036 partiellement remplacée ; toute nouvelle action
filament reste fermée jusqu'au successeur intégré hors imprimante**

## Contexte

La gate `G4-K1-CONTROL-CFS-DIRECT-OWNER-PHYSICAL-LOAD-UNLOAD-V1` avait été
conçue comme une qualification isolée : aucun mouvement d'axe, retrait direct
sans cutter et chargement sans purge. Thomas a rappelé deux contraintes
physiques obligatoires de sa K1 Max :

- avant un retrait, la tête doit atteindre la position cutter et le filament
  doit être coupé ;
- après une insertion ou un chargement, une purge doit toujours être faite dans
  le bac, puis décrochée par `3 à 4` allers-retours francs du mécanisme du bac.

Le contrat produit contenait déjà le trajet cutter pour un changement et une
fin normale, ainsi que la purge visible. ADR-036 avait néanmoins accepté une
dérogation temporaire sans cutter pour la V1 directe. Cette dérogation est
incompatible avec le besoin physique réel.

La tentative V1 s'est arrêtée encore plus tôt : après activation et restart,
`auto_refill` est revenu à `1`. Le préflight actif a fermé la gate sur
`stock_auto_refill_invalid`, avant chauffe, trame CFS, moteur filament ou
mouvement d'axe. Le rollback a restauré le propriétaire désactivé et les deux
capteurs sont restés actifs ; le filament initial est donc toujours engagé.

## Décision

Les frontières suivantes deviennent indissociables :

1. **Retrait** : température explicite, géométrie sûre, position cutter
   qualifiée, coupe, rétraction locale de la pointe, retrait/rembobinage,
   vérification des deux capteurs.
2. **Chargement** : route et température explicites, chargement, vérification
   des deux capteurs, puis purge immédiate dans le vrai bac.
3. **Décrochage** : après la purge, exécuter `3 à 4` allers-retours francs sur
   le mécanisme du bac. Le trajet part des coordonnées déjà qualifiées : purge
   autour de `X185,5 Y305 Z30`, approche sûre par `X203 Y273 Z32`, puis carré
   `X203..206 / Y304..305 / Z32`. La cadence exacte du successeur devra rester
   dans l'enveloppe physique déjà qualifiée et être relue avant pose.
4. **Preuve** : une image caméra nette doit confirmer que la boule est tombée
   et que rien ne pend sous la buse. Une phase logicielle ou un capteur filament
   ne remplace pas cette preuve.
5. **Géométrie** : aucune référence Z, palpation ou calibration de mesh n'a lieu
   après insertion, chargement ou purge. Toutes les mesures de contact sont
   terminées avec buse propre avant cette frontière.

Le cas « bon filament déjà engagé et conservé » reste distinct : il ne va pas
au cutter et ne retire pas le filament, mais il exige quand même une purge de
preuve avant impression. Dès qu'un retrait est demandé, le cutter redevient
obligatoire.

Aucune nouvelle gate physique ne doit isoler un chargement de sa purge ni un
retrait de sa coupe. Le prochain candidat est d'abord entièrement construit et
testé hors imprimante comme une chorégraphie intégrée. Il doit aussi résoudre
la remise à `1` d'`auto_refill` au restart sans rouvrir les grosses commandes
stock.

## Conséquences

- V1 est close KO et son exécuteur est rendu non appelable.
- La règle « aucun cutter dans la V1 directe » d'ADR-036 est remplacée.
- Les `24/24` scénarios du moteur direct restent une preuve de protocole, pas
  une autorisation d'utiliser seuls ses retraits physiques.
- La prochaine interface quotidienne reste un seul parcours K1 Control ; elle
  ne demande pas à Thomas de recomposer manuellement cutter, retrait, purge et
  décrochage.
- Toute purge ou activité filament invalide la confirmation précédente de buse
  propre pour une future palpation.

## Alternatives refusées

- **Essayer d'abord le retrait direct sans cutter** : ne correspond pas au
  fonctionnement physique demandé et peut tirer une pointe chaude dans tout le
  chemin.
- **Charger sans purger pour ne tester que les capteurs** : laisse une matière
  non stabilisée dans la buse et ne prouve ni le débit ni le décrochage.
- **Faire la purge sans caméra** : ne prouve ni sa position dans le bac ni la
  chute de la boule.
- **Demander à Thomas plusieurs commandes séparées** : recrée la fragmentation
  que le cycle autonome doit précisément supprimer.

## Preuve liée

- capture privée :
  `20260831-132914-g4-k1-control-cfs-direct-owner-physical-load-unload-v1` ;
- résultat :
  `packages/k1-control-v1/cfs-direct-owner-physical-load-unload-v1/RESULT.md` ;
- géométrie du bac : `CLEAN-MOTION-V1`, verdict humain `E4 OK` ;
- caméra : `docs/49-pilotage-camera-simple-et-autonome-v1.md` ;
- ordre calibration/insertion : ADR-034.
