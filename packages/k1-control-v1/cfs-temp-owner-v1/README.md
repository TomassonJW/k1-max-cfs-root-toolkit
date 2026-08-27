# CFS-TEMP-OWNER-V1

Observateur passif pour la troisième exigence physique du Goal 3.

Il enregistre toutes les `0,5 s` les températures, cibles, routes CFS,
commande active, deux capteurs de filament, position, profil actif et Z accepté.
Il ne possède aucun chemin de commande : pas de G-code, mouvement, chauffe,
action CFS, fichier distant ou service.

Les checkpoints prévus sont :

- `CLEANING_PREP` : chargement, petite purge visible et retrait manuels avant
  le second essai de nettoyage ;
- `KEEP_CORRECT` : conserver le bon filament déjà engagé ;
- `EMPTY_LOAD` : charger une route fraîche depuis un chemin vide ;
- `WRONG_CHANGE` : remplacer une matière engagée incorrecte une seule fois ;
- `CROSS_CFS` : observer un cas réel sur le second CFS.

L'observateur ne donne jamais lui-même un verdict physique. Thomas exécute les
actions stock et confirme séparément le résultat visible. Une capture qualifie
seulement les états et transitions réellement observés.

Le programme est envoyé par l'entrée standard SSH et n'est jamais copié sur la
K1. Il utilise uniquement des lectures GET locales Moonraker et les empreintes
des configurations. Les valeurs d'identité comme numéro de série, UUID ou RFID
ne sont ni demandées ni exportées.

La baseline live de cinq secondes est verte : huit lectures, aucune route
engagée, aucune commande active, cibles zéro, deux CFS connectés, capteur tête
actif, capteur après cutter libre, profil `11 × 11` actif, Z `−0,04 mm` et
configurations inchangées. Elle n'a produit aucun effet et ne qualifie encore
aucune transition physique.
