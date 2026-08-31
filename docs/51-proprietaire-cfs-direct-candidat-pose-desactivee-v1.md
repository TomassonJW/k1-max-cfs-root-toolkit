# Propriétaire CFS direct — candidat de pose désactivée V1

Date : 2026-08-31

Statut : **préparé et validé hors imprimante ; non posé ; connexion K1 fermée**

## Ce qui existe maintenant

Le moteur direct `24/24` possède désormais un véritable adaptateur Klipper et
un déployeur réversible. La configuration livrée fixe `enabled: false`.

Une pose autorisée ajouterait exactement :

- un fichier de configuration ;
- un composant Klipper ;
- un sous-paquet de quatre fichiers qui réutilise exactement le protocole, le
  moteur et l'adaptateur de transport déjà validés ;
- un include dans `printer.cfg` ;
- un seul `RESTART` Klipper, puis la remise du meilleur mesh `11 × 11`.

Elle ne chaufferait pas, ne déplacerait aucun axe, ne toucherait pas au
filament et n'enverrait aucune trame CFS.

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

## Rollback prévu

Le déployeur sauvegarde le `printer.cfg` exact, retire uniquement les six
fichiers ajoutés, restaure le fichier exact, redémarre Klipper et remet une fois
`k1_p001_t055_r001_n11x11`. Le composant et son objet doivent ensuite être
absents.

## Frontière restante

Cette préparation n'autorise toujours aucune connexion ni pose. Après une pose
désactivée réussie, la gate suivante sera une seule qualification physique
`T1A` : réassociation si nécessaire, retrait, chargement puis retrait final,
sans palpage, sans mesh, sans purge et sans retry. La buse ne sera donc pas
utilisée comme capteur pendant cette gate filament.

Le backend Moonraker du cycle intégré ne lit pas encore le nouvel objet Klipper.
Ses effets restent fermés après cette pose. Le raccord des champs de preuve fera
partie de la gate d'activation/qualification, pas de la pose inerte.
