# 62 — Blocage de départ Orca : G28 et T0 avant START_PRINT

Date : 2026-09-05. Correction du profil et copie vérifiée sur la K1 ; essai
d'impression non réalisé.

## Cause prouvée

Les deux départs à 16:21 et 16:43 dans le journal K1 sont interrompus par
`_KCTRL_PROBE_GUARD_ON` : cible buse `220 °C`, plafond de contact `105 °C`.
Le travail demande pourtant `190 °C` et un plateau à `55 °C`.

Le fichier a été tranché par Orca 2.4.2 avec le profil
`Creality K1 Max (0.4 nozzle) - Copie`. Son début exécutable contient :

```gcode
G28
T0
START_PRINT EXTRUDER_TEMP=190 BED_TEMP=55
```

Le journal suit `T0` vers l'emplacement `T1B`, son chargement, puis sa purge
à `220 °C` avant l'entrée dans `START_PRINT`. Notre démarrage tente ensuite
sa référence de hauteur ; la protection refuse la cible encore active.
Un deuxième référencement après insertion serait de toute façon contraire
à ADR-045. Abaisser ou désactiver le plafond n'est donc pas la correction.

## Changement limité

Le champ `machine_start_gcode` du profil **Copie** perd uniquement ses deux
premières lignes. Il devient identique à celui du profil **CopieBIS** déjà
présent, désormais versionné dans
`packages/k1-control-v1/owned-start-print-v2/orca-machine-start.gcode`.
Tous les autres champs du profil sont conservés, vérifiés par comparaison
JSON. Le fichier JSON est modifié uniquement sur la valeur de ce champ.

Sur la K1, une copie distincte porte le suffixe `_KCTRL-fixed.gcode`. Elle
retire uniquement les lignes exécutables 205 et 206, soit sept octets.
L'original reste intact. Une seconde connexion compare indépendamment tous
les octets restants : `50 877 329` octets identiques à partir de `START_PRINT`.
Cela conserve les températures, les changements d'outil ultérieurs, les
volumes de purge, le parcours de la pièce et la fin d'impression.

Aucune définition de macro n'est changée et aucun interpréteur de commande
`Tn` n'est ajouté. Le choix de bobine par la table CFS, le complément de purge
de `120 mm`, le contrôle de présence filament, le chargement du profil de
maillage et de son Z, ainsi que l'armement/désarmement du capteur de fin de
bobine suivent exactement les commandes installées précédemment.

## Vérification sur la machine

La création de la copie est précédée d'un contrôle au repos, répété juste
avant publication. Aucun G-code de contrôle n'est envoyé, aucune chauffe,
aucun mouvement ni redémarrage n'est demandé.

Les huit fichiers protégés conservent leurs empreintes avant/après :
`printer.cfg`, `box.cfg`, `gcode_macro.cfg`, notre `owned-start-print-v2.cfg`,
le garde de température de palpage, les variables Z persistantes,
`kctrl_slot_map.py` et `kctrl_wait.py`. Le Z enregistré du profil `11 × 11`
reste `+0,050 mm` ; il n'est pas remplacé par une ancienne valeur de passation.

Empreintes du travail :

| Objet | SHA-256 |
|---|---|
| Original | `f0476a6303603abaa596ae0521f80dd039f2e42a39763307353875074e27af0c` |
| Copie corrigée | `3a0f373fd2fe86ec65b49fbf425cf01b09ce35edf30dca84613fa9810f3b1524` |
| Partie identique depuis START_PRINT | `85b56d32c1771be7e6ad1461c50495eebc60a98dd4639618e0264f2ff0cc272c` |

La copie apparaît dans la liste des fichiers Moonraker. L'état final observé
reste `error` pour l'ancien travail, impression inactive et cibles de chauffe
nulles. Le filament est encore présent dans la tête. Le maillage actif avait
été effacé par le départ avorté ; le correctif ne le recharge pas manuellement,
car le prochain `START_PRINT` le chargera après sa référence de hauteur.

## Tests et limites

- `64/64` contrôles ciblés du préfixe, de la purge, du choix de bobine, du
  rechargement et de la table CFS passent.
- La suite complète obtient `1 068` tests verts et `55` sous-tests verts,
  avec les deux mêmes échecs déjà inscrits dans la CI :
  `test_unload_requires_head_sensor_to_clear` et
  `test_all_canonical_scenarios_are_implemented_once`. Aucun nouvel échec.
- Deux cas supplémentaires rejouent ensuite la frontière thermique contre
  le vrai modèle Jinja du garde : le préfixe ancien reproduit le refus
  `220/105`, le préfixe corrigé le traverse depuis un état froid. Le dernier
  lot du correctif est `14/14` ; la suite complète n'a pas été relancée pour
  ces deux ajouts isolés.

Ces tests ne simulent pas la mécanique du CFS et ne remplacent pas une preuve
caméra. Le multi-filament et la fin réelle de bobine gardent leurs limites de
qualification antérieures. Aucun de ces essais physiques n'a été effectué.

Le réparateur de copies est volontairement borné au premier outil `T0` et
au préfixe exact observé. Il refuse tout autre préfixe, toute destination
préexistante et toute modification de la source pendant la copie. Un fichier
partiel reste visible pour diagnostic si une copie est interrompue ; il n'est
pas publié comme fichier `.gcode` imprimable.

## Reprise et retour arrière

Pour l'essai, désengager le filament par la commande officielle qui effectue
la coupe, nettoyer la buse manuellement puis confirmer ce nettoyage. Le
départ corrigé conserve sa référence de hauteur ; il ne doit donc pas partir
avec le filament encore engagé après les échecs précédents. Le plateau doit
être libre. Lancer ensuite la **copie corrigée depuis le début**, depuis
l'interface Creality pour conserver le choix visuel de bobine.

Pour les prochains tranchages, recharger le profil Orca corrigé si
l'application était déjà ouverte. Sa mémoire en cours n'a pas été contrôlée.

La sauvegarde exacte et les reçus restent privés, hors Git, sous
`inventory/raw/20260905-owned-start-prefix-fix/`. Le profil précédent est
`orca-Copie-before.json`. Une restauration ne doit se faire que si le profil
en place est encore celui corrigé, pour ne pas écraser une modification de
l'opérateur. L'original du G-code est conservé. Aucune restauration de macro,
de réglage machine ou de service n'est nécessaire puisque ceux-ci n'ont pas
été modifiés.
