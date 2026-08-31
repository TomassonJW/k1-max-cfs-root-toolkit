# ADR-038 — Delta stock, profils thermiques 11 × 11 et cycle atomique

Date : 2026-08-31

Statut : **acceptée hors imprimante ; aucune pose ni action physique autorisée**

## Contexte

Le cycle final ne peut pas recalculer sa géométrie après avoir inséré du
filament : une insertion laisse normalement un résidu sur la buse et fausse une
nouvelle palpation de contact. Le besoin réel couvre aussi plusieurs couples de
températures matière/plateau, un Z canonique associé, les changements de
filament et un retrait final au cutter. Une unique macro de départ et un unique
mesh implicite ne suffisent donc pas.

Les captures locales couvrent maintenant deux cycles complémentaires : une
impression normale mono-filament complète de `37 713 392` octets et une P5 de
`383 733` octets avec un changement unique. Cette dernière montre l'ordre
stock coupe → retour cutter → retrait → chargement → purge à `Y305` →
restauration Z → reprise, puis une fin complète. La seconde tentative P5 s'est
terminée sans pause ni incident CFS remarqué.

La ligne d'amorçage évoquée oralement comme `X0/Y0 → Y120` était incertaine.
La source constructeur déjà capturée prouve plutôt `X0,1/X0,4`, `Y20..180`,
avec deux extrusions de `10 mm`, puis un dégagement relatif de `5 mm`. Cette
preuve locale est retenue ; la valeur `Y120` ne devient pas une commande.

## Décision

1. Le G-code fournit obligatoirement les températures de première couche et la
   route demandée. Ses règles filament complètes ont priorité. Si elles sont
   absentes, un jeu CFS complet peut servir de repli ; un jeu G-code partiel est
   refusé afin d'éviter un mélange silencieux.
2. Un registre sélectionne **exactement** un couple `plateau + température
   plateau + température buse`. Son entrée contient un mesh qualifié `11 × 11`
   et un Z canonique qualifié. Le contact utilise la température de palpage
   déjà retenue de `140 °C`, sans filament. Aucun profil « le plus proche »
   n'est choisi.
3. Si l'entrée exacte manque, le print est bloqué et K1 Control propose le
   parcours séparé de calibration. Cette calibration reste accessible en un
   clic, mais exige filament absent, buse fraîchement nettoyée, références puis
   mesure `11 × 11` et validation du Z.
4. Le cycle quotidien fait ses références X/Y/Z sans filament, puis charge le
   profil et le Z enregistrés sans recalculer le mesh. Après insertion, toute
   palpation et tout `BED_MESH_CALIBRATE` sont interdits.
5. La chorégraphie physique de référence est celle observée dans les traces
   stock. On conserve cutter, bac, ordre retrait/chargement/purge, ligne
   d'amorçage, restauration et fin. Aucun nouveau mouvement ne peut apparaître
   sans preuve locale ou correction explicitement demandée.
6. Chaque retrait forme une transaction indissociable : dégagement, position
   cutter, coupe qualifiée, retrait direct et preuve des capteurs. Chaque
   chargement forme une transaction indissociable : position bac, chargement
   direct, purge, `3 ou 4` allers-retours qualifiés et preuve caméra.
7. La même transaction est utilisée au départ, lors de chaque changement de
   filament et à la fin. Aucun effet opaque `BOX_*` constructeur n'est appelé :
   le journal prouve qu'il force `220 °C` et ne permet pas de supprimer
   sélectivement ses effets cachés. Le propriétaire direct porte néanmoins la
   même chorégraphie stock observée.
8. Après la purge du bac, la ligne d'amorçage reprend le trajet constructeur
   prouvé `X0,1/X0,4`, `Y20..180`. La baisse relative de `5 mm` est une
   correction explicite demandée, pas un mouvement attribué à tort à la macro
   stock, qui finit par de petits mouvements `Z2 / Z0,3 / Z2`.
9. La fin ne fait pas un `G28` complet. Elle dégage la pièce, baisse le plateau,
   coupe et retire le filament, parque la tête, coupe chauffes et ventilateurs,
   puis libère les moteurs.
10. Le roulement automatique vers une bobine de secours reste une fonction du
    produit. Pendant un job possédé, l'auto-remplacement stock est désactivé
    pour éviter deux propriétaires. K1 Control détecte le runout, garde la pause
    verrouillée, choisit exactement une bobine disponible dont l'identité
    approuvée correspond sur référence, matière, couleur, diamètre et recette
    thermique, conserve la cible G-code active, exécute la transaction filament,
    restaure le contexte exact puis reprend. Zéro ou plusieurs candidats laisse
    l'impression en pause ; le simple groupe « même matériau » du firmware ne
    suffit pas sans identité approuvée.

## Conséquences

- Le profil historique `k1_p001_t055_r001_n11x11` et le Z `−0,04 mm` restent
  des preuves utiles, mais ne sont pas automatiquement associés à toutes les
  températures de buse : une entrée thermique exacte doit être qualifiée.
- La future UI quotidienne reste simple : lancer le print. Le choix du profil,
  le cutter, la purge et les contrôles sont internes. L'utilisateur n'a pas à
  recomposer la séquence.
- Le paramétrage d'équivalence des bobines reste utile et visible, mais la
  décision de bascule appartient à K1 Control pendant l'impression.
- La calibration est un parcours séparé, visible et accessible, pas une étape
  cachée du lancement quotidien.
- Le moteur hors imprimante peut tester toutes les transitions, mais il ne rend
  pas la chorégraphie cutter physiquement qualifiée.
- Aucune nouvelle impression de découverte n'est requise. Le futur motif court
  valide le delta final et la réalité caméra, pas les mouvements stock déjà
  capturés.

## Alternatives refusées

- **Repalper après insertion** : le résidu de filament peut fausser le contact.
- **Choisir le mesh thermique le plus proche** : erreur silencieuse non
  quantifiée.
- **Mélanger quelques règles G-code avec des valeurs CFS** : propriété des
  températures ambiguë.
- **Faire un retrait direct sans cutter ou charger sans purge** : cycle
  physiquement incomplet.
- **Faire `G28` à la fin** : mouvement inutile et potentiellement dangereux
  autour de la pièce terminée.

## Preuves liées

- ADR-034 : calibration avant insertion ;
- ADR-037 : cutter et purge indissociables ;
- `CX_PRINT_DRAW_ONE_LINE` dans la capture constructeur ciblée ;
- impression normale complète du 21 août et P5 à changement unique du 20 août ;
- `stock-sequence-delta.json`, carte vérifiable conserver/remplacer/ajouter ;
- géométrie cutter dans la lecture K1 du 24 août ;
- verdict humain `E4 OK` pour la zone `X203..206 / Y304..305 / Z32` ;
- paquet `cfs-cutter-purge-integrated-r2-offline-v1`.
