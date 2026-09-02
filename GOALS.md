# GOALS — pilotage macro

Date de mise à jour : 2026-09-01

Ce fichier sert d'index rapide pour les grandes sessions de travail. Les noms
ci-dessous regroupent les petites gates déjà définies dans `GATES.md` ; ils ne
les remplacent pas et n'autorisent aucune action sur la K1 par eux-mêmes.

Ce document ne crée aucun Goal Codex. Le compteur canonique reste fermé à
**quatre Goals pour terminer le projet** : aucun cinquième Goal obligatoire ne
sera ajouté. Les Goals 1 et 2 sont clos. ADR-029
établit qu'aucun profil actuel n'est robuste : tous ont des défauts de bord. Le
`11 × 11`, meilleur profil observé, est actif et revérifié. CLEAN-MOTION-V1 est
clos OK après les validations humaines C, D1, D2, D3, E2, E3-R2 et E4. ADR-030
ferme ensuite le nettoyage automatique en KO et rend le nettoyage manuel
obligatoire. Le Goal 3 compte désormais deux exigences résolues sur sept. Le
run thermique R5 est clos KO : la purge n'est pas tombée dans le bac, le
mouvement de décrochage n'a pas eu lieu et la référence Z n'est pas fiable
physiquement. ADR-033 et le document 49 rendent désormais la caméra obligatoire.
ADR-034 ferme ensuite R3 : toute palpation doit précéder l'insertion. Son
successeur R4 est installé et validé à froid avec le `11 × 11`, sans chauffe ni
mouvement. La V1 physique directe T1A est ensuite close KO avant effet. Le
propriétaire stock-derived actif et ses correctifs ont depuis été installés. La
purge lit maintenant le G-code et utilise `140 mm` au chargement initial, au
lieu des `30 mm` insuffisants de la reprise. Le capteur cutter est désormais
**qualifié bon** : `BOX_CUT_HALL_TEST` le fait passer par `1` puis `0` avec
zéro échec de relâchement. ADR-041 établit que `box.cut_pos` ne reflète jamais
ce capteur et retire la garde d'ADR-040 fondée sur lui. ADR-042 recadre le
périmètre produit : la bascule Orca quitte le chemin critique et le Z accepté
doit devenir un attribut du profil de mesh. `T1A` reste engagé ; son retrait
est la prochaine action physique.

## Besoin produit — formulation canonique de Thomas

Cette section fait autorité sur le périmètre. Elle a été dictée par Thomas le
1er septembre 2026 et corrige le pilotage précédent (voir ADR-042).

Le problème d'origine : les firmwares K1 Max, kit CFS et CFS produisent des
séquences d'impression longues et imprévisibles, avec des dérives de
température, de mesh et de Z liées à la séquence et au calibrage.

Ce que le système doit faire, par ordre de priorité :

1. **Mesh par température de plateau.** Des mesh calibrés par bande de
   température, et au lancement d'une impression le bon profil se charge
   automatiquement d'après la température de plateau du G-code.
2. **Températures respectées.** Les températures filament du G-code sont
   appliquées au chargement CFS et à l'impression, sans parasitage.
3. **Démarrage propre.** Une séquence de départ sans palpage Z parasite,
   pour que le Z redevienne prédictible.
4. **Changement de filament.** Couleur, matière, ou fin de bobine avec relève
   automatique sur une bobine compatible détectée par le CFS.
5. **Z-offset par profil.** Il se calibre en imprimant un grand carré
   (`280 × 280`), se règle à la main sur la machine, et s'enregistre **dans le
   profil** pour être rechargé avec le mesh correspondant.
6. **Édition point par point du mesh**, à la main, notamment sur les bords.

Contraintes explicites :

- les calibrations de mesh se font **sans filament inséré** ;
- le nettoyage de buse est **manuel** et le reste ;
- le `11 × 11` demande la méthode spéciale d'ADR-011 : la machine s'arrête
   d'elle-même vers 36 points de palpage sans elle ;
- un seul profil existe aujourd'hui, `k1_p001_t055_r001_n11x11`, pour un
   plateau à `55 °C`, et il a dérivé : une recalibration est due.

Hors périmètre V1, explicitement :

- l'envoi direct des fichiers depuis Orca et tout déclenchement piloté par le
  slicer sont **V2**, non prioritaires, et ne conditionnent pas la clôture.

## Vue rapide

| Ordre | Grand Goal | État | Résultat concret attendu |
| --- | --- | --- | --- |
| 1 | `GOAL-P4-OFFLINE-CYCLE-CFS-V1` | terminé hors imprimante | système logiciel complet simulé et plan futur inerte vérifié |
| 2 | `GOAL-P4-K1-READ-ONLY-QUALIFICATION-V1` | terminé en lecture seule ; écart de mesh alors observé, corrigé par une gate distincte | réponses et délais réels qualifiés sans commande ni impression |
| 3 | `GOAL-P4-PHYSICAL-SLICES-QUALIFICATION-V1` | en cours ; `2/7`, purge G-code corrigée, capteur cutter qualifié bon par `BOX_CUT_HALL_TEST` (ADR-041) | toutes les fonctions physiques et le profil de bord validés sans fragmenter la chorégraphie réelle |
| 4 | `GOAL-P4-DAILY-PRODUCTION-V1` | prévu après Goal 3 ; bascule Orca retirée du chemin critique (ADR-042) | Z par profil, mesh multi-températures, relève CFS, trois impressions et clôture |

Le registre exécutable
`packages/k1-control-v1/physical-slices-qualification-v1/completion-matrix.json`
fige exactement les sept exigences internes du Goal 3. Il indique actuellement
`2/7` exigences closes. CLEAN-MOTION-V1 a qualifié les géométries à froid. Les
essais chauds suivants ont montré que la brosse du bac recollait le filament et
que la grande brosse restait non convaincante même après huit allers-retours
diagonaux à `F12000`. Thomas a donc choisi le nettoyage manuel obligatoire.
Cette résolution reste attachée à l'identifiant historique de l'exigence : le
KO automatique n'est ni supprimé ni présenté comme un succès. Les actions
automatiques sont désormais bloquées. L'exigence courante est la qualification
CFS. `EMPTY_LOAD/T1A` est passé avec purge visible et retour des chauffes à
zéro. La reprise `KEEP_CORRECT_T1A` a ensuite prouvé que `T1A` restait engagé,
sans transition, sans commande CFS active et sans cible cachée à `220 °C`.
Elle a aussi prouvé que `START_PRINT` remplaçait encore le `11 × 11` par
`default` pendant ses mouvements bas et lançait le mauvais brossage avant que
K1 Control puisse réarmer la géométrie. Thomas a dû nettoyer la buse à la main,
puis corriger temporairement le Z de `−0,04` à `−0,19 mm` pour obtenir une
première couche à peine correcte. Le run R5 du 29 août a ensuite invalidé la
partie « sans brosse » : une purge de bord ne remplace pas la purge dans le bac
ni l'aller-retour qui décroche la boule. L'impression observée très au-dessus du
plateau rend la référence Z de R5 non fiable malgré une télémétrie ordinaire.
ADR-033 impose maintenant un départ possédé avec purge explicite dans le bac,
mouvement E4, deux contrôles caméra bloquants et référence Z précise seulement
après preuve visuelle de buse propre. Son candidat R3 est préparé uniquement
hors imprimante ; le pilote caméra et ses `16` blocs Jinja sont validés à froid
sans effet. Ce registre ne
crée aucun Goal supplémentaire. ADR-032 et la cartographie canonique
`design/cfs-control-source-map-v1.json` réutilisent maintenant les captures
locales, le binaire stock, HelixScreen, FrederickAlt, CFSTool et les principaux
retours K1/CFS. Elles choisissent K1 Control comme unique propriétaire du cycle
au-dessus de petites primitives stock qualifiées séparément. Le changement
automatique vers une bobine identique est conservé dans ce propriétaire. Le
préflight S12 est désormais clos en lecture seule : binaire et chargeur exacts,
commandes, rappels internes, états et deux CFS sont liés à la carte publique.
Aucune primitive d'effet, implémentation ou pose n'est encore autorisée.

## Goal 1 — Terminer le système hors imprimante

Identifiant : `GOAL-P4-OFFLINE-CYCLE-CFS-V1`

État : **terminé hors imprimante**.

Ce qui a été réellement fait :

- construire le transport simulé du garde CFS ;
- couvrir le démarrage, le bon ou mauvais filament, l'absence de filament, les
  changements, le runout, la pause, la reprise, l'annulation et la fin ;
- tester coupures, délais, faux succès et doubles commandes ;
- fixer les règles de nettoyage, de chauffe et d'arrêt thermique ;
- préparer les futurs fichiers d'installation, sauvegardes et retours arrière ;
- fermer les tests, la documentation et Git.

Limite respectée : aucune connexion K1, aucun G-code réel, aucune chauffe, aucun
mouvement et aucun candidat de pose exécutable.

Première mission interne close :
`G4-K1-CONTROL-CFS-STOCK-UNLOAD-GUARD-TRANSPORT-OFFLINE-V1`, `13/13` scénarios.

Résultat : les `27/27` scénarios canoniques sont verts, les tests ciblés du cycle
obtiennent `20/20` et le plan futur épingle trois sources, trois destinations,
les sauvegardes et le rollback sans contenir de commande distante. La suite
complète exécute `476` tests, dont `473` verts et `3` ignorés connus.

Autorité consommée : ce Goal est clos. Il ne donne aucune autorité sur
l'imprimante ni sur le Goal 2.

## Goal 2 — Vérifier le système sur la vraie K1 sans impression

Identifiant : `GOAL-P4-K1-READ-ONLY-QUALIFICATION-V1`

État : **terminé en lecture seule ; l'écart de mesh alors observé est clos par
une gate distincte**.

Ce qui a été réellement fait :

- deux lectures fraîches, nettoyées sur la K1 avant leur retour local ;
- forme de réponse stable et plafond de lecture fermé à `5 s` ;
- lectures d'état mesurées à `199,212 ms` et `235,525 ms` ;
- deux CFS connectés, aucune route engagée, commande vide, chauffes à zéro ;
- Z accepté à `−0,04 mm`, mouvements bas désarmés et configurations exactes ;
- collecteur `GET`, traduction pure et règle d'invalidation du mapping testés ;
- points d'intégration Moonraker préparés sans ajouter de composant.

Vérifications : `32/32` tests ciblés Goal 2 et cycle, puis `488` tests dans la
suite complète dont `485` verts et `3` ignorés connus ; `29/29` scripts
PowerShell relus sans erreur.

Limite : aucune impression, aucun G-code, aucun retrait, aucune chauffe, aucun
mouvement, aucun fichier distant, aucun restart et aucune reconnexion CFS
provoquée.

Résultat historique de la capture : `CLOSED_READ_ONLY_BLOCKED_MESH_DRIFT`. La
K1 utilisait
alors le mesh `default`, dont la matrice différait du profil quotidien
`k1_p001_t055_r001_n06x06`. Une lecture fraîche de fin de session montre
ensuite le composite `k1_p001_t055_r001_n11x11` actif. La cause de ce
changement intermédiaire n'est pas qualifiée. Une gate a chargé à tort le
`6 × 6` sous l'ancienne nomenclature, puis
`G4-K1-CONTROL-BEST-CURRENT-MESH-RESTORE-V1` a remis et revérifié le meilleur
profil actuel `11 × 11`. Le paquet de
lecture seule reste clos ; aucun candidat de pose ou connecteur de commande n'a
été créé dans le Goal 2.

Autorité consommée : ce Goal est clos. Il ne donnait par lui-même aucune
autorité pour changer le profil actif ni commencer le Goal 3 ; ces actions
ont depuis reçu leur autorité distincte.

## Goal 3 — Installer progressivement et qualifier les fonctions physiques

Identifiant : `GOAL-P4-PHYSICAL-SLICES-QUALIFICATION-V1`

État : **en cours ; `2/7` exigences passées ; nettoyage automatique clos KO et
remplacé par une gate manuelle obligatoire ; la conservation réelle de `T1A`
est prouvée ; le départ stock est KO ; START-SEQUENCE-OWNER-V1 a été installé
puis invalidé physiquement par R5 ; R3 est interdit par ADR-034 ; R4 est
installé et validé à froid avec son pilote caméra ; l'architecture
complète CFS est choisie, le préflight S12 est clos
en lecture seule et le cœur propriétaire obtient `21/21` hors imprimante ;
l'observabilité V2 et l'exclusion réelle du propriétaire stock sont closes OK ;
le run thermique R5 est clos KO et sans retry ; la prochaine gate chaude reste
bloquée jusqu'à la résolution de la position physique du filament, son retrait
avant toute palpation, le nettoyage réel de la buse, puis la réinsertion
officielle de `T1A` après la géométrie de contact ; le propriétaire CFS direct
obtient `24/24` et son candidat de pose désactivée `13/13`, mais ce dernier
n'est pas encore installé**.

Le checkpoint C a référencé XYZ, rechargé le `11 × 11`, commandé `Z=50 mm` et
attendu la fin. Un premier faux KO local a confondu la position physique
compensée `50,23 mm` avec la consigne. Aucun mouvement n'a été rejoué ; la
validation corrigée en lecture seule est verte. Thomas a donné
`CHECKPOINT C OK`. Ce checkpoint ne doit pas être rejoué.

D1 a ensuite déplacé une seule fois la tête à froid jusqu'à
`X81 Y280 Z50`, encore `24,5 mm` avant la zone stock déclarée. La machine est
restée froide, au repos, sans route CFS, configurations inchangées et profil
`11 × 11` actif. Thomas a confirmé `D1 OK` et D1 n'a pas été rejoué. D2 a ensuite
approché une seule fois jusqu'à `X81 Y300 Z50`, soit `4,5 mm` avant la zone Y
stock, avec le même état sûr. Thomas a confirmé `D2 OK`, puis D3 a approché une
seule fois jusqu'à `X81 Y303 Z50`, soit `1,5 mm` avant la zone Y stock, et a
été accepté.

Les captures manuelles ont ensuite mesuré la grande brosse autour de
`X66..99 / Y303..307 / Z2` et la seconde autour de
`X203..206 / Y303..305 / Z32`. E2 a validé un balayage réel à froid de la
grande brosse. E3-R2 a resserré l'approche de la seconde, puis E4 a validé son
carré exact `X203..206 / Y304..305`. Le retour final est `X203 Y273 Z32`, les
chauffes sont à zéro, aucune route CFS n'est engagée et le `11 × 11` est resté
actif. CLEAN-MOTION-V1 est donc clos OK.

Ce qui sera réellement fait, une petite tranche à la fois :

- la cartographie en lecture seule du binaire S12, des arguments publics
  corrélés, des callbacks de runout et de l'exclusion du propriétaire stock est
  maintenant close sans effet ;
- le propriétaire direct K1 Control est maintenant implémenté hors imprimante
  contre les trames locales exactes, avec `24/24`, sans recopier les projets
  GPL ;
- son composant installable désactivé, son backup et son rollback exact sont
  préparés avec `13/13` ; l'installer sans trame filament ;
- qualifier le départ avec purge dans le bac, décrochage E4, contrôles caméra
  bloquants et référence Z précise seulement après image propre ;
- qualifier un retrait unique et l'arrêt réel des chauffes ;
- vérifier chargement sans flush stock, changement de filament, runout entre
  les deux CFS, pause, reprise, annulation et fin ;
- reprendre le diagnostic des bords seulement après une route fraîche et une
  purge réellement visible ;
- corriger les bords point par point depuis la source `11 × 11`, puis tester un
  candidat dérivé sans écraser les profils existants.

Limite : chaque tranche conserve ses critères OK/KO. Aucun retry automatique et
aucune poursuite après un KO. Codex pilote les lectures, images, commandes et
arrêts ; Thomas n'intervient que pour un acte matériel réellement nécessaire,
décrit en langage courant, sans texte d'autorisation à recopier.

Fin attendue : toutes les fonctions physiques nécessaires sont validées
séparément et réversibles ; l'ancien démarrage Orca reste encore disponible.
La clôture exige les sept lignes `PASSED` et un audit transversal conforme au
registre ; un test logiciel ne peut jamais remplacer une observation physique.

## Goal 4 — Valider la production quotidienne et clôturer

Identifiant : `GOAL-P4-DAILY-PRODUCTION-V1`

État : **prévu après le Goal 3**. Remplace `GOAL-P4-DAILY-CUTOVER-V1`, dont la
bascule Orca est retirée du chemin critique par ADR-042.

Ce qui sera réellement fait :

- corriger le stockage du Z accepté pour qu'il soit **un attribut du profil de
  mesh**, chargé et vérifié avec lui — préalable à toute campagne
  multi-températures ;
- recalibrer le `11 × 11` avec la méthode d'ADR-011, filament retiré ;
- calibrer une bande de température supplémentaire et prouver que le bon profil
  se charge seul d'après la température de plateau du G-code ;
- établir le Z de chaque profil par le carré `280 × 280`, réglage manuel, puis
  enregistrement dans le profil ;
- brancher l'éditeur de mesh point par point sur la machine ;
- retirer le post-traitement Orca `+0,27 mm`, seule dépendance slicer restante ;
- exercer les deux CFS, un changement de filament et une relève automatique
  sur bobine compatible ;
- redémarrer à froid et exécuter trois impressions consécutives représentatives ;
- confirmer la conservation du Z, du mesh et des configurations après reboot ;
- fermer la documentation, les données privées, Git et la baseline V1.

Fin attendue : fonctionnement quotidien simple, unifié, réversible et validé en
production. Quand ce Goal passe, le projet est **terminé** et aucune gate
obligatoire ne reste ouverte.

Backlog V2, hors clôture : envoi direct depuis Orca, déclenchement piloté par
le slicer, compatibilités communautaires.

## Après les quatre Goals

Il n'existe plus de phase obligatoire P5 ou P6 après le Goal 4. Les éventuelles
compatibilités communautaires ou améliorations futures deviennent un backlog
optionnel, extérieur à la définition de fin du projet. Elles ne peuvent pas
repousser la clôture.

## Démarrage recommandé

Le capteur cutter est qualifié bon (ADR-041). La prochaine action physique est
le retrait intégré `T1A`, puis le nettoyage manuel et une première impression
mono-filament complète de bout en bout — la fondation qui n'a jamais été
obtenue. Le correctif Z-par-profil (ADR-042) vient ensuite, avant toute
recalibration multi-températures.
