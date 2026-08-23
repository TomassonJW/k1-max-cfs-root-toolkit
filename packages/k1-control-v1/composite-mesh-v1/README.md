# COMPOSITE-MESH-V1

Prototype strictement hors imprimante du mode précision défini par l'ADR-013.

`compose_mesh.py` ne pilote rien. Il reçoit des sous-grilles déjà mesurées et
refuse la fusion si :

- un passage dépasse 36 contacts ;
- les passages ne partagent pas la même session, plaque, chauffe et référence
  d'axes ;
- un redémarrage Klipper est déclaré ;
- une position manque, est dupliquée ou n'est pas finie.

Pour une cible `11 × 11`, le partitionnement prévu est `6 × 6`, `5 × 6`,
`6 × 5`, puis `5 × 5`. Il produit 121 mesures physiques distinctes et un
profil bicubique. L'installation, l'acquisition et la persistance sur la K1 ne
font pas partie de ce prototype et restent interdites sans leur gate dédiée.
