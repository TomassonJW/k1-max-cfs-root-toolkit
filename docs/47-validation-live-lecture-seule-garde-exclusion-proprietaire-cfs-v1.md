# Validation live en lecture seule du garde d’exclusion propriétaire CFS V1

Date : 2026-08-28
Mission : `G4-K1-CONTROL-CFS-OWNER-EXCLUSION-GUARD-LIVE-READ-ONLY-V1`
Verdict : `CLOSED_READ_ONLY_BLOCKED_CONNECTION_EPOCH_AND_EFFECTIVE_Z_SOURCE`

## Résultat réel

La capture privée
`20260828-190631-g4-k1-control-cfs-owner-exclusion-guard-live-read-only-v1`
a exécuté exactement deux requêtes `GET` dans une seule session SSH. Les
réponses ont été nettoyées sur la K1 avant leur retour local. Aucun identifiant
`sn` ou `uuid` n’a été exporté.

Les deux lectures sont stables : Klipper est en `standby`, `T1` et `T2` sont
connectés, aucune route filament n’est engagée, la commande CFS est vide, les
cibles thermiques sont à zéro et le profil actif est
`k1_p001_t055_r001_n11x11`. Les trois empreintes de configuration sont restées
identiques. La politique stock d’auto-remplacement vaut `1` et l’impression CFS
stock est activée.

Le garde d’effet n’a été ni importé ni appelé. Il n’y a eu aucun G-code,
chauffage, mouvement, effet CFS, fichier distant, restart ou autre action
physique.

## Pourquoi la gate reste bloquée

La K1 ne fournit pas d’époque de connexion exploitable dans les objets lus.
Deux réponses identiques ne permettent donc pas de détecter une déconnexion et
reconnexion rapide revenue au même état entre les sondages. Inventer cette
valeur affaiblirait le refus sûr du garde.

La capture fournit également une empreinte stable du stockage Z accepté, mais
pas sa valeur. Le champ live `gcode_move.homing_origin[2]`, observé proche de
zéro, n’est pas la valeur Z acceptée `−0,04 mm` et ne peut pas la remplacer.
L’adaptateur pur a donc été appelé uniquement pour prouver son refus avec les
blocages `connection_epoch_invalid` et `effective_z_source_unqualified`.

## Frontière et suite

V1 est consommée et `rerun_authorized=false` : aucune troisième lecture ne doit
être faite sous cette autorité. Les preuves versionnées sont le contrat, la
carte de preuve nettoyée et le validateur dans
`packages/k1-control-v1/cfs-owner-exclusion-guard-live-read-only-v1/`. La source
privée reste ignorée par Git et n’est référencée que par son empreinte SHA-256.

La prochaine mission unique proposée est
`G4-K1-CONTROL-CFS-OWNER-OBSERVABILITY-ADAPTER-OFFLINE-V2`. Elle doit concevoir
hors imprimante une projection qui refuse sûrement l’absence d’époque de
connexion et qui obtient la vraie valeur Z acceptée depuis une source qualifiée.
Elle n’autorise aucune connexion K1, commande, pose ou action physique.
