# CALIBRATION-UI-CAMPAIGN-V1

Statut : protocole préparé hors imprimante. Le GO reçu avant la correction des
matrices n'est pas consommé. Cette campagne physique n'est pas autorisée tant
que `CALIBRATION-UI-MATRIX-V1` n'est pas posée, validée et rendue dans le vrai
navigateur, puis que la gate exacte mise à jour
`G4-K1-CONTROL-CALIBRATION-UI-CAMPAIGN-V1` n'a pas été approuvée.

## But

Prouver l'autonomie calibration quotidienne : Thomas réalise toute la campagne
depuis l'écran K1 Control, sans console et sans commande Codex. Codex peut
observer les états en lecture seule et réunir les preuves, mais ne clique pas et
n'envoie aucune action de calibration à sa place.

## Niveaux de matrice réellement couverts

L'interface corrigée expose quatre niveaux : `6 × 6` rapide en Lagrange, puis
`9 × 9` standard, `11 × 11` précis et `15 × 15` expert en bicubique. Les quatre
combinaisons passent déjà les contrôles du navigateur, du serveur et de
l'agrégation de six matrices. La campagne physique qualifie maintenant chaque
niveau avec exactement six meshes réels. Les niveaux standard, précis et expert
s'arrêtent après la preuve du mesh et une annulation sûre depuis l'écran. Le
niveau rapide termine ensuite le parcours Z complet : vingt-quatre meshes au
total, jamais un septième passage sur un niveau.

## Préconditions

- `CALIBRATION-UI-MATRIX-V1` est installée, son dossier est en `0755`, ses
  empreintes sont exactes et son API est en phase `idle` ;
- la page `http://localhost:4409/k1-control/` affiche réellement
  `K1 Control — calibration`, pas Mainsail ni une erreur HTTP ;
- la K1 est en `standby`, cibles à zéro, runtime Z sain et chemin fermé ;
- la plaque `PEI_TEXTURED_A` est installée et le plateau est libre ;
- le profil robuste et le Z `−0,04 mm` de FIRST-CALIBRATION-V2 sont disponibles
  comme point de départ et backup.

## Parcours entièrement écran

1. Vérifier `API connectée`, `PEI_TEXTURED_A`, `55 °C`, `140 °C`, `200 s` et le
   seed automatiquement repris à `−0,04 mm`.
2. Sélectionner `9 × 9 — Standard`. Le bicubique doit être automatique et
   Lagrange inaccessible. Ne pas cocher le remplacement, confirmer le plateau
   libre et lancer exactement six mesures.
3. À `Qualifié`, cliquer `Annuler la calibration`, vérifier les chauffes coupées,
   puis laisser Codex capturer l'état qualifié et fermé en lecture seule. Refaire
   exactement ce parcours en `11 × 11 — Précis`, puis en `15 × 15 — Expert`.
4. Sélectionner enfin `6 × 6 — Rapide` et `Lagrange`, cocher le remplacement de
   la référence existante, confirmer le plateau libre et lancer six mesures.
   Aucun septième passage ni rerun automatique n'est permis à aucun niveau.
5. Après qualification du `6 × 6`, même après fermeture/réouverture éventuelle
   de la page, retrouver les paramètres. Reconfirmer plateau libre et buse propre.
6. Commencer le Z à `5 mm`, puis franchir un par un les paliers `2`, `1`, `0,5`,
   `0,3`, `0,2`, `0,15` et `0,1 mm`.
7. Au dernier palier, utiliser la cale papier réelle d'environ `0,09 mm` et les
   seuls ajustements proposés par l'interface. Ne confirmer qu'après observation
   d'un jeu sûr et perceptible.
8. Confirmer le jeu, vérifier la remontée, puis enregistrer le Z depuis l'écran.

## OK final

L'écran affiche `Calibration acceptée`, l'API reste connectée, la phase vaut
`accepted`, les quatre groupes de six meshes sont qualifiés et chaque capture
intermédiaire existe. Le contrôle indépendant doit confirmer les profils
`n06x06`, `n09x09`, `n11x11` et `n15x15`, le stockage Z
`ok`, `accepted_z_valid=1`, la session et les mouvements bas désarmés, le chemin
`committed`, `standby`, les deux cibles à zéro et deux CFS connectés.

## Enchaînement des preuves locales

Codex crée un seul identifiant
`YYYYMMDD-HHMMSS-g4-k1-control-calibration-ui-campaign-v1` et son dossier privé
ignoré par Git. Avec ce même identifiant, il exécute `Preflight`, puis
`CaptureLevel -Level standard`, `precise`, `expert` et `quick` aux checkpoints
décrits ci-dessus, enfin `Validate`. Ces actions ne contiennent aucune route
G-code et ne font que relire les empreintes, l'API, l'état privé et Klipper.

## KO et retour sûr

Au premier écart, Thomas utilise `Annuler la calibration` depuis l'écran et la
gate s'arrête. Aucun niveau suivant n'est lancé. Aucun rerun automatique n'est
accepté. Un profil déjà qualifié peut rester présent ; aucun profil refusé n'est
persisté. Une intervention console ou Codex pour terminer la campagne invalide la preuve
d'autonomie, même si l'état matériel final paraît correct.

Le script local `scripts/validate-k1-control-calibration-ui-campaign-v1.ps1`
fournit `Plan`, `Preflight`, `CaptureLevel` et `Validate`. Ses actions connectées restent
strictement en lecture seule : empreintes, API métier, état privé de campagne et
état Klipper. Elles enregistrent les captures complètes uniquement sous
`inventory/raw/`, ignoré par Git.
