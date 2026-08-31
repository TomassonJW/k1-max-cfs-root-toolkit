# Cycle CFS dérivé du stock — candidat de pose désactivée V1

Ce paquet porte les mouvements utiles réellement observés dans la séquence
Creality vers un composant K1 Control séparé. Il ne réutilise aucun effet
opaque `BOX_*` et ne remet ni homing, ni palpage, ni recalcul de mesh après le
chargement du filament.

La configuration livrée garde `enabled: false`. Ce booléen appartient à la
configuration Klipper et n'est pas modifiable avec `SET_GCODE_VARIABLE`.
Pendant cette pose désactivée, les cinq entrées d'effet refusent avant même de
lire leurs arguments. Elles ne lient pas le propriétaire CFS direct et
n'envoient aucune commande.

## Ce qui est préparé

- cutter : approche `X38/Y230`, course jusqu'à la butée `X38/Y304,5`, attente
  du capteur `cut_pos=1`, maintien dans cette position pendant tout le retrait
  direct, puis seulement retour à `Y230` et preuve `cut_pos=0` ;
- chargement au bac `X185,5/Y305/Z30`, purge à température G-code, puis `3` ou
  `4` allers-retours sur `X203..206` en alternant `Y305/Y304` à `Z32` ;
- ligne constructeur exacte `X0,1/X0,4`, `Y20..180`, deux extrusions de
  `10 mm`, suivie d'un `Z+5` relatif qui abaisse le plateau ;
- fin sans nouveau `G28` : dégagement, cutter, retrait direct, parc
  `X203/Y273`, chauffes et ventilateurs à zéro, puis `M84` ;
- garde de roulement : pause verrouillée, une seule bobine de secours et même
  empreinte d'identité approuvée avant la séquence cutter/chargement/purge.
- ticket d'effet consommé avant le premier mouvement : une issue incertaine ne
  peut jamais relancer automatiquement le cutter, le chargement ou la purge.

Le garde de roulement ne remplace pas à lui seul l'orchestrateur : celui-ci
doit calculer l'empreinte à partir de la référence, du matériau, de la couleur,
du diamètre, de la recette thermique et de l'approbation utilisateur, puis
préserver la température et le contexte de reprise.

## Vérifications locales

```powershell
python packages\k1-control-v1\cfs-stock-derived-cycle-owner-install-disabled-v1\run_scenarios.py
python packages\k1-control-v1\cfs-stock-derived-cycle-owner-install-disabled-v1\verify_candidate.py
python -m unittest tests.test_cfs_stock_derived_cycle_owner_install_disabled_v1 -v
pwsh -NoProfile -File scripts\deploy-k1-control-cfs-stock-derived-cycle-owner-install-disabled-v1.ps1 -Action Plan
```

Le déployeur réversible est préparé dans
`scripts/deploy-k1-control-cfs-stock-derived-cycle-owner-install-disabled-v1.ps1`.
Son action `Plan` reste locale ; les autres actions sont fermées par la gate
exacte. Ce paquet n'est pas installé et n'autorise aucune activation. La
prochaine tranche de conception est l'abonnement du composant Moonraker
existant à ces primitives, aux tickets persistants et aux verdicts caméra.
