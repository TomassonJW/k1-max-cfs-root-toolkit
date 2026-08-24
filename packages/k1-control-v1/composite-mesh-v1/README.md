# COMPOSITE-MESH-V1

Prototype strictement hors imprimante du mode précision défini par l'ADR-013.

`compose_mesh.py` ne pilote rien. Il reçoit des sous-grilles déjà mesurées et
refuse la fusion si :

- un passage dépasse 36 contacts ;
- les passages ne partagent pas la même session, plaque, chauffe et référence
  d'axes ;
- un redémarrage Klipper est déclaré ;
- une position manque, est dupliquée ou n'est pas finie.

L'entrée de production hors imprimante est `compose_11x11`. Elle impose aussi
l'ordre et la géométrie exacts des quatre partitions : aucune permutation,
borne décalée, taille ou interpolation implicite n'est acceptée.

Pour une cible `11 × 11`, le partitionnement prévu est `6 × 6`, `5 × 6`,
`6 × 5`, puis `5 × 5`. Il produit 121 mesures physiques distinctes et un
profil bicubique.

`render_profile.py` prépare uniquement en mémoire le bloc Klipper généré du
profil `k1_p001_t055_r001_n11x11`. Il exige un unique bloc `SAVE_CONFIG`, le
profil robuste `6 × 6` unique et l'absence du profil cible. Il ne lit ni
n'écrit aucun fichier par lui-même. L'installation, l'acquisition et la
persistance sur la K1 ne font pas partie de ce prototype et restent interdites
avant la preuve physique SUBGRID-V1 et leur gate dédiée.
