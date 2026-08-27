# HANDOFF COMPLET — session K1 Max CFS du 27 août 2026

Projet : `C:\Users\janko\Documents\ChatGPT\k1-max-cfs-root-toolkit`

Branche cible : `main`

Nouvelle tâche créée : non

Goal de mission repris : `GOAL-P4-PHYSICAL-SLICES-QUALIFICATION-V1`

État de reprise : **ATTENDRE_PRÉSENCE_HUMAINE_CLEAN_MOTION**

## Résultat global de la session

Cette session a terminé les deux premiers grands Goals de P4, corrigé l'accès
Mainsail, réactivé le robuste quotidien `6 × 6` et laissé le dépôt et la K1
dans un état vérifié et reprenable avant la première tranche physique.

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

La dernière validation indépendante, effectuée après l'activation autorisée,
montre sur deux lectures stables :

- K1 : `standby` ;
- cible buse : `0.0 °C` ;
- cible plateau : `0.0 °C` ;
- mesh actif : `k1_p001_t055_r001_n06x06` ;
- matrice active : `6 × 6`, empreinte `c3c7a2ba…` exacte ;
- Z accepté : `−0,04 mm` ;
- axes : libérés ;
- CFS : `T1/T2` connectés, aucune commande active.

Le passage intermédiaire historique de `default` au composite `11 × 11` n'est
pas qualifié. La mission passerelle n'avait envoyé aucune commande de mesh. La
gate dédiée a depuis remis le robuste qualifié actif. La production reste
fermée et le mode Précision reste caché.

`G4-K1-CONTROL-ROBUST-MESH-ACTIVATION-V1` est close OK. Le préflight frais
`20260827-robust-mesh-activation-v1-authorized-preflight` a confirmé le
`11 × 11` précédent, le robuste `6 × 6` présent, l'état au repos et toutes les
empreintes attendues. La capture
`20260827-robust-mesh-activation-v1-authorized-run` a envoyé une seule fois
`BED_MESH_PROFILE LOAD=k1_p001_t055_r001_n06x06` et obtenu `ACTIVATION_OK`.
Aucun rollback, fichier distant, restart, chauffe, mouvement, homing, palpage
ou impression n'a eu lieu. La capture indépendante
`20260827-robust-mesh-activation-v1-independent-validation` a ensuite confirmé
deux fois le robuste actif et les configurations inchangées.

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
- activation robuste : **OK**, une tentative, aucun rollback ;
- validation indépendante après activation : **OK**, `2/2` lectures ;
- tests ciblés activation et CLEAN-MOTION : **OK**, `22/22` ;
- suite complète : **OK**, `513` tests dont `510` verts et `3` ignorés connus ;
- scripts PowerShell versionnés : **OK**, `32/32` relus sans erreur ;
- validation physique ou impression : **non exécutée**, hors périmètre ;
- dépôt avant cette clôture documentaire : **propre et poussé**.

Documents à relire : `HANDOFF.md`, `GOALS.md`, `STATE.md`, `GATES.md`,
`packages/k1-control-v1/robust-mesh-activation-v1/RESULT.md`,
`packages/k1-control-v1/clean-motion-v1/RESULT.md` et le document 42.

## Prochaine mission unique

Identifiant figé : `G4-K1-CONTROL-CLEAN-MOTION-V1`.

Le préalable du mesh est satisfait. Cette première tranche du Goal 3 doit
mesurer à froid la brosse réelle et qualifier une trajectoire sans collision.
Les limites logicielles et la zone stock déclarée X `68…94 mm`,
Y `304,5…306,5 mm` sont connues, mais elles ne prouvent pas la géométrie
physique.

Avant toute commande de mouvement, Thomas doit être devant la K1 et confirmer :

- plateau entièrement libre ;
- brosse réelle visible sans obstacle ;
- possibilité d'observer la buse pendant chaque rapprochement ;
- disponibilité pour donner un verdict après chaque checkpoint.

La gate restera froide : aucune chauffe, extrusion, action CFS, mesure de mesh,
écriture Z, configuration distante, restart ou retry automatique. Toute perte
de visibilité, résistance, bruit inhabituel ou état ambigu impose l'arrêt.

La prochaine action immédiate est donc humaine : aucun agent ni modèle ne peut
remplacer cette observation. Une fois Thomas présent, `gpt-5.6-terra` avec
raisonnement `high` est conseillé pour piloter les checkpoints et les preuves.
L'option `medium` est moins coûteuse, avec plus de risque de reprise si une
observation physique est ambiguë.

## Texte de reprise à envoyer dans une nouvelle session

> `$session-tas` Reprends la passation complète dans
> `docs/HANDOFF-SESSION-COMPLETE-2026-08-27.md`. Le robuste `6 × 6` est déjà
> actif et la gate d'activation est consommée. Attends que je sois devant la K1,
> plateau libre et brosse visible, puis exécute uniquement
> `G4-K1-CONTROL-CLEAN-MOTION-V1` à froid, checkpoint par checkpoint, avec arrêt
> immédiat au premier doute. Ne chauffe, n'extrude et ne lance aucun CFS.

La tâche source reste visible et ne doit pas être archivée.
