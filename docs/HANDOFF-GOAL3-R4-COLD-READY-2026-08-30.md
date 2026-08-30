# Handoff — Goal 3, R4 prêt à froid

Date : 2026-08-30
Projet : `C:\Users\janko\Documents\ChatGPT\k1-max-cfs-root-toolkit`
Nouvelle tâche créée : non
Nouveau Goal Codex : absent

## Résultat utile

Le successeur réel de R3 est prêt hors imprimante. R4 applique l'ordre physique
confirmé par Thomas sans imposer le cycle complet à chaque travail. Si la
géométrie est encore valide, il garde `T1A` et ne palpe pas. Sinon : buse propre
et aucune route CFS pendant toutes les palpations, puis insertion officielle de
`T1A`, puis départ sans nouvelle palpation.

Après insertion, le chemin R4 contient zéro `G28`, zéro `ACCURATE_G28`, zéro
`BED_MESH_CALIBRATE` et zéro `CX_PRINT_LEVELING_CALIBRATION`. Il recharge le
profil `11 × 11` et le Z accepté sans mesure, puis chauffe, purge dans le bac,
fait le décrochage E4, attend la caméra, amorce hors plateau, attend une seconde
image et rend enfin la main au modèle.

## État réel confirmé une seule fois

Thomas a remis le `11 × 11` en un clic dans Mainsail. Une unique lecture passive
a confirmé :

- `standby`, chauffes demandées à zéro ;
- `T1A` seul engagé, commande CFS vide ;
- `k1_p001_t055_r001_n11x11` actif ;
- Z accepté `−0,04 mm` ;
- propriétaire au repos ;
- parc haut qualifié.

Cette restauration est consommée. Ne pas refaire un préflight identique avant
un changement réel de la machine.

## Preuves froides

- vérificateur R4 dédié vert ;
- `20` blocs Jinja parsés par le Python exact de la K1 via stdin ;
- aucun fichier distant, G-code, chauffage, mouvement, extrusion, ordre CFS ou
  service pendant cette validation ;
- déployeur en mode plan vert avec empreintes figées ;
- backup exact, rollback automatique, vraie transition du socket Klipper,
  remise unique du `11 × 11` et autotest froid du surveillant prévus.

Le Goal 3 reste honnêtement à `2/7`. R4 n'est ni posé, ni essayé physiquement,
ni validé en production.

## Prochaine action unique

Poser R4 à froid. Concrètement, Codex sauvegarde puis remplace un seul fichier
de macros, redémarre seulement Klipper, remet le `11 × 11`, vérifie l'état et
déclenche un autotest du surveillant qui ne chauffe et ne bouge rien. Au premier
écart, l'ancienne version est restaurée automatiquement.

Cette pose modifie la configuration active de la K1 ; elle exige donc une
autorisation explicite portant sur cette pose précise. Elle n'autorise pas
l'essai chaud. L'essai physique ultérieur commencera par le chemin court
actuellement possible : nettoyer la buse, garder `T1A`, vérifier la géométrie
sans mesure puis démarrer. Le désengagement, la palpation et la réinsertion par
les clics officiels ne seront demandés que si la géométrie a réellement été
perdue. Les contrôles caméra et l'arrêt restent à la charge de Codex.

Modèle conseillé pour la pose froide : `gpt-5.6-terra` en raisonnement `high`,
car le changement est étroit mais touche une K1 réelle et doit vérifier le
rollback. Option économique acceptable : `gpt-5.4` en `high` ; le compromis est
une reprise moins sûre si l'état réel diffère du manifeste. Pour l'essai chaud
avec caméra, reprendre `gpt-5.6-sol` en `high`.

La tâche source reste visible et ne doit pas être archivée.
