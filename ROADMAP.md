# ROADMAP

## P0 — Repository and safety baseline

Status: **completed**

- define scope and non-goals;
- separate public artefacts from private raw data;
- establish agent prohibitions and progression gates;
- prepare read-only acquisition and recovery prerequisites.

Exit: Gate G1.

## P1 — Root and stock acquisition

Status: **completed**

- enable root manually;
- verify machine, board, printer firmware and both CFS firmware versions;
- inventory processes, services, mounts, configuration and log paths;
- copy relevant files from printer to local private storage;
- calculate checksums;
- publish only sanitised manifests and evidence.

Exit: Gate G2.

## P2 — Behaviour map and diagnosis

Status: **completed on 2026-08-20 — Gate G3 passed for offline preparation**

- reconstruct configuration includes and service ownership;
- build call graphs for startup, Z homing, levelling, tool changes, loading, cutting, flushing and resume;
- identify every write to temperature targets, Z offsets and meshes;
- compare two executions of identical G-code;
- separate mechanical repeatability, thermal effects and software resets.
- ingest the real Orca profiles, custom G-code and already-produced projects;
- build an offline timeline showing which component owns Z, mesh, temperature,
  pressure advance and CFS state at each step;
- decide whether dynamic wrappers cover every CFS temperature path or whether
  the compiled owner must be replaced.

Exit: Gate G3.

## P3 — Conception et prototype complet hors imprimante

Status: **completed on 2026-08-20 — prototype vert, premier G4 préparé mais non autorisé**

Le paquet fixe `G4-ZSAFE-START-V1` est rejeté et n'a jamais été déployé. La
phase construit maintenant un seul produit cohérent avant toute demande
d'installation.

- verrouiller le contrat Z : réglage en session, enregistrement explicite,
  persistance et invalidation après nouvelle référence ;
- définir les meshes par plaque et plage thermique, plus un mesh adaptatif non
  persistant par travail ;
- simuler l'ordre thermique, nettoyage, référence finale, mesh, Z, CFS, purge,
  impression et fin ;
- construire l'interface quotidienne `K1 Control` sur un faux Moonraker relié
  au moteur d'état ;
- sélectionner et épingler une pile Moonraker/Mainsail compatible MIPS/Buildroot
  sans installateur général ni mise à jour automatique ;
- produire le contrat Orca complet départ/fin/changement d'outil ;
- couvrir démarrage, refill équivalent, changement voulu, deux CFS, pause,
  reprise, annulation, fin et changement manuel de température ;
- préparer les poses réversibles, sauvegardes, empreintes, tests haut et
  rollbacks, sans les exécuter.

Exit: prototype local complet, matrice verte, versions exactes et premier paquet
G4 nommé préparé. Cette sortie n'autorise toujours pas son déploiement.

Sortie atteinte : 17/17 scénarios verts, bundle local vérifié, Moonraker MIPS
et Mainsail `v2.18.2` épinglés, contrat Orca complet et
`G4-K1-CONTROL-FOUNDATION-V1` préparé sans mutation de l'imprimante.

## P4 — Installation contrôlée du système de pilotage

Status: **calibration quotidienne autonome ; composite `11 × 11` meilleur au
centre mais KO aux bords ; éditeur hors imprimante validé ; diagnostic de bord
suspendu ; débit CFS prouvé mais séquence brute refusée ; binaire et journal
exacts audités ; retrait stock `T1A` capturé avec deux phases réussies mais
chauffe finale non coupée ; garde stock, mapping live et adaptateur de réponse
fermés et verts sans transport ; production fermée**

Le produit est posé par étapes techniques réversibles, mais Thomas reçoit un
seul fonctionnement quotidien :

1. API et Mainsail en observation — V1 refusée par le préflight réel ; V2
   rollbackée après preuve d'incompatibilité du compte Moonraker ; V3 conserve
   le syslog stock, place l'authentification compatible sur nginx et est
   installée avec compte vérifié et ouverture LAN contrôlée ;
2. état et chemin de calibration Z installés ; FIRST-CALIBRATION-V2 et campagne
   quotidienne depuis l'écran validées ;
3. profil composite `11 × 11` acquis et persisté ; sa comparaison V2 prouve un
   gain central mais refuse sa promotion à cause des bords ;
4. `MESH-EDITOR-OFFLINE-V1` validé hors imprimante, avec profil source immuable,
   profil dérivé versionné, historique et rollback ;
5. `MESH-EDGE-DIAGNOSTIC-V1` suspendu : la route `CFS1/A` et une purge visible
   ont été prouvées pour un passage, mais la séquence a imposé `220 °C`, homé
   X/Y et tenté la purge avec le plateau trop haut ;
6. contrat complet du cycle figé hors imprimante : états filament, nettoyage,
   référence finale, sélection du mesh, Z, changements, pause, reprise et fin ;
7. `CFS-BOUNDARY-GUARD-V1` validé hors imprimante sur six invariants ;
   `CFS-BOX-WRAPPER-AUDIT-V1` a ensuite confirmé le `220 °C` et la géométrie
   internes ; aucune primitive stock n'est qualifiée et l'adaptateur reste
   fail-closed ;
8. `CFS-DYNAMIC-TEMP-ROUTING-V1` close hors imprimante : ticket par phase,
   route fraîche, deux CFS et 25 scénarios verts ; propriétaire filament minimal
   choisi, mais protocole d'exécution et transport encore absents ;
9. protocole minimal cartographié hors imprimante puis fermé en KO borné : une
   seule route d'effet `T1A`, aucune liste appelable ; acquisition des preuves
   manquantes avant toute implémentation ou qualification physique ;
10. gate de preuve supplémentaire close en KO borné : le retrait stock `T1A`
    est maintenant relié à deux requêtes, deux réponses et au capteur local,
    mais l'exclusion stock et le cycle complet restent manquants ;
11. capture réelle du retrait officiel `T1A` close : macro terminée, route
    désengagée et configurations inchangées, mais cible `220 °C` laissée active
    jusqu'à `TURN_OFF_HEATERS` ;
12. garde hors imprimante de la macro constructeur clos : une seule tentative,
    preuve réelle de fin, aucun retry et arrêt thermique toujours vérifié après
    effet ;
13. préflight live en lecture seule clos : champs réels cartographiés, aucun état
    direct de fin de retrait, garde corrigé sur la route réellement libérée et
    état courant bloqué sans route ;
14. adaptateur hors ligne clos : dix réponses synthétiques, traduction vers les
    huit champs du garde, refus des routes ambiguës et données invalides, aucun
    réseau ni chemin d'effet ; prochaine gate = validation live en lecture seule ;
15. contrat Orca final et retrait atomique prouvé de l'ancien post-traitement
    `+0,27 mm`.

Le rollback exact de `MESH-EDGE-DIAGNOSTIC-V1` et sa validation finale sont
verts. Aucun acte physique suivant n'est automatiquement autorisé. La reprise
du motif reste interdite tant que la route du filament et une purge réellement
visible ne sont pas prouvées depuis un état frais.

La seconde famille suit ADR-016 et le contrat V1 figé : un unique
`KCTRL_JOB_BEGIN` remplacera à terme le cumul Orca `G28 + Tn + START_PRINT`.
Il résoudra l'outil logique depuis l'état CFS frais, sans slot physique codé en
dur. Le bon filament déjà engagé restera engagé, chaque départ obtiendra une
purge visible, une pause normale ne déclenchera pas une reprise CFS et les
températures du G-code seront appliquées séparément aux phases ancien filament,
transition et nouveau filament. La fin normale gardera le filament engagé ; un
bouton distinct réalisera le désengagement et le nettoyage à la demande.

Chaque pose a son backup, son diff, ses critères OK/KO et son rollback. Aucune
pose suivante ne commence si l'écran, Creality Web/Print, le CFS ou Klipper
régressent.

Exit: système complet installé et prêt pour Gate G5.

## P5 — Production validation

Status: **not started**

- cold boot and three consecutive prints on a known plate without manual Z correction;
- live Z calibration saved once, retained after restart, then deliberately
  invalidated by a new reference calibration;
- plate/temperature mesh selection verified; no adaptive per-job mesh before
  a separately qualified gate;
- composite regeneration, local point correction, derived-profile versioning
  and one-click fallback available through K1 Control without Codex;
- same-material CFS changes;
- cross-CFS change between CFS 1 and CFS 2;
- at least one cross-material transition policy;
- OrcaSlicer upload and control path;
- retained Creality compatibility where required;
- measured startup-time improvement with no first-layer regression.
- daily use through `K1 Control` without Codex or per-print file editing.
- normal pause/resume proven without an implicit CFS purge and without losing
  the latest effective Z.

Exit: stable V1 baseline and tagged release.

## P6 — Community hardening

Status: **not started**

- document hardware and firmware compatibility matrix;
- add automated redaction and config tests;
- translate key documentation if useful;
- accept external reports through reproducible evidence templates;
- select and add an explicit licence;
- publish versioned releases without proprietary payloads.
