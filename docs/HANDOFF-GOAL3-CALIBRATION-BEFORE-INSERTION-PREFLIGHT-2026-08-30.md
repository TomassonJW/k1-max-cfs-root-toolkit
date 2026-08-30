# Handoff — Goal 3, calibrations avant insertion et préflight sans effet

Date : 2026-08-30
Projet : `C:\Users\janko\Documents\ChatGPT\k1-max-cfs-root-toolkit`
Nouvelle tâche créée : non
Nouveau Goal Codex : absent

## Décision durable

Thomas a confirmé les gestes manuels : buse nettoyée, plateau nettoyé et libre,
`T1A` réengagé avec la fonction officielle, puis buse renettoyée après cette
insertion. Ce dernier geste révèle une règle physique générale : une insertion
laisse un résidu sous la buse et peut fausser une palpation suivante.

ADR-034 impose donc l'ordre final : toutes les références Z, meshes et autres
mesures par contact se terminent avec buse propre et sans filament engagé ; le
filament est inséré seulement ensuite. Un travail qui garde un bon filament
engagé ne repalpe pas. Si une nouvelle mesure devient nécessaire, il doit
désengager, nettoyer, mesurer, puis réinsérer.

R3 est fermé avec
`SUPERSEDED_NEVER_DEPLOY_OR_RUN_PROBING_AFTER_INSERTION`. Son parse Jinja et ses
arrêts caméra restent des preuves froides historiques. R3 ne doit jamais être
posé ni essayé à chaud : il exigeait `T1A`, purgeait, puis exécutait
`ACCURATE_G28`.

## Préflight réel strictement en lecture seule

Capture privée :
`inventory/raw/20260830-calibration-before-insertion-hot-preflight-v1/`.

La caméra a produit une image nette `1280 × 720`. La revue montre la tête haute,
le plateau sans objet d'impression et aucune activité visible. Elle ne prouve
pas la propreté microscopique de la buse ni un bon Z.

Deux lectures d'état stables ont confirmé :

- Klippy prêt, impression `standby`, aucune erreur ni alerte ;
- cibles buse et plateau à zéro ;
- `T1A` engagé, second CFS sans route et commande CFS vide ;
- Z accepté valide à `−0,04 mm`, mouvements bas non armés ;
- configurations inchangées entre les deux lectures ;
- profil `k1_p001_t055_r001_n11x11` toujours présent ;
- mais profil actif `default`, matrice palpée `6 × 6`.

Le verdict est
`CLOSED_KO_R3_SUPERSEDED_AND_ACTIVE_MESH_DRIFT`. Aucun G-code, chauffage,
mouvement, extrusion, ordre CFS, fichier distant, service, pose ou impression
n'a eu lieu.

## Livrables

- ADR-034 et renvoi de l'ADR-033 historique ;
- contrat canonique du cycle et ordre de pilotage corrigés ;
- règle prioritaire ajoutée dans `AGENTS.md` ;
- paquet `calibration-before-insertion-v1` avec contrat, preuve nettoyée,
  vérificateur et tests ;
- R3 transformé en artefact fermé et non exécutable ;
- registre Goal 3 maintenu à `2/7` ; aucune validation physique n'est inventée.

## Prochaine mission unique

La prochaine gate est
`G4-K1-CONTROL-BEST-CURRENT-MESH-RESTORE-BEFORE-R4-V1`.

Concrètement, Codex chargera une seule fois le profil `11 × 11` déjà présent,
puis le relira indépendamment. Ce geste remet la géométrie connue en place ; il
n'effectue aucune palpation et ne touche ni aux chauffes, ni aux axes, ni au
filament, ni à la configuration. Au premier écart, il s'arrête sans retry.

Cette commande modifie l'état actif de la machine et reste donc une gate séparée
du préflight clos. Elle n'autorise ni R3, ni R4, ni une impression. Après ce
retour au `11 × 11`, la mission hors imprimante suivante devra concevoir R4 avec
deux chemins : réutiliser une géométrie valide sans palper, ou finir toutes les
palpations sans filament avant le chargement.

Modèle conseillé pour la restauration : `gpt-5.6-terra` en raisonnement `high` ;
le geste est court et déjà qualifié, mais la lecture avant/après doit rester
stricte. Option optimale si la conception R4 est enchaînée dans la même mission :
`gpt-5.6-sol` en `high`, car l'ordre géométrie/CFS devient structurant.

La tâche source reste visible et ne doit pas être archivée.
