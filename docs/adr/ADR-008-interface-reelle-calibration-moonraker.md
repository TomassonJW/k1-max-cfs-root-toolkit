# ADR-008 — Interface réelle de calibration dans Moonraker

Date : 2026-08-22

## Contexte

Mainsail, le runtime `KCTRL_*` et le chemin Z sont installés, mais leur présence
ne rend pas la calibration autonome. Le prototype local savait afficher l'état
et envoyer quelques macros ; il ne permettait pas de choisir tout le contexte,
de conduire les six maillages robustes ni de survivre à la fermeture du
navigateur.

## Options examinées

1. Laisser l'opérateur utiliser la console Mainsail. Refusé : ce n'est pas une
   interface guidée et l'ordre des actions reste contournable.
2. Exécuter toute la campagne dans JavaScript. Refusé : une page fermée peut
   perdre les matrices ou laisser les chauffes actives.
3. Ajouter un second serveur applicatif. Refusé : coût mémoire et surface de
   maintenance inutiles sur cette K1 Max.
4. Ajouter un petit composant au Moonraker déjà épinglé et garder une page
statique. Retenu.

## Décision

`CALIBRATION-UI-V1` ajoute un composant Moonraker original et une page statique
sous `/k1-control/`. Le composant conserve l'état atomiquement, crée le backup
avant chauffe, exécute le protocole robuste côté serveur, coupe les chauffes en
cas d'échec et expose seulement des routes métier bornées. La chauffe et la
stabilisation utilisent une boucle serveur annulable. Une opération physique
Klipper déjà engagée finit avant l'annulation, mais aucun passage suivant ne
démarre.

La page permet de choisir plaque, températures, stabilisation, matrice,
interpolation et seed Z explicite. Elle expose enregistrer, annuler, restaurer le
Z précédent et restaurer tout le backup de campagne sans commande libre. La vue
experte Mainsail reste séparée.

## Conséquences

- fermer la page ne coupe pas le contrôleur de sécurité de la campagne ;
- aucune API G-code arbitraire n'est ajoutée ;
- l'extension dépend de l'API exacte du Moonraker épinglé et doit passer son
  import réel avant pose ;
- la pose de l'interface ne lance aucune calibration ;
- l'autonomie calibration ne pourra être déclarée qu'après pose, test réel de
  l'interface et campagne complète réussie.
