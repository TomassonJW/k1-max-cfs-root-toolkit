# COMPOSITE-MESH-V1

Candidat physique borné du mode précision défini par l'ADR-013. La première
sous-grille `5 × 5` est qualifiée ; la campagne complète reste séparée de son
installation sans mouvement et de son futur affichage dans l'interface.

`compose_mesh.py` ne pilote rien. Il reçoit des sous-grilles déjà mesurées et
refuse la fusion si :

- un passage dépasse 36 contacts ;
- les passages ne partagent pas la même session, plaque, chauffe et référence
  d'axes ;
- un redémarrage Klipper est déclaré ;
- une position manque ou n'est pas finie ;
- la divergence d'un recouvrement dépasse `0,05 mm`.

L'entrée de production hors imprimante est `compose_11x11`. Elle impose aussi
l'ordre et la géométrie exacts des quatre partitions : aucune permutation,
borne décalée, taille ou interpolation implicite n'est acceptée.

La preuve réelle du 24 août 2026 a montré que le post-traitement propriétaire
PRTouch échoue aussi sur une grille rectangulaire `5 × 6`, après ses 30
contacts. Le partitionnement corrigé emploie donc quatre quadrants carrés
`6 × 6` qui se recouvrent sur la ligne et la colonne centrales. Il produit 144
contacts pour 121 positions physiques uniques. Les 23 contacts répétés sont
moyennés après estimation d'un seul biais constant par quadrant. La moyenne
pondérée de ces quatre corrections reste nulle afin de ne pas déplacer la
hauteur globale mesurée. Les 21 positions de recouvrement servent de contrôle
et leur écart maximal après alignement doit rester inférieur ou égal à
`0,05 mm`.

La capture réelle R2 contient les 144 contacts. Le firmware a introduit un
biais nord/sud visible avant toute persistance : écart brut maximal
`0,147858 mm`. L'alignement constant fondé uniquement sur les recouvrements le
ramène à `0,043745029 mm`, avec une moyenne `0,013871331 mm`. La reprise dédiée
réutilise ces mesures sans nouvelle chauffe, homing ou palpation.

`render_profile.py` prépare uniquement en mémoire le bloc Klipper généré du
profil `k1_p001_t055_r001_n11x11`. Il exige un unique bloc `SAVE_CONFIG`, le
profil robuste `6 × 6` unique et l'absence du profil cible. Il ne lit ni
n'écrit aucun fichier par lui-même.

`k1_control_composite_mesh_core.py` orchestre ensuite une seule chauffe, un seul
nettoyage et un seul homing pour les quatre passages. Il coupe les chauffes
avant toute persistance, écrit atomiquement le candidat après backup exact,
redémarre Klipper une seule fois, relit les 121 valeurs puis recharge le profil
robuste. Tout échec restaure le backup bit à bit et retire le profil cible.
