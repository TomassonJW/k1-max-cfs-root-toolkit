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

La campagne physique réutilise ces lectures en quatre preuves seulement :

1. chemin vide puis chargement manuel unique de `T1A` ;
2. conservation de `T1A` pendant le futur démarrage représentatif ;
3. changement unique de `T1A` vers `T2C`, qui couvre aussi le second CFS ;
4. identité ambiguë bloquée sans effet par l'adaptateur de décision en lecture
   seule désormais prêt.

Les captures des étapes 2 et 3 seront réutilisées pour changement/runout et fin
de travail : elles ne seront pas rejouées uniquement pour remplir deux lignes.

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

La première fenêtre `EMPTY_LOAD/T1A` n'a vu aucune action et reste explicitement
non probante. Thomas a confirmé qu'il n'avait rien déclenché pendant cette
fenêtre, puis que la dernière action réelle avait chargé et retiré `T1A` lors
de la préparation manuelle du nettoyage. Le prochain essai peut donc recharger
ce même `T1A` sous observation, sans attribuer à l'interface un refus non vu.

La reprise `20260828-goal3-cfs-empty-load-t1a-r2` est close OK : une seule
transition vers `T1A`, cible de buse à `220 °C`, purge visible confirmée par
Thomas, puis cibles zéro et configurations inchangées. `T1A` reste engagé pour
le checkpoint suivant `KEEP_CORRECT_T1A`. La campagne physique était alors à
`1/4`.

Le premier `KEEP_CORRECT_T1A` a ensuite échoué proprement avant qualification :
le préfixe Orca historique `G28/T0/START_PRINT` a conservé `T1A` sans transition,
mais a remplacé le `11 × 11` par `default`. Après annulation, les chauffes sont
à zéro mais l'état interne reste `cancelled/T0`, sans route engagée. Thomas a
choisi l'extinction et la reprise à froid. Aucun retry ni restart n'a été lancé.

Le départ possédé a finalement repris ce checkpoint sous la capture
`20260829-goal3-start-owner-physical-keep-correct-t1a-v1-run`. T1A est resté
engagé, la purge est confirmée et deux couches sont bonnes après réglage humain
du Z à `−0,19 mm`. La campagne passe à `2/4`. Le Z accepté `−0,04 mm` reste à
diagnostiquer dans une fenêtre thermique stabilisée avant les autres impressions.

L'adaptateur de décision ne commande rien. Il refuse plusieurs routes, une
commande CFS active, un segment présent dont la route résiduelle n'a pas été
confirmée et toute route engagée dont la matière n'a pas été confirmée. Il
propose `LOAD` lorsque les deux capteurs sont libres, ou lorsque l'opérateur a
confirmé que le segment résiduel vient exactement de la même route demandée.
Une route résiduelle différente reste bloquée. `KEEP` ou `CHANGE` exigent une
identité matière explicite.
