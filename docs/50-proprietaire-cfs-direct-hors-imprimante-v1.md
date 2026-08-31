# Propriétaire CFS direct hors imprimante V1

## Pourquoi cette tranche existe

Le premier cycle intégré a prouvé que même une primitive stock présentée comme
petite pouvait reprendre la température, référencer X/Y et vider le mesh. La
version finale ne peut donc plus déléguer le chargement ou le retrait à
`box_wrapper`.

ADR-036 garde uniquement l'infrastructure série déjà fonctionnelle : ouverture
du bus, adresses, enveloppe et CRC. K1 Control possède chaque étape filament,
chaque capteur, la température et l'arrêt au premier écart.

## Sources retenues

La vérité principale vient de deux journaux privés déjà capturés sur cette K1 :

- le chargement local donne les trames capteur, mode, tendeur et étapes
  `0/4/5/6` ;
- le retrait local donne les deux déclencheurs et la traction de pointe
  `−20 mm` à `140 mm/s` ;
- les réponses observées confirment le CRC-8 `0x07`.

Le source officiel `Hi_Klipper` confirme que le transport local reçoit la trame
applicative puis appelle
`cmd_send_data_with_response(frame, timeout, False)`. Les projets publics
gitstonelabs et FrederickAlt servent seulement à recouper la forme générale :
leurs variantes ne remplacent jamais les octets de cette K1 et aucun code tiers
n'est copié.

## Machine d'état retenue

Le chargement exige un chemin tête et après-cutter vide, la présence de matière
sur le slot exact et une température K1 Control déjà atteinte. Il passe ensuite
en mode alimentation, active le tendeur des deux boîtes, exécute `0`, `4`, puis
`5` un nombre borné de fois jusqu'au capteur tête, termine par `6`, exige le
buffer au milieu, fixe la route exacte et désactive chaque tendeur une fois.

Le retrait exige la route exacte et les deux capteurs présents. Il passe en
mode alimentation, lance le retrait vers le buffer, effectue une seule traction
locale, termine le rembobinage puis exige les deux capteurs libres.

Après un redémarrage, une route `T1A` logique perdue peut être réassociée sans
moteur uniquement si les deux capteurs de chemin et le capteur matière du slot
A concordent. Une ambiguïté ferme le cycle.

Tout timeout, statut non nul, CRC invalide, réponse incohérente ou capteur
inattendu mène à `failed_safe`. L'étape incertaine n'est jamais renvoyée. Une
désactivation du tendeur encore nécessaire est tentée une seule fois par
adresse et son éventuelle incertitude reste déclarée.

## Résultat

Le validateur indépendant obtient `24/24`. Il couvre `T1A`, `T2D`, la
réassociation sans moteur, les deux capteurs, les températures, deux cycles
complets successifs, les timeouts, un statut local `0x0c`, les réponses
corrompues et l'absence de retry.

Cette validation ne se connecte pas à la K1 et n'autorise aucun effet. Le
propriétaire direct n'est pas encore installé.

## Suite

La prochaine tranche installe le composant en mode désactivé, sauvegarde les
fichiers exacts, prouve le rollback et démontre que le propriétaire stock ne
peut pas agir en parallèle. Elle ne chauffe et ne déplace aucun filament.

Une seule qualification physique chargement/retrait sous caméra viendra
ensuite. C'est seulement après cette preuve que le cycle intégré pourra être
réessayé.
