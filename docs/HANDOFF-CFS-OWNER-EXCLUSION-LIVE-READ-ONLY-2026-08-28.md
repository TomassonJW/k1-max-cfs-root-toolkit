# Archive — exclusion propriétaire CFS, lecture live V1

Cette passation est historique. Lire désormais
`docs/HANDOFF-CFS-OWNER-EXCLUSION-LIVE-EFFECT-2026-08-28.md`.

Date : 2026-08-28
Mission close : `G4-K1-CONTROL-CFS-OWNER-EXCLUSION-GUARD-LIVE-READ-ONLY-V1`
État : `CLOSED_READ_ONLY_BLOCKED_CONNECTION_EPOCH_AND_EFFECTIVE_Z_SOURCE`
Nouvelle tâche : non
Goal actif : absent

## État livré

La gate autorisée a consommé exactement deux lectures fraîches et nettoyées de
la K1, dans une seule session SSH. La capture privée canonique est
`20260828-190631-g4-k1-control-cfs-owner-exclusion-guard-live-read-only-v1` ;
son contenu reste ignoré par Git et sa carte de preuve versionnée conserve
seulement son chemin, son empreinte et le résultat sûr.

Les deux réponses sont stables. La machine était en `standby`, les chauffes à
zéro, `T1` et `T2` connectés, aucune route engagée et aucune commande CFS
active. Le profil `k1_p001_t055_r001_n11x11` était actif. Les empreintes de
`printer.cfg`, `box.cfg` et `gcode_macro.cfg` sont identiques avant et après.
La politique stock d’auto-remplacement et l’impression CFS stock étaient toutes
deux actives.

Aucun chemin d’effet du garde n’a été importé ou appelé. Aucun G-code,
chauffage, mouvement, effet CFS, fichier distant, restart ou déploiement n’a eu
lieu. La mission n’a donc qualifié aucun effet réel et n’autorise pas la
production.

Le résultat n’est pas une promotion de l’adaptateur. Deux informations de
sécurité manquent encore. Premièrement, les objets K1 lus n’exposent pas
d’époque de connexion : une reconnexion rapide revenue au même état entre les
deux sondages resterait invisible. Deuxièmement, l’empreinte du stockage Z est
stable mais sa valeur n’est pas observable dans cette capture. Le
`homing_origin` live proche de zéro n’est pas le Z accepté `−0,04 mm` et ne peut
pas lui être substitué. L’adaptateur pur refuse donc la projection avec
`connection_epoch_invalid` et `effective_z_source_unqualified`.

Les composants principaux sont regroupés dans
`packages/k1-control-v1/cfs-owner-exclusion-guard-live-read-only-v1/` : contrat
fermé, collecteur historique, validation pure, carte de preuve, résultat et
documentation. Le document canonique est
`docs/47-validation-live-lecture-seule-garde-exclusion-proprietaire-cfs-v1.md`.
Les contrats d’architecture, le registre de décisions et les tests de politique
sont alignés sur ce verdict.

## Vérifications et limites

- `OK` — exactement deux snapshots live, nettoyés à distance ;
- `OK` — état stable, configurations inchangées, machine sûre au moment des lectures ;
- `OK` — `9/9` tests ciblés du paquet ;
- `OK` — `24/24` tests ciblés de preuve, architecture et autorité ;
- `OK` — suite complète : `678` tests, dont `675` verts et `3` ignorés connus ;
- `KO borné` — époque de connexion absente ;
- `KO borné` — vraie valeur Z acceptée non projetée ;
- `non exécuté` — tout effet, pose, impression ou validation physique, car hors autorité.

V1 est consommée et ne doit pas être rejouée : `rerun_authorized=false`.
Aucune troisième lecture n’est permise par le GO reçu. La tâche source reste
visible et non archivée. Le SHA Git final, l’état local/distant et les totaux de
tests sont donnés dans le compte rendu de clôture qui accompagne cette
passation.

## Prochaine mission unique

La reprise proposée est
`G4-K1-CONTROL-CFS-OWNER-OBSERVABILITY-ADAPTER-OFFLINE-V2`.

Elle doit, hors imprimante, définir et tester une projection qui :

1. fournit une époque de connexion issue d’une source réellement observable ou
   refuse explicitement son absence ;
2. lit la vraie valeur Z acceptée depuis une source qualifiée, sans utiliser
   `homing_origin` comme raccourci ;
3. conserve les comparaisons strictes du garde et bloque toute ambiguïté ;
4. reste sans transport, sans commande distante et sans candidat de pose.

Relire d’abord le contrat live V1, sa carte de preuve, le document 47, ADR-032
et D-084. La mission est close lorsque la matrice synthétique couvre les
reconnexions, la dérive Z, les champs absents et les états stables, avec un
adaptateur pur et aucun accès K1.

État de reprise : `ATTENDRE_GO`. Ce futur GO autorisera uniquement la conception
et les tests locaux de l’adaptateur V2. Une nouvelle lecture live, puis le
premier effet réel, resteront deux gates séparées.
