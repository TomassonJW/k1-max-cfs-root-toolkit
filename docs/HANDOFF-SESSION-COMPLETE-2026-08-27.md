# HANDOFF COMPLET — session K1 Max CFS du 27 août 2026

Projet : `C:\Users\janko\Documents\ChatGPT\k1-max-cfs-root-toolkit`

Branche cible : `main`

Nouvelle tâche créée : non

Goal Codex actif : absent

État de reprise : **ATTENDRE_GO**

## Résultat global de la session

Cette session a terminé les deux premiers grands Goals de P4, corrigé l'accès
Mainsail et laissé le dépôt et la K1 dans un état vérifié et reprenable.

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

La dernière lecture live, effectuée après la validation de la passerelle,
montre :

- K1 : `standby` ;
- cible buse : `0.0 °C` ;
- cible plateau : `0.0 °C` ;
- mesh actif : `k1_p001_t055_r001_n11x11` ;
- mesh quotidien requis : `k1_p001_t055_r001_n06x06`.

Le passage intermédiaire de `default` au composite `11 × 11` n'est pas
qualifié. La mission passerelle n'a envoyé aucune commande de mesh. Le profil
robuste est toujours présent mais n'est pas actif. La production reste fermée,
le mode Précision reste caché et aucune impression ne doit être lancée dans cet
état au titre de cette passation.

## Git et preuves

Les commits de mission déjà publiés sont :

- `94c94b17cef3ce8041c1fcc0e71d9f89df303a0b` — retrait du mot de passe et
  déploiement réversible ;
- `528aefff9be1c498ba79bef25b1b84dee8584e62` — état live du mesh consigné.

Avant le commit documentaire final de cette passation, `main` et `origin/main`
étaient alignés, avec une divergence `0/0` et aucun changement étranger. Le SHA
final contenant ce fichier est communiqué dans le compte rendu de clôture.

Vérifications réutilisables :

- passerelle sans mot de passe : **OK** ;
- vrai rendu Chrome/Mainsail : **OK** ;
- Moonraker et Klipper : **OK**, aucun échec ni avertissement ;
- suite automatique finale : **491 tests**, 488 verts et 3 ignorés connus ;
- validation physique ou impression : **non exécutée**, hors périmètre ;
- dépôt après la dernière mutation applicative : **propre et poussé**.

Documents à relire : `HANDOFF.md`, `GOALS.md`, `STATE.md`, `GATES.md`,
`packages/k1-control-v1/k1-read-only-qualification-v1/RESULT.md`, ADR-028 et le
rapport `20260827-gateway-private-lan-no-auth-v1-deployment-report.md`.

## Prochaine mission unique

Identifiant proposé : `G4-K1-CONTROL-ROBUST-MESH-ACTIVATION-V1`.

Résultat attendu : charger uniquement le profil déjà présent
`k1_p001_t055_r001_n06x06`, puis prouver qu'il est actif et que sa matrice
correspond à la version qualifiée.

Contraintes obligatoires :

- lecture fraîche avant effet : `standby`, cibles zéro, aucun travail actif ;
- sauvegarder dans la preuve le profil actif précédent `11 × 11` ;
- une seule commande `BED_MESH_PROFILE LOAD` vers le robuste ;
- aucun chauffage, mouvement, homing, palpage, recalibrage, extrusion,
  impression, fichier distant ou restart ;
- relire immédiatement le nom actif et la matrice ;
- arrêt au premier écart et retour au profil précédent si la commande produit
  un état ambigu.

Cette activation runtime ne nécessite pas Thomas devant la K1, car elle ne
produit aucun mouvement ni chauffage. Elle nécessite néanmoins une nouvelle
mission explicite, car elle modifie l'état actif de la machine. Sa réussite ne
lance pas automatiquement le Goal 3.

Après cette gate seulement, le prochain grand Goal sera
`GOAL-P4-PHYSICAL-SLICES-QUALIFICATION-V1`. Thomas devra alors être présent pour
chaque tranche qui chauffe, déplace, charge, retire, purge ou imprime.

Modèle conseillé pour l'activation du mesh : `gpt-5.6-terra`, raisonnement
`high`. Option économique acceptable : le même modèle en `medium`, avec un
risque supérieur de manquer une incohérence de matrice ou de retour arrière.

## Texte de reprise à envoyer dans une nouvelle session

> `$session-tas` Reprends la passation complète dans
> `docs/HANDOFF-SESSION-COMPLETE-2026-08-27.md`. Vérifie d'abord Git et l'état
> live en lecture seule. N'exécute que
> `G4-K1-CONTROL-ROBUST-MESH-ACTIVATION-V1` : charger une seule fois le profil
> robuste `k1_p001_t055_r001_n06x06`, vérifier le nom actif et la matrice, sans
> chauffe, mouvement, homing, palpage, impression, fichier distant ni restart.
> Ne commence pas le Goal 3 dans la même autorisation.

La tâche source reste visible et ne doit pas être archivée.
