# Résultat

Statut actuel : `SAFE_PARK_PREFLIGHT_CORRECTED_OFFLINE_WAITING_RENEWED_EXACT_PHYSICAL_GO`.

Le candidat privé est dérivé du G-code physique déjà qualifié. Sa différence
est uniquement la fin sûre. La stabilisation n'est plus placée dans le fichier
d'impression : le pilote l'exécute avant de créer le jeton humain, dans cet
ordre exact :

- `M140 S55` ;
- `M190 S55` ;
- `G4 P200000` ;
- `M140 S0` ;
- confirmation consommable « buse nettoyée » ;
- départ unique du fichier.

Cette correction évite que le jeton de cinq minutes expire pendant la montée
du plateau et les `200 s`. Elle normalise aussi un ancien état `complete` par
`SDCARD_RESET_FILE` avant tout chauffage, uniquement si nécessaire.

Le vérificateur du candidat, le plan hors imprimante et les sept tests ciblés
sont verts.
L'essai conserve `T1A`, ne permet aucun réglage Z avant le verdict visuel et
n'autorise aucun retry automatique.

Le premier préflight a bloqué sans effet sur le statut terminal sûr `complete`,
puis une double lecture seule a prouvé l'état stable. Le garde corrigé accepte
désormais seulement `standby` sans fichier ou `complete` avec fichier. Le
préflight R2 était vert. Après le retour humain sur la mauvaise fin et le filet
de purge, ce fichier a été invalidé puis supprimé de la K1 sous contrôle de son
empreinte exacte.

Le propriétaire R2 est maintenant installé et validé à froid. Sa purge suit le
tracé constructeur `X0,1/X0,4`, `Y20..180`, à `F3000`, avec remontée `Z5`.
Le candidat local ajoute la fin sûre `Z50 / X203 Y273 / M84`.

Le pilote de l'essai attend désormais l'empreinte R2 exacte. Son arrêt
d'urgence baisse aussi le plateau à `Z50` et parque la tête à `X203 Y273` avant
de libérer les axes lorsqu'ils sont encore référencés. La validation terminale
exige réellement cette position, en plus des chauffes zéro et des axes libérés.

Aucun fichier n'a été renvoyé sur la K1. L'essai attend le rechargement et la
relecture de `T1A`, puis une autorisation physique distincte avec Thomas présent.

Une lecture fraîche de reprise sous la capture
`20260829-resume-read-only-z-thermal-preflight` a été refusée avant tout effet
avec `t1a_route_not_unique`. Elle confirme que le redémarrage a effacé la route
logique et que `T1A` doit être rechargé puis relu avant tout transfert ou essai.

Après l'extinction nocturne, une seconde capture fraîche
`20260829-resume2-z-thermal-preflight-r2` a reproduit ce refus sans effet. Deux
lectures indépendantes ont ensuite établi la cause exacte : les deux CFS sont
connectés, mais `engaged_routes=[]`, tandis que le mesh actif est revenu à
`default`. Le filament peut donc rester physiquement dans la tête sans que la
route logique survive à l'extinction. Le Z accepté `−0,04 mm`, son stockage et
les configurations restent conformes. La reprise exige maintenant un
réengagement stock de `T1A`, puis la gate corrigée
`G4-K1-CONTROL-BEST-CURRENT-MESH-RESTORE-AFTER-POWER-CYCLE-V1` pour le
rechargement à froid du meilleur profil
courant `11 × 11`, avant un nouveau préflight.

Cette reprise est maintenant terminée : `T1A` est la route unique et le
`11 × 11` exact est actif après une gate froide close sans rollback. L'essai
thermique reste séparé, sans upload ni chauffe encore exécutés. Il exige Thomas
présent, plateau libre, buse nettoyée, arrêt immédiat disponible et aucun
ajustement Z avant le verdict visuel des deux couches.

L'autorisation attachée au commit `39a1364` a ensuite été consommée par le
préflight. Le plan local était vert, mais le préflight s'est fermé avant tout
effet avec `axes_not_released`. Aucun G-code, transfert, chauffage, mouvement,
extrusion ou effet CFS n'a été produit. Le garde avait conservé l'ancienne
exigence « axes libérés » alors que la recharge froide venait de qualifier le
parc haut `xyz` exact à `X210 / Y291,5 / Z66,8915`.

La correction hors imprimante accepte désormais seulement deux états initiaux :
axes libérés, ou axes `xyz` dans le parc sûr déjà qualifié `X200..220 /
Y270..300 / Z50..315`. Toute origine partielle, position absente ou position
hors de cette enveloppe reste refusée. Le G-code privé, sa fin sûre et les
effets autorisés ne changent pas. Aucun nouveau préflight live n'a été lancé ;
une nouvelle autorisation exacte sur le commit corrigé reste obligatoire.
