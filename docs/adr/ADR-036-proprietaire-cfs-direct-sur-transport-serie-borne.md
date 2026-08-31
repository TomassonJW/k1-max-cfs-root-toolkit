# ADR-036 — Propriétaire CFS direct sur le transport série borné

Date : 2026-08-31

Statut : **décision acceptée ; moteur hors imprimante en cours de qualification ;
aucune pose ni action physique autorisée**

## Contexte

ADR-032 gardait K1 Control comme propriétaire du travail, mais prévoyait encore
d'appeler de petites primitives `BOX_*` du propriétaire Creality. Le premier
essai intégré a invalidé ce choix : `BOX_EXTRUDE_MATERIAL` a imposé `220 °C`,
référencé X/Y, vidé le mesh actif puis échoué sans engager `T1A`.

Les journaux privés déjà capturés sur cette K1 donnent maintenant les trames
applicatives exactes réellement utilisées par le binaire local pour un
chargement réussi, un retrait réussi, les capteurs, le tendeur et l'état du
buffer. Le source officiel `Hi_Klipper` confirme aussi l'interface minimale du
transport déjà installé :
`serial_485.cmd_send_data_with_response(frame, timeout, False)`.

Les projets publics étudiés confirment le CRC, la forme du bus et les grandes
phases, mais leurs propres séquences ou numéros d'étape ne sont pas tous
identiques à cette S12. Ils servent donc de recoupement, jamais de source de
vérité pour un effet physique sur cette machine.

## Options

### Reprendre les macros ou méthodes `box_wrapper`

Rejeté. Même découpées, elles gardent des décisions cachées de chauffe,
référence, mesh, retry et reprise.

### Installer un pilote public complet

Rejeté pour cette version. Aucun candidat public n'est physiquement qualifié
sur cette K1 précise avec ses deux CFS. Copier un pilote GPL ajouterait aussi
une décision de distribution inutile. Aucun code tiers n'est copié.

### Garder uniquement le transport série stock

Accepté. Le transport Creality continue d'ouvrir le bus, de gérer l'adresse et
d'ajouter l'enveloppe `0xF7`/CRC. Il ne décide plus du cycle filament. K1
Control envoie lui-même chaque trame applicative qualifiée, lit chaque réponse
et s'arrête au premier écart.

## Décision

K1 Control possède directement le chargement et le retrait au-dessus de
`serial_485`, avec les règles suivantes :

- routes `T1A..T2D` seulement ; adresses 1 et 2, masques A/B/C/D égaux à
  `1/2/4/8` ;
- température entièrement possédée et prouvée par K1 Control avant la première
  trame ; aucune commande thermique CFS ;
- chargement local observé : capteur matière, mode alimentation, tendeur des
  deux boîtes, étapes `0`, `4`, puis `5` bornée jusqu'au capteur de tête,
  étape `6`, buffer au milieu, mode impression et désactivation du tendeur ;
- retrait local observé : mode alimentation, déclencheur buffer, une traction
  locale de `−20 mm` à `140 mm/s`, puis déclencheur matière et preuve que le
  capteur de tête est libre ;
- aucun cutter n'est appelé dans cette V1 : la seule séquence locale complète
  observée retire le filament par ces deux déclencheurs et la traction locale ;
  si la gate physique ne libère pas tout le chemin, elle ferme la V1 au lieu de
  réintroduire un cutter stock non qualifié ;
- toute trame d'effet porte un identifiant consommable une seule fois ;
- timeout, statut CFS non nul, CRC invalide, réponse incohérente ou capteur
  inattendu ferme le cycle ; aucune étape d'effet n'est renvoyée ;
- la désactivation de sécurité du tendeur est tentée au plus une fois par
  adresse après un chargement incomplet ; son résultat incertain reste déclaré ;
- ce propriétaire ne référence aucun axe, ne modifie aucun mesh ou Z, ne
  purge pas, ne chauffe pas et ne reprend jamais une impression de lui-même.

Les grandes macros `Tn`, `START_PRINT`, `END_PRINT`, ainsi que toutes les
primitives d'effet `BOX_*`, restent exclues du chemin K1 Control. Le composant
stock `box` ne doit plus pouvoir être propriétaire concurrent lors du futur
cutover. `auto_addr` et `serial_485` restent seulement l'infrastructure du bus.

Cette ADR remplace la couche 4 et la liste de primitives candidates d'ADR-032.
Elle ne change pas les règles de géométrie d'ADR-034 ni le cycle cible
d'ADR-035.

## Validation requise

La progression se fait en trois preuves distinctes :

1. validation hors imprimante des octets, de l'ordre, des deux CFS, des
   températures, des erreurs, de l'absence de retry et de plusieurs cycles ;
2. pose réversible du propriétaire direct, encore désactivé, avec exclusion
   prouvée du propriétaire stock ;
3. une qualification physique bornée chargement/retrait, sous caméra, avant
   tout nouvel essai intégré.

La preuve hors imprimante n'autorise ni la pose ni les effets physiques.

## Rollback futur

Le déployeur devra sauvegarder les fichiers exacts, arrêter tout nouveau cycle,
attendre un état sans effet incertain, restaurer les composants stock et leur
configuration exacte, redémarrer seulement les services nécessaires puis
relire chauffes, capteurs, routes, mesh et Z. Un filament dont l'état physique
est incertain devra rester une intervention humaine, jamais une supposition du
rollback.

## Conséquences

Le système reprend enfin le contrôle des températures et supprime les décisions
cachées qui ont invalidé le candidat précédent. Il conserve le firmware des
deux CFS et le transport déjà fonctionnel, ce qui réduit la surface à
requalifier.

En contrepartie, K1 Control doit désormais maintenir une petite machine d'état
matérielle très stricte et sa compatibilité S12. Toute mise à jour du binaire
Creality ou toute réponse nouvelle invalide la qualification jusqu'à une
nouvelle lecture.
