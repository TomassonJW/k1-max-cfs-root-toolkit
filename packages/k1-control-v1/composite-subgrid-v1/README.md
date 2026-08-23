# COMPOSITE-SUBGRID-V1

Premier jalon physique de l'ADR-013. Le composant Moonraker acquiert uniquement
la sous-grille centrale décalée `5 × 5` : positions X/Y `34, 92, 150, 208,
266 mm`, soit 25 contacts PRTouch.

Il impose `PEI_TEXTURED_A`, `55/140 °C`, `200 s` et Lagrange. L'appel exige la
gate exacte et une confirmation fraîche de plateau libre. Il refuse une machine
active, une chauffe existante, un runtime Z ouvert, un CFS déconnecté ou un
profil temporaire.

Après acquisition, la matrice est conservée dans l'état privé du composant. Les
chauffes sont coupées, le profil robuste `6 × 6` est rechargé, le profil
temporaire est retiré et Klipper est redémarré seulement après la capture afin
d'éliminer toute modification de session en attente. Aucun profil composite
n'est persisté.

Ce paquet ne lance pas quatre sous-grilles et ne prouve pas encore le mode
composite `11 × 11` complet.
