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
combinaisons doivent passer les contrôles du navigateur, du serveur et de
l'agrégation de six matrices. La campagne physique ci-dessous reste volontairement
sur le niveau rapide `6 × 6` : elle prouve une fois le parcours matériel complet
sans prétendre avoir répété quatre campagnes longues. Les niveaux supérieurs ne
sont donc pas qualifiés physiquement par cette seule gate.

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

1. Vérifier `API connectée` et les valeurs `55 °C`, `140 °C`, `200 s`, `6 × 6`,
   `Lagrange` et le seed automatiquement repris à `−0,04 mm`.
2. Cocher le remplacement de la référence existante et confirmer la plaque
   libre, puis lancer le mesh.
3. Attendre exactement six mesures. Aucun septième passage et aucun rerun ne
   sont permis. Le résultat doit être `Qualifié` avec les trois métriques sous
   leurs limites.
4. Même après fermeture/réouverture éventuelle de la page, retrouver les
   paramètres de campagne. Reconfirmer le plateau libre et la buse propre.
5. Commencer le Z à `5 mm`, puis franchir un par un les paliers `2`, `1`, `0,5`,
   `0,3`, `0,2`, `0,15` et `0,1 mm`.
6. Au dernier palier, utiliser la cale papier réelle d'environ `0,09 mm` et les
   seuls ajustements proposés par l'interface. Ne confirmer qu'après observation
   d'un jeu sûr et perceptible.
7. Confirmer le jeu, vérifier la remontée, puis enregistrer le Z depuis l'écran.

## OK final

L'écran affiche `Calibration acceptée`, l'API reste connectée, la phase vaut
`accepted`, les six meshes sont qualifiés et le backup de campagne existe. Le
contrôle indépendant doit ensuite confirmer le profil attendu, le stockage Z
`ok`, `accepted_z_valid=1`, la session et les mouvements bas désarmés, le chemin
`committed`, `standby`, les deux cibles à zéro et deux CFS connectés.

## KO et retour sûr

Au premier écart, Thomas utilise `Annuler la calibration` depuis l'écran. Une
fois l'opération bornée terminée, il utilise `Restaurer avant cette calibration`
et confirme la boîte de dialogue. Aucun rerun automatique n'est accepté. Une
intervention console ou Codex pour terminer la campagne invalide la preuve
d'autonomie, même si l'état matériel final paraît correct.

Le script local `scripts/validate-k1-control-calibration-ui-campaign-v1.ps1`
fournit `Plan`, `Preflight` et `Validate`. Ses deux actions connectées restent
strictement en lecture seule : empreintes, API métier, état privé de campagne et
état Klipper. Elles enregistrent les captures complètes uniquement sous
`inventory/raw/`, ignoré par Git.
