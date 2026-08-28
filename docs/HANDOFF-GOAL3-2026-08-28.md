# Handoff Goal 3 — 2026-08-28

## État livré

Le projet conserve exactement quatre Goals. Le Goal 3
`GOAL-P4-PHYSICAL-SLICES-QUALIFICATION-V1` reste en cours avec `2/7`
exigences closes. Le nettoyage automatique est définitivement rejeté au profit
du nettoyage manuel. La campagne CFS est à `1/4` : `EMPTY_LOAD_T1A` est passé,
les trois autres checkpoints restent ouverts.

La preuve `EMPTY_LOAD_T1A` associe une transition unique vers `T1A`, une purge
visible confirmée par Thomas, une cible à `220 °C`, les deux chauffes revenues à
zéro, le profil `11 × 11`, le Z accepté `−0,04 mm` et des configurations
inchangées. Elle est canonique dans
`packages/k1-control-v1/cfs-temp-owner-v1/empty-load-t1a-evidence.json`.

Le premier `KEEP_CORRECT_T1A` est KO avec arrêt sûr. Le fichier Orca initial,
généré le 28 août 2026, avait un Z slicer nul mais commençait par `G28`, `T0`,
puis `START_PRINT`. Pendant la capture, `T1A` est resté sélectionné sans
transition, mais le profil actif est passé de `k1_p001_t055_r001_n11x11` à
`default`; le démarrage était encore dans `T0` à la fin des cinq minutes. Aucun
verdict de première couche n'a été donné. Thomas a annulé depuis l'interface
stock.

La dernière lecture fraîche avant la décision d'éteindre rapportait
`print_stats=cancelled`, chauffes demandées à zéro, profil `default`, commande
CFS résiduelle `T0` et aucune route engagée. L'écran paraissait arrêté. Cela
prouve un état résiduel du chemin stock démarrage/annulation ; cela ne prouve
pas une panne générique du cœur Klipper. Aucun `RESTART`, reboot, chargement,
G-code correctif ou nouvelle impression n'a été envoyé après la décision de
Thomas d'éteindre la K1.

Un fichier corrigé est présent sur la K1 sous le titre
`Languettes_3 LU Bin Fit - Bin-To-Bin Clicking Lite Rail - (5.5 MU Rail)_PLA_4h6m`.
Il n'a pas été lancé. Les lignes critiques ont été vérifiées en lecture seule :
`START_PRINT EXTRUDER_TEMP=190 BED_TEMP=55`, post-traitement Z nul,
`KCTRL_PRODUCTION_ARM PLATE=1 TEMP_BAND=55 PROBE_REV=1 NOZZLE_ID=1 CONFIG_ID=1 X_COUNT=11 Y_COUNT=11`,
puis `M104/M109 S190`; aucun `G28` ou `Tn` ne précède `START_PRINT`. Son hash
distant n'a pas été capturé avant extinction.

## Vérifications

- `EMPTY_LOAD_T1A` : **OK**, preuve humaine et capture technique concordantes.
- `KEEP_CORRECT_T1A` : **KO avec arrêt sûr**, preuve conservée dans
  `keep-correct-t1a-ko-evidence.json`.
- Chauffes après annulation : **OK**, cibles buse et plateau à zéro.
- Retour interne complet : **KO**, état `cancelled/T0`, mesh `default`, aucune
  route engagée.
- Configurations pendant la capture : **OK**, empreintes inchangées.
- Fichier Orca corrigé : **lecture critique OK**, lancement non exécuté et hash
  distant non capturé.
- Validation humaine première couche : **non exécutée**.

## Reprise unique

Résultat attendu : reprendre `KEEP_CORRECT_T1A` sans reproduire l'ancien départ,
puis poursuivre les trois checkpoints CFS. Au premier démarrage de demain :

1. Thomas allume la K1 et attend son repos complet, sans lancer de fichier.
2. L'agent fait un préflight frais en lecture seule : état d'impression,
   commande CFS, routes, chauffes, mesh, Z et empreintes.
3. Si `T0`, une chauffe ou une incohérence persiste, arrêter sans retry et
   diagnostiquer. Ne jamais déclarer automatiquement que « Klipper déconne ».
4. Si l'état est propre, restaurer et revérifier le profil `11 × 11` par la gate
   déjà éprouvée, puis faire recharger `T1A` une seule fois par Thomas.
5. Thomas nettoie manuellement la buse. Recontrôler et épingler le hash du
   fichier `…PLA_4h6m`, lancer une nouvelle capture `KEEP_CORRECT`, puis Thomas
   démarre lui-même le fichier. Exiger : aucune transition de route, purge
   visible, `11 × 11` et Z `−0,04 mm` effectifs avant les mouvements bas.

Interdits : aucun retry automatique, aucune réutilisation du fichier `4h8m`,
aucune supposition `T0=T1A`, aucun Goal 4, aucun profil qualifié « robuste » et
aucune impression si le préflight froid n'est pas vert. Relire `GOALS.md`,
`physical-slices-qualification-v1/completion-matrix.json`, le contrat CFS et
les deux preuves JSON. État de reprise : **ATTENDRE_GO** après allumage humain.

Horizon ultérieur : finir les trois checkpoints CFS, puis les exigences
changement/runout, pause/reprise, fin/désengagement et enfin le profil de bord
point par point avant tout Goal 4.
