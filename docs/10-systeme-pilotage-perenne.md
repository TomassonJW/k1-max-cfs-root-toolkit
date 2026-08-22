# 10 — Système de pilotage pérenne

Date : 2026-08-22

Statut : **fondation et runtime Z/mesh installés ; interfaces autonomes non atteintes**

## Décision claire

Le résultat attendu n'est pas un macro qui fige `+0,27 mm`. C'est un système
complet que Thomas peut utiliser sans Codex pour les impressions courantes.

Il doit réunir dans un même produit :

- une interface quotidienne simple ;
- une interface experte pour voir le mesh, les macros, les états et les logs ;
- une correction Z réglable pendant une impression de calibration, enregistrée
  seulement sur demande et conservée après les impressions et redémarrages ;
- une invalidation explicite de cette correction lorsqu'une nouvelle
  calibration change la référence ;
- des meshes identifiés par plaque et plage de température ;
- un démarrage paramétrable dont l'ordre de sécurité reste impossible à casser ;
- des températures réellement commandées par le G-code ou Thomas, y compris
  pendant les opérations des deux CFS ;
- un contrat Orca unique pour le départ, la fin et les changements de filament ;
- des sauvegardes, un historique, des contrôles et un rollback compréhensibles.

Le paquet `G4-ZSAFE-START-V1` ne répond pas à ce besoin. Il est rejeté, n'a
jamais été déployé et ne doit plus être proposé.

## Ce que Thomas verra

### Seuils d'autonomie vérifiables

Le projet ne doit plus appeler « terminé » un état qui exige encore la console
ou Codex. Deux sorties distinctes sont suivies :

- **autonomie calibration** : choix plaque, températures, stabilisation,
  matrice et interpolation ; déroulé sûr ; comparaison des mesures ; actions
  enregistrer, annuler et restaurer ; erreurs compréhensibles, le tout sans
  commande manuelle ;
- **autonomie production** : contrat Orca actif, démarrage sûr, Z et mesh
  automatiquement cohérents, ancien `+0,27 mm` retiré, températures des deux
  CFS respectées et travaux ordinaires sans intervention Codex.

État au 2026-08-22 : **aucun de ces deux seuils n'est encore atteint**. Mainsail
`v2.18.2` et le runtime `KCTRL_*` sont installés, mais ils constituent la vue
experte et le moteur, pas encore l'interface quotidienne autonome.

### Écran quotidien `K1 Control`

L'écran principal doit montrer, sans console ni code :

- **Prêt** ou **Bloqué**, avec la raison exacte ;
- plaque choisie et température de plateau prévue ;
- correction Z acceptée, date et contexte de calibration ;
- mesh choisi ou mesh adaptatif prévu ;
- températures demandées et températures réellement actives ;
- outil et CFS concernés ;
- boutons `Calibrer le Z`, `-0,01`, `-0,005`, `+0,005`, `+0,01`,
  `Enregistrer`, `Annuler` et `Restaurer la valeur précédente`.

Une impression normale ne doit demander aucun réglage à chaque fois. Thomas
choisit ses profils dans Orca, envoie le travail et vérifie un état vert.

### Écran expert

Mainsail est le candidat retenu pour la vue experte : carte du plateau,
console, macros, fichiers, courbes de températures, erreurs et historique
technique. Il complète `K1 Control` ; il ne porte pas seul les règles métier de
la K1 Max et des CFS.

L'interface Creality et l'écran de la machine restent installés. Leur fonction
Z actuelle n'est pas la méthode d'enregistrement du nouveau système, car les
traces prouvent que sa séquence de fin annule la correction.

## Règle Z durable

La valeur acceptée n'est pas la valeur interne que l'interface Creality remet à
zéro. Elle appartient à notre propre état, séparé des fichiers constructeur.

### Première calibration ou calibration devenue invalide

1. Thomas choisit la plaque, la buse et la plage de température.
2. `K1 Control` ouvre une session de calibration.
3. Une valeur de départ provisoire est fournie explicitement ; le logiciel ne
   contient aucun `+0,27` caché comme valeur universelle.
4. La séquence sûre prépare la machine et lance le motif de première couche.
5. Les boutons Z modifient uniquement la session en cours.
6. `Enregistrer` crée une calibration acceptée avec sa valeur, son contexte et
   l'empreinte des éléments qui établissent la référence Z.
7. `Annuler` restaure la valeur acceptée précédente sans rien sauvegarder.

### Impressions suivantes

- la valeur acceptée est chargée **après** la référence Z finale et la politique
  de mesh ;
- la fin d'impression, un clic accidentel ou la remise à zéro Creality ne peut
  pas modifier cet enregistrement ;
- un redémarrage ou une coupure ne l'invalide pas ;
- aucune valeur observée en direct n'est sauvegardée automatiquement.

### Quand il faut recalibrer

Le système bloque la production et demande une nouvelle calibration si un
élément capable de changer la référence a changé, notamment :

- nouvelle calibration PR Touch ou calibration système ;
- changement du réglage capteur qui sert à la référence ;
- changement de buse ou de diamètre déclaré ;
- changement de plaque sans calibration compatible ;
- changement d'un fichier ou d'un macro inclus dans l'empreinte Z ;
- état impossible à vérifier après une intervention externe.

Un simple redémarrage n'est pas une raison de perdre un Z validé. Une nouvelle
calibration l'est. L'ancienne valeur reste dans l'historique pour diagnostic et
rollback, mais n'est plus utilisée en production.

## Mesh par plaque et température

Chaque mesh de référence possède au minimum :

- un identifiant de plaque ;
- une plage de température de plateau ;
- la date, le nombre de points et les limites mesurées ;
- l'empreinte de la référence capteur ;
- une mesure de qualité et un état `accepté`, `provisoire` ou `invalide`.

Deux usages sont prévus :

- **mesh de référence complet** : enregistré volontairement pour une plaque et
  une plage thermique ;
- **mesh adaptatif du travail** : calculé autour des objets du G-code et utilisé
  uniquement pour ce travail. Il n'est jamais réutilisé comme profil global.

La version Klipper capturée accepte déjà `MESH_MIN`, `MESH_MAX` et
`PROBE_COUNT`, mais pas le paramètre moderne `ADAPTIVE=1`. L'adaptation doit donc
être produite par notre contrat Orca et nos macros, sans mise à jour générale de
Klipper juste pour cette fonction.

Le contrôle aléatoire stock ne doit plus recréer et sauvegarder silencieusement
un mesh. Une nouvelle mesure ou un nouvel enregistrement est une action visible
dans l'interface.

Un assistant de réglage des vis peut être ajouté avec
`SCREWS_TILT_CALCULATE`, uniquement après validation des coordonnées sur cette
machine et cette plaque. Il guide la correction mécanique ; il ne remplace pas
le mesh ni le Z fin.

## Ordre de démarrage imposé

Les températures, durées, vitesses, limites de zone, stratégie de mesh et
quantités de purge sont paramétrables. Les barrières de sécurité ne le sont pas.

L'ordre cible est :

1. valider le contrat du travail, la plaque, les outils et la calibration ;
2. stabiliser le plateau à la température demandée et préparer la buse à une
   température de référence configurable ;
3. faire la référence grossière nécessaire ;
4. exécuter uniquement le chemin de nettoyage contrôlé et validé ;
5. faire la référence Z finale sur buse propre ;
6. charger ou mesurer le mesh correspondant à la plaque et à la température ;
7. charger la correction Z acceptée, ou la valeur provisoire d'une session de
   calibration explicitement ouverte ;
8. vérifier réellement référence, mesh et correction, puis seulement armer les
   mouvements bas de production ;
9. préparer le CFS et le bon outil avec les températures du travail ;
10. purger selon le profil actif ;
11. imprimer ;
12. terminer sans modifier la calibration acceptée.

Avant l'étape 8, aucune extrusion, purge ou trajectoire basse de production
n'est admise. Seuls la prise de référence et le nettoyage dans une zone validée
sont des chemins bas contrôlés.

## Températures et deux CFS

Le propriétaire est défini par le travail, pas par la base générique CFS :

- démarrage : température du premier outil fournie par Orca ;
- remplacement par un filament équivalent : conserver la cible active ;
- vrai changement d'outil ou de matériau : utiliser la cible du prochain outil
  fournie par le G-code ;
- changement manuel de Thomas : cette nouvelle cible devient la référence
  jusqu'à la prochaine instruction explicite du G-code.

Après chaque appel stock CFS connu, le système compare cible attendue et cible
réelle. Si le module compilé possède un chemin tardif impossible à intercepter,
le lot ne sera pas déclaré compatible : il faudra remplacer uniquement la
couche propriétaire de la température, pas toute la gestion CFS.

La matrice minimale couvre : premier chargement, remplacement équivalent,
changement voulu, changement entre les deux CFS, pause, reprise, annulation,
fin et intervention manuelle.

## Contrat Orca

Le profil final doit être livré sous forme importable, avec les champs exacts
et une version commune avec la partie machine. Il transmet :

- identifiant de plaque ;
- température plateau et températures de chaque outil ;
- premier outil et prochain outil ;
- limites réelles des objets pour le mesh adaptatif ;
- profil de nettoyage et de purge ;
- mode `production`, `calibration` ou `validation haute`.

Les champs départ, fin et changement de filament sont modifiés ensemble avec le
côté machine. Le post-traitement `+0,27 mm` actuel reste présent tant que le
remplacement complet n'a pas passé ses tests. Il n'est pas copié dans le nouveau
profil final.

## Architecture proposée

```text
OrcaSlicer
    | contrat versionné du travail
    v
Moonraker épinglé et sécurisé
    |------------------------|
    v                        v
K1 Control              Mainsail
usage quotidien          vue experte
    |                        |
    +-----------+------------+
                v
état K1 séparé : Z, meshes, profils, historique
                |
                v
macros originaux et wrappers bornés
                |
                v
Klipper/Creality 2.3.5.34 + deux CFS conservés
```

Moonraker et Mainsail ne seront pas installés par un script général. Les
versions, services Buildroot, ports, droits, authentification, consommation
mémoire et rollback seront épinglés et testés pour cette machine. `K1 Control`
utilisera une partie stable et limitée de l'API Moonraker. Son interface reste
statique afin de ne pas ajouter un deuxième serveur applicatif sur les 209 Mio
de RAM mesurés.

## Un produit, plusieurs poses réversibles

Le système est conçu et testé comme un tout, mais posé par morceaux pour qu'un
problème soit attribuable et réversible :

1. API et interfaces en observation, sans changement de démarrage ;
2. état de calibration Z et interface de calibration ;
3. mesh, nettoyage, démarrage et purge sûrs ;
4. propriété dynamique des températures CFS ;
5. profil Orca final et retrait prouvé de l'ancien post-traitement.

Ce découpage n'oblige pas Thomas à régler la machine à chaque impression. Il
sert seulement à éviter qu'une installation défectueuse casse en même temps le
Z, les CFS et l'interface.

## Ce qui reste manuel et ce qui devient automatique

| Manuel | Automatique |
|---|---|
| choisir les bons profils plaque/matière dans Orca | vérifier leur cohérence avant départ |
| lancer une calibration après invalidation | invalider, conserver l'historique et bloquer un état incohérent |
| juger le motif et cliquer sur `Enregistrer` | conserver et recharger le Z accepté |
| agir physiquement sur les vis si nécessaire | mesurer et indiquer le sens/la quantité de correction |
| surveiller la toute première validation d'un nouveau lot | appliquer l'ordre sûr à toutes les impressions suivantes |
| choisir ou confirmer les emplacements CFS | préserver les températures à travers les transitions |

## Preuves hors imprimante exigées

Avant le premier déploiement, le prototype complet doit démontrer :

- aucune valeur Z universelle cachée ;
- sauvegarde Z uniquement par action explicite ;
- persistance après fin et redémarrage ;
- invalidation après nouvelle référence/calibration ;
- impossibilité de purger avant l'armement de sécurité ;
- sélection du mesh par plaque/température ;
- non-persistance des meshes adaptatifs ;
- conservation des températures dans toute la matrice CFS ;
- refus d'un contrat Orca incomplet ou de mauvaise version ;
- sauvegarde, diff, contrôle des empreintes et rollback de chaque pose ;
- coexistence avec l'écran, Creality Web/Print et les deux CFS.

Le contrat exécutable correspondant est dans
`design/production-control-contract.json` et ses contrôles dans
`tests/test_production_control_contract.py`.

Le premier écran local et le moteur d'état pur sont présents sous `prototype/`.
Ils utilisent uniquement des données synthétiques et ne connaissent aucune
adresse d'imprimante.

## État livré et prochaine gate

Le prototype hors imprimante a maintenant réalisé les cinq points annoncés :
pile épinglée, faux Moonraker relié à l'interface et au moteur, 17/17 scénarios
verts, contrat Orca avec fixtures et paquet de fondation préparé.

V1 a reçu son GO, puis son préflight a détecté l'absence de `logrotate` avant
toute mutation. V2 a reçu son GO, atteint un Mainsail fonctionnel par tunnel,
puis a été rollbackée lorsque l'absence de flux de compte Mainsail a rendu son
contrat d'authentification impossible. Les deux noms sont fermés.
La fondation V3, sa correction PATHS-V1 et le runtime Z/mesh sont désormais
installés et validés. Le runtime démarre dans un état vide calibrable, mais garde
sa production fermée sans Z accepté. Il ne remplace encore ni `START_PRINT`, ni
le contrat Orca, ni le post-traitement `+0,27 mm`, ni la propriété des
températures CFS.

La prochaine gate canonique est
`G4-K1-CONTROL-FIRST-CALIBRATION-V1`. Sa préparation hors imprimante doit figer
le contexte de plaque, les températures, la stabilisation, la matrice,
l'interpolation, deux mesures qualifiées, le Z provisoire, l'acceptation et le
rollback. Elle doit également figer le parcours de l'écran autonome, sans faire
passer une exécution en console pour l'UX finale.

Toute chauffe, mouvement, homing, calibration ou écriture persistante attend la
revue complète puis le GO exact de cette gate. Après cette première calibration,
la bascule atomique interface/Orca/`START_PRINT`, la propriété des températures
CFS et G5 resteront nécessaires avant de déclarer le pilotage autonome.
