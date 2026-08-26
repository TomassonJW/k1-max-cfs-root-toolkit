# Audit du routage des températures CFS V1

Date : 2026-08-26
Statut : recherche hors imprimante close ; aucune pose ni action K1 autorisée

## Question étudiée

Peut-on inscrire au démarrage d'une impression les bonnes températures dans le
slot CFS choisi afin que le chargement, la purge et l'impression utilisent
directement les bonnes valeurs, y compris lorsque la première couche diffère du
reste de la pièce ?

## Réponse courte

La fiche matière du CFS peut fournir **une température de buse par matière** au
chemin stock. Cela peut éviter le repli observé à `220 °C` si la fiche et la
base locale sont parfaitement synchronisées. Ce mécanisme ne porte toutefois
pas les quatre valeurs nécessaires à une impression complète :

- température de buse de première couche ;
- température de buse normale ;
- température de plateau de première couche ;
- température de plateau normale.

Il ne protège pas non plus la géométrie cachée du chargement stock. La mise à
jour dynamique de la base matière avant chaque travail n'est donc pas retenue
comme propriétaire principal des températures.

## Preuve sur la K1 exacte

La capture privée
`inventory/raw/20260826-cfs-box-wrapper-read-only-audit-v1` montre, pour la
route alors résolue vers `T1A` :

- `material_type: 000001` dans les données du slot ;
- `get material extrusion speed: 2` ;
- `get next material temp: 220` ;
- `flush_temp: 220` ;
- puis une cible réelle de buse à `220 °C`.

Les chaînes du binaire exact contiennent `nozzle_temperature`,
`filament_max_volumetric_speed`, `get_material_target_temp`, `M104` et `M109`.
Elles relient donc le type matière du slot à la base locale
`creality/userdata/box/material_database.json` et à la cible de buse.

En revanche, aucune chaîne ne montre un champ de première couche, une cible de
plateau ou une interface publique par slot équivalente à une recette complète.
Cette absence seule ne prouve pas qu'aucun effet indirect n'existe ; elle suffit
à refuser d'attribuer au mécanisme une capacité non démontrée.

`MODIFY_BOX_CFG` ne documente pas de clé de température par slot.
`Tn_extrude_temp` est un repli global du module, pas un contrat dynamique par
bobine. `BOX_MODIFY_TN_DATA` modifie l'identité déclarée du slot ; l'utiliser
pour détourner une matière vers une autre recette ferait diverger inventaire,
matériel, refill et historique.

## Ce que documente Creality

La documentation officielle décrit, pour un filament sans RFID, l'édition de
la marque, du type, du nom et de la couleur. Elle indique aussi que les données
du slot peuvent inclure une plage de température de buse et la valeur PA. Elle
ne documente pas l'écriture, avant chaque impression, d'un quadruplet
première-couche/normal pour la buse et le plateau.

Le profil officiel courant `Creality K1_CFS-C 0.4 nozzle` transmet séparément
au démarrage `nozzle_temperature_initial_layer` et
`bed_temperature_initial_layer_single`, puis sélectionne l'outil et réaffirme
la cible de première couche. C'est une preuve que le trancheur et le démarrage
du travail portent des valeurs que la seule fiche CFS ne représente pas.

Sources consultées le 26 août 2026 :

- <https://wiki.creality.com/en/software/update-released/Basic-introduction/CFS-tutorial>
- <https://wiki.creality.com/en/cfs/cfs-filament-loading-guide>
- <https://wiki.creality.com/en/cfs/function-work-flow-cfs>
- <https://github.com/CrealityOfficial/CrealityPrint/blob/master/resources/profiles/Creality/machine/Creality%20K1_CFS-C%200.4%20nozzle.json>

## Recoupements communautaires, non assimilés à une preuve K1

Une analyse détaillée sur K2/CFS rapporte que `kvParam.nozzle_temperature`
écrase la cible lors d'un changement d'outil, avec une seule valeur
opérationnelle et sans distinction de première couche. Elle décrit aussi les
risques de cache, redémarrage et resynchronisation de la base. C'est cohérent
avec la capture K1, mais ce n'est pas une preuve de compatibilité directe avec
notre firmware :

- <https://github.com/oliverzein/Creality-CFS/blob/master/docs/2026-07-12-db-temp-override-investigation.md>

Le correctif OrcaSlicer proposé pour réaffirmer `M104` après `T0` protège la
cible finale du travail. Il ne rend pas correcte une chauffe ou une purge déjà
commencée à la mauvaise température :

- <https://github.com/OrcaSlicer/OrcaSlicer/issues/14753>
- <https://github.com/OrcaSlicer/OrcaSlicer/pull/14763>

Une implémentation Klipper ouverte accepte un paramètre `TEMP` à chaque
chargement, retrait et purge. Elle montre qu'un routage explicite est
concevable ; elle ne qualifie ni notre K1 ni nos deux CFS chaînés :

- <https://github.com/gitstonelabs/creality-cfs-klipper/blob/main/configs/cfs_macros.cfg>

## Décision

Le prochain propriétaire reçoit un contrat de travail explicite avec au moins
`NOZZLE_FIRST`, `NOZZLE_NORMAL`, `BED_FIRST` et `BED_NORMAL`. Chaque frontière
CFS reçoit la cible de buse de la phase courante. Le plateau reste une cible
séparée, surveillée sur toute la frontière. Après retour du CFS, les deux cibles
sont vérifiées ; une simple correction tardive ne transforme jamais une phase
incorrecte en succès.

La base matière reste une information et un repli borné. Elle pourra être
alignée statiquement sur une recette qualifiée, mais elle ne sera pas réécrite
globalement à chaque travail sans preuve de relecture à chaud, d'isolation par
slot, de rollback et d'absence d'effet sur le refill.

La propriété thermique ne résout pas la propriété géométrique. La position de
purge candidate reste `X=185,5 / Y=305 / Z=30 mm`; le positionnement, les
références d'axes, le mesh et le Z accepté restent protégés séparément.

## Prochaine mission

`G4-K1-CONTROL-CFS-DYNAMIC-TEMP-ROUTING-V1` commence strictement hors
imprimante. Elle doit comparer et simuler :

1. base matière statique comme filet de sécurité seulement ;
2. réaffirmation post-`T` comme défense, jamais comme propriétaire de purge ;
3. résolution ciblée de la température au moment exact où le CFS la demande ;
4. propriétaire série minimal si aucune interception étroite n'est démontrable.

Elle couvre chargement initial, changement d'outil, refill, runout,
pause/reprise, deux CFS chaînés et retour au filament déjà engagé. Elle produit
un contrat, un simulateur, des tests d'échec et un plan de rollback relu.

Aucune connexion K1, écriture distante, chauffe, homing, mouvement, commande
CFS, purge ou impression n'appartient à cette mission. Une pose ou un essai
physique formera une gate ultérieure, avec autorisation fraîche.
