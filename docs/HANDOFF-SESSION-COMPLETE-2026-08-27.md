# HANDOFF COMPLET — session K1 Max CFS du 27 août 2026

Projet : `C:\Users\janko\Documents\ChatGPT\k1-max-cfs-root-toolkit`

Branche cible : `main`

Nouvelle tâche créée : non

Goal de mission repris : `GOAL-P4-PHYSICAL-SLICES-QUALIFICATION-V1`

État de reprise : **CHECKPOINT_C_HUMAIN_OK_PRÉPARER_RAPPROCHEMENT_SUIVANT**

## Résultat global de la session

Cette session a terminé les deux premiers grands Goals de P4 et corrigé l'accès
Mainsail. Une interprétation ultérieure a chargé à tort le `6 × 6` comme profil
« robuste ». ADR-029 corrige la nomenclature : tous les profils actuels ont des
défauts de bord, aucun n'est robuste et le `11 × 11` est le meilleur profil
observé. `G4-K1-CONTROL-BEST-CURRENT-MESH-RESTORE-V1` l'a remis actif et
revérifié avant la première tranche physique.

### Goal 1 — système complet hors imprimante

`GOAL-P4-OFFLINE-CYCLE-CFS-V1` est clos hors imprimante. Le transport simulé du
garde CFS obtient `13/13`, le cycle complet `27/27` et les tests ciblés du moteur
`20/20`. Le moteur couvre démarrage, filament correct, absent ou incorrect,
changement, runout, pause, reprise, annulation, reboot, fin et retrait séparé.

Le plan futur épingle les sources, destinations, sauvegardes et retours arrière,
mais ne contient aucun connecteur K1 ni aucune commande distante. Cette preuve
n'autorise ni installation ni production.

### Goal 2 — qualification réelle strictement en lecture seule

`GOAL-P4-K1-READ-ONLY-QUALIFICATION-V1` est clos. La capture privée retenue est
`20260827-142853-goal-p4-k1-read-only-qualification-v1`.

Deux lectures nettoyées et stables ont confirmé Klipper prêt, la K1 en
`standby`, les cibles à zéro, les deux CFS connectés, aucune route engagée, le Z
accepté à `−0,04 mm` et les empreintes exactes. Les lectures ont pris
`199,212 ms` et `235,525 ms`, sous le plafond fermé de `5 s`.

Le statut final du Goal reste `CLOSED_READ_ONLY_BLOCKED_MESH_DRIFT`. Sa capture
observait `default` actif au lieu du robuste requis
`k1_p001_t055_r001_n06x06`. Aucun G-code, fichier distant, restart, chauffe,
mouvement, retrait ou impression n'a été produit.

### Suppression du mot de passe Mainsail

`G4-K1-CONTROL-GATEWAY-PRIVATE-LAN-NO-AUTH-V1` est installé et validé. Le port
`4409` ne demande plus de compte ni de mot de passe.

La frontière restante est réseau : nginx accepte uniquement la boucle locale
et les plages IPv4 privées. Moonraker reste lié à `127.0.0.1:7125`, inaccessible
directement sur le LAN, et reçoit les requêtes du proxy local approuvé. Le
fichier `nginx.htpasswd` reste présent mais inutilisé pour permettre un retour
arrière exact.

L'appel LAN anonyme de `/server/info` est vert. Un vrai Chrome a rendu Mainsail
en `Standby`, sans erreur console. Seul `S57k1_control_gateway` a été rechargé ;
aucun effet physique ni changement de mesh n'a été envoyé pendant cette
mission.

Cette configuration ne doit jamais être exposée par une redirection de port,
une DMZ, un tunnel public ou un Wi-Fi invité non maîtrisé. Tout appareil déjà
présent sur le LAN privé peut maintenant contrôler la K1.

## État réel au moment de la passation

La dernière validation indépendante, effectuée après la correction autorisée,
montre sur deux lectures stables :

- K1 : `standby` ;
- cible buse : `0.0 °C` ;
- cible plateau : `0.0 °C` ;
- mesh actif : `k1_p001_t055_r001_n11x11` ;
- matrice active : `11 × 11`, empreinte `58fd96c5…` exacte ;
- Z accepté : `−0,04 mm` ;
- axes : libérés ;
- CFS : `T1/T2` connectés, aucune commande active.

La mission passerelle n'avait envoyé aucune commande de mesh. L'ancienne gate
d'activation a ensuite chargé le `6 × 6` à partir d'une nomenclature erronée.
Son exécution reste traçable, mais elle ne doit pas être rejouée. La correction
a rechargé une seule fois le `11 × 11`, sans chauffe, mouvement, fichier,
restart, homing, palpage ni impression. Deux lectures indépendantes confirment
le résultat. La production reste fermée et le mode Précision reste caché.

Historique : `G4-K1-CONTROL-ROBUST-MESH-ACTIVATION-V1` est techniquement close
OK, mais son interprétation produit est annulée. Le préflight frais
`20260827-robust-mesh-activation-v1-authorized-preflight` a confirmé le
`11 × 11` précédent, le robuste `6 × 6` présent, l'état au repos et toutes les
empreintes attendues. La capture
`20260827-robust-mesh-activation-v1-authorized-run` a envoyé une seule fois
`BED_MESH_PROFILE LOAD=k1_p001_t055_r001_n06x06` et obtenu `ACTIVATION_OK`.
Aucun rollback, fichier distant, restart, chauffe, mouvement, homing, palpage
ou impression n'a eu lieu. La capture indépendante
`20260827-robust-mesh-activation-v1-independent-validation` a ensuite confirmé
deux fois le `6 × 6` actif et les configurations inchangées. La gate corrective
`G4-K1-CONTROL-BEST-CURRENT-MESH-RESTORE-V1` a depuis remis et revérifié le
`11 × 11` exact.

## Git et preuves

Les commits de mission déjà publiés sont :

- `94c94b17cef3ce8041c1fcc0e71d9f89df303a0b` — retrait du mot de passe et
  déploiement réversible ;
- `528aefff9be1c498ba79bef25b1b84dee8584e62` — état live du mesh consigné ;
- `e105e5b` — paquet réversible d'activation du robuste ;
- `cbff064` — cadre hors effet de la première tranche CLEAN-MOTION ;
- `4858b68` — qualification live en lecture seule de ses sources logicielles.

Avant le commit documentaire final de cette passation, `main` et `origin/main`
étaient alignés, avec une divergence `0/0` et aucun changement étranger. Le SHA
final contenant ce fichier est communiqué dans le compte rendu de clôture.

Vérifications réutilisables :

- passerelle sans mot de passe : **OK** ;
- vrai rendu Chrome/Mainsail : **OK** ;
- Moonraker et Klipper : **OK**, aucun échec ni avertissement ;
- ancienne activation `6 × 6` : **exécution OK, classement annulé** ;
- correction vers le meilleur profil `11 × 11` : **RESTORE_OK**, une tentative,
  aucun rollback, validation indépendante `2/2` ;
- tests ciblés activation et CLEAN-MOTION : **OK**, `22/22` ;
- suite complète : **OK**, `513` tests dont `510` verts et `3` ignorés connus ;
- scripts PowerShell versionnés : **OK**, `32/32` relus sans erreur ;
- validation physique ou impression : **non exécutée**, hors périmètre ;
- dépôt avant cette clôture documentaire : **propre et poussé**.

Documents à relire : `HANDOFF.md`, `GOALS.md`, `STATE.md`, `GATES.md`,
`packages/k1-control-v1/robust-mesh-activation-v1/RESULT.md`,
`packages/k1-control-v1/clean-motion-v1/RESULT.md` et le document 42.

## Prochaine mission unique

Identifiant : `G4-K1-CONTROL-CLEAN-AND-REFERENCE-V1`.

CLEAN-MOTION-V1 est clos OK. C, D1, D2 et D3 ont été acceptés, puis deux
captures manuelles ont fixé la grande brosse autour de
`X66..99 / Y303..307 / Z2` et la seconde autour de
`X203..206 / Y303..305 / Z32`. E2 a validé le balayage de la grande brosse,
E3-R2 l'approche resserrée de la seconde et E4 son carré exact
`X203..206 / Y304..305`, avec retour sûr à `X203 Y273 Z32`. Le verdict final
est `E4 OK`. Les chauffes sont à zéro, aucune route CFS n'est engagée, les
configurations sont inchangées et le meilleur profil actuel `11 × 11` reste
actif.

La prochaine tranche doit créer une recette versionnée à partir de cette
géométrie, faire tomber le flux initial dans le réceptacle, observer un
nettoyage à chaud borné réellement efficace, éviter tout essuyage à une
température non qualifiée, lancer une seule référence Z avec buse propre, puis
relire l'arrêt thermique et l'état sûr. La matière réellement présente ou le
slot à charger doit être résolu avant de fixer les températures ; aucun `T0`
ne peut être supposé.

Le registre
`packages/k1-control-v1/physical-slices-qualification-v1/completion-matrix.json`
fige les sept exigences du Goal 3 et retourne actuellement `1/7` close. La
bascule Orca/K1 Control, le reboot à froid, les trois impressions de production
et la clôture finale restent au Goal 4 ; aucun cinquième Goal n'est permis.

## Texte de reprise à envoyer dans une nouvelle session

> `$session-tas` Reprends la passation complète dans
> `docs/HANDOFF-SESSION-COMPLETE-2026-08-27.md`. Le meilleur profil observé
> `11 × 11` est actif ; aucun profil actuel n'est qualifié robuste. Je suis
> devant la K1, plateau libre, brosses visibles, buse observable et arrêt
> immédiat possible. CLEAN-MOTION-V1 est clos avec `E4 OK`; le Goal 3 est à
> `1/7`. Reprends `G4-K1-CONTROL-CLEAN-AND-REFERENCE-V1`, résous explicitement
> la matière ou le slot avant toute température, puis prépare et exécute le
> nettoyage réel et l'unique référence Z par checkpoints humains.

La tâche source reste visible et ne doit pas être archivée.
