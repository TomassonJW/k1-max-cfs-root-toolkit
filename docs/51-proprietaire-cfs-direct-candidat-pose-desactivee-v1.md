# Propriétaire CFS direct — pose désactivée V1

Date : 2026-08-31

Statut : **posé et validé désactivé ; zéro trame CFS ; activation fermée**

## Ce qui existe maintenant

Le moteur direct `24/24` possède désormais un véritable adaptateur Klipper et
un déployeur réversible. La configuration livrée fixe `enabled: false`.

La pose close a ajouté exactement :

- un fichier de configuration ;
- un composant Klipper ;
- un sous-paquet de quatre fichiers qui réutilise exactement le protocole, le
  moteur et l'adaptateur de transport déjà validés ;
- un include dans `printer.cfg` ;
- un seul `RESTART` Klipper, puis la remise du meilleur mesh `11 × 11`.

Elle n'a chauffé ni déplacé aucun axe, n'a touché ni extrudé le filament et n'a
envoyé aucune trame CFS.

## Pourquoi la pose reste inerte

Avec `enabled: false` :

- le composant ne prend pas l'objet `serial_485` ;
- il ne remplace aucune commande stock ;
- réassociation, chargement et retrait refusent avant même leurs arguments ;
- l'autotest vérifie trois refus et publie zéro trame envoyée.

Les `13/13` scénarios hors imprimante couvrent aussi le futur mode actif. Dans
ce mode seulement, les dix-neuf entrées stock connues sont remplacées par des
refus ou constatées absentes. Avant toute trame, le composant exige
`auto_refill = 0`, `t_command` vide et les CFS `T1/T2` connectés.

## Déroulement et rollback prouvé

La première tentative s'est arrêtée avant le premier transfert candidat : le
client SCP Windows utilisait par défaut SFTP, absent de la K1. Le rollback a
restauré le `printer.cfg` exact, confirmé les six fichiers absents, redémarré
Klipper et remis `k1_p001_t055_r001_n11x11`. Le préflight suivant était vert.

Le déployeur force maintenant le mode SCP historique compatible. La seconde
capture `20260831-123137-g4-k1-control-cfs-direct-owner-install-disabled-v1` a
obtenu la pose, sa validation intégrée et deux validations indépendantes.

L'état final est `ready/standby`, cibles zéro, axes libérés, Z `−0,04 mm`,
`11 × 11` actif, `T1/T2` connectés et aucune route logique. Le nouvel objet est
`enabled=false`, `phase=disabled`, ne prend pas le transport, ne remplace aucune
commande stock et publie zéro trame envoyée.

## Frontière restante

La pose est consommée et ne doit pas être rejouée. La gate suivante sera une
seule qualification physique `T1A` : réassociation si nécessaire, retrait,
chargement puis retrait final,
sans palpage, sans mesh, sans purge et sans retry. La buse ne sera donc pas
utilisée comme capteur pendant cette gate filament.

Le backend Moonraker du cycle intégré ne lit pas encore le nouvel objet Klipper.
Ses effets restent fermés après cette pose. Le raccord des champs de preuve fera
partie de la gate d'activation/qualification, pas de la pose inerte.
