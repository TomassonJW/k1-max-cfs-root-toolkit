# 106 - Fausse fin de filament T1B, CFS laissé au repos, reprise sauvée

Date : 12 novembre 2026. Impression mono-filament T1B (fichier `el-dorado-tray-2`,
PLA, 4 h 52), environ 150 g déjà imprimés. Conventions des documents 70 et 105 :
**[FAIT]** lu dans un journal ou un fichier, horodaté ; **[HYPOTHÈSE]** cohérent
avec les faits, non démontré ; **[INCONNU]** non observé.

## 1. Ce qui s'est passé

| Heure K1 | Fait |
| --- | --- |
| jusqu'à 06:04:06 | CFS 1 en mode impression (`mode = 2`), état `OK`, toutes les 4 s. Masque `connections` du CFS 1 : `0x02`, la case B est vue. |
| 06:04:09,756 | Réponse d'état du CFS 1 : `FILAMENT_ERR[0x50]`, puis `key839` « no filament detected at box extrude position » `[1, "B"]`. `filament_useup` = 1, `auto_refill` = 0. |
| 06:04:09,788 | `error: printing to pause` ; fichier arrêté à la position 28141069 (Z20,8, X92,816 Y63,605). |
| 06:04:11 et 06:04:16 | Masque `connections` toujours `0x02` (B présent) et état revenu `OK`. |
| 06:04:17 | `recode_err: filament_err, last_tnn: T1B` puis routine stock « extrude all material » à 195 °C. |
| 06:29:54 | `extrude more than 3000` : la routine s'arrête après 3000 mm poussés au bac (la grosse purge vue par Thomas). |
| 06:29:55 | `cmd: SET_BOX_MODE` : le CFS 1 passe au repos, `box.T1.mode` = `"0"`. |

[FAIT] La bobine B n'était pas vide : Thomas l'a vue pleine, chargée jusqu'à la
tête, et l'impression a fini avec elle.

[FAIT] Le CFS 1 lui-même a déclaré l'erreur : ce n'est ni le capteur de tête ni
une décision de Klipper. Le même CFS voyait la case B dans son masque de
connexions 3 s avant et 2 s après. L'erreur porte sur le capteur interne de la
sortie de case (« box extrude position »), pas sur la présence de la bobine.

[HYPOTHÈSE] Lecture fugitive de ce capteur interne (poussière, filament
légèrement décalé, glissement du galet). Déjà vu en fin d'impression sur T1A
(documents 81, 104, 105), c'est la première fois en pleine impression.

[FAIT] `auto_refill` valait 0 à 06:04:09 parce que la garde capteur V1 avait
marqué T1B à 04:25:06 et coupé l'auto-remplacement (ADR-077). À 04:22:06, la
même erreur, auto-remplacement actif, n'avait rien arrêté. La coupe a changé la
fausse erreur en pause et purge : document 107, ADR-078.

## 2. Pourquoi la première reprise imprimait dans le vide

[FAIT] Après sa boucle de 3000 mm, la routine stock remet le CFS au repos
(`mode = 0`). Dans ce mode, le CFS ne donne plus de mou : l'extrudeur tire sur
un filament bloqué, rien ne sort. Thomas l'a constaté à la main : pas de mou du
buffer, filament impossible à pousser.

[FAIT] Les purges à 260 °C (30 puis 150 mm) n'ont rien sorti pour la même
raison. Ce n'était pas une buse bouchée : dès le CFS remis en mode impression,
50 mm à 230 °C sont sortis normalement.

La reprise stock (`RESUME`) ne remet pas le mode impression ; elle relance au
contraire un rechargement `T1A` lu dans `print_file_name.json`
(`tn_cur_tnn`), traduit vers T1B par `kctrl_slot_map`.

## 3. Reprise réellement faite

1. Sauvegarde puis réécriture atomique de
   `/usr/data/creality/userdata/config/print_file_name.json`
   (`print_file_name.json.bak-20261112-reprise-t1b`) : `tn_cur_tnn` vidé, pour
   éviter le rechargement stock à la reprise.
2. Courant extrudeur rétabli (`RESTORE_E_CURRENT`), ventilateurs du fichier.
3. Bac : sortie à Y273 à Z constant avant toute descente (garde du bac,
   ADR-071). Un premier abaissement à Y291,5 a été refusé par la garde, qui a
   coupé les chauffes ; refaites ensuite.
4. **Correctif décisif** : `BOX_SET_BOX_MODE ADDR=1 MODE=PRINT NUM=B`, relu
   `mode = 2`, buffer `middle`. Thomas confirme le mou.
5. Purge 50 mm à 230 °C au bac, sortie confirmée, buse nettoyée par Thomas.
6. 195 °C, sortie à Y273, retour à X92,816 Y63,605 Z20,8, `M83`,
   `SAVE_GCODE_STATE NAME=PAUSE_STATE`, `M26 S28141069`, un seul `RESUME_BASE`.
7. Reprise à 94,4 %, Thomas confirme le dépôt « au bon endroit, impeccable ».

Aucun redémarrage, aucun module posé, aucune impression annulée.

[FAIT] Fin : fichier `complete` à 09:53:24, 100 %. Fin K1 Control V5 :
coupe confirmée, rembobinage `T1B`, `phase = complete`, aucun échec, cibles
zéro à 09:53:50, tête libre (`filament_sensor_2` faux), Klipper `ready`.
`auto_refill` rendu à sa valeur sauvée `0` ; `filament_useup` reste à `1`
(survit au reboot, document 104). Garde de fin active 15 min : pas de poussée
à la main sans `KCTRL_SENSOR_GUARD_RELEASE`.

## 4. À retenir

- Après une erreur CFS en impression, lire `box.T<n>.mode` : `0` = repos, pas
  de mou. Le remettre en impression sur la case engagée avant toute purge ou
  reprise.
- Ne pas conclure à une buse bouchée tant que le CFS n'est pas en mode
  impression.
- Le `key839` d'impression reste une fausse fin tant que le masque
  `connections` voit la case : un vrai bout de bobine fait aussi tomber ce bit.

## 5. Suite proposée

- Garde de reprise : construite hors imprimante le 12 novembre, pas posée
  (`cfs-sensor-guard-v2`, ADR-078, document 107). Elle garde
  l'auto-remplacement actif en impression, ce qui évite la pause, et en pause
  dit la fausse fin et le mode repos sans agir.
- Procédure de reprise en un geste dans K1 Control : vider `tn_cur_tnn`, mode
  impression sur la case engagée, purge courte, retour au point exact.
- Nettoyer le capteur de sortie de la case B du CFS 1.
