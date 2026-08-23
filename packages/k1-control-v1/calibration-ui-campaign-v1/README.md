# CALIBRATION-UI-CAMPAIGN-V1

Statut : protocole corrigé après la preuve réelle de la limite PRTouch à 36
points. L'autorisation de session reste ponctuelle ; le contrat persistant reste
fermé par défaut.

## But

Prouver l'autonomie calibration quotidienne : Thomas réalise toute la campagne
depuis l'écran K1 Control, sans console et sans commande Codex. Codex peut
observer les états en lecture seule et réunir les preuves, mais ne clique pas et
n'envoie aucune action de calibration à sa place.

## Matrice réellement couverte

Le pilote propriétaire `prtouch_v2_wrapper.py` de la K1 a levé un `IndexError`
exactement au point 37 d'une demande `9 × 9`. L'interface expose donc uniquement
`6 × 6` en Lagrange. Une calibration normale mesure un seul mesh complet de 36
points. Les six meshes de `FIRST-CALIBRATION-V2` restent la qualification
scientifique initiale déjà validée, pas une routine quotidienne.

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
2. Vérifier la matrice fixe `6 × 6` et `Lagrange`, cocher le remplacement de la
   référence existante, confirmer le plateau libre et lancer un seul mesh.
   Aucun deuxième passage ni rerun automatique n'est permis.
3. Après contrôle du `6 × 6`, même après fermeture/réouverture éventuelle
   de la page, retrouver les paramètres. Reconfirmer plateau libre et buse propre.
4. Commencer le Z à `5 mm`, puis franchir un par un les paliers `2`, `1`, `0,5`,
   `0,3`, `0,2`, `0,15` et `0,1 mm`.
5. Au dernier palier, utiliser la cale papier réelle d'environ `0,09 mm` et les
   seuls ajustements proposés par l'interface. Ne confirmer qu'après observation
   d'un jeu sûr et perceptible.
6. Confirmer le jeu, vérifier la remontée, puis enregistrer le Z depuis l'écran.

## OK final

L'écran affiche `Calibration acceptée`, l'API reste connectée, la phase vaut
`accepted` et l'unique mesh complet est relu. Le contrôle indépendant doit
confirmer le profil `n06x06`, le stockage Z
`ok`, `accepted_z_valid=1`, la session et les mouvements bas désarmés, le chemin
`committed`, `standby`, les deux cibles à zéro et deux CFS connectés.

## Enchaînement des preuves locales

Codex crée un seul identifiant
`YYYYMMDD-HHMMSS-g4-k1-control-calibration-ui-campaign-v1` et son dossier privé
ignoré par Git. Avec ce même identifiant, il exécute `Preflight`, puis
`CaptureLevel -Level supported`, puis `Validate`. Ces actions ne contiennent aucune route
G-code et ne font que relire les empreintes, l'API, l'état privé et Klipper.

## KO et retour sûr

Au premier écart, Thomas utilise `Annuler la calibration` depuis l'écran et la
gate s'arrête. Aucun rerun automatique n'est accepté. Un profil déjà qualifié
peut rester présent ; aucun profil refusé n'est persisté. Une intervention
console ou Codex pour terminer la campagne invalide la preuve
d'autonomie, même si l'état matériel final paraît correct.

Le script local `scripts/validate-k1-control-calibration-ui-campaign-v1.ps1`
fournit `Plan`, `Preflight`, `CaptureLevel` et `Validate`. Ses actions connectées restent
strictement en lecture seule : empreintes, API métier, état privé de campagne et
état Klipper. Elles enregistrent les captures complètes uniquement sous
`inventory/raw/`, ignoré par Git.
