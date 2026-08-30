# Résultat

Statut : `CLOSED_OK_CAMERA_READ_ONLY_AND_R3_COLD_VALIDATED`.

Le pilote caméra a résolu `k1max-root` sans exporter l'adresse, pris une image
fraîche `1280 × 720` par un unique `GET`, contrôlé la netteté et extrait les
zones buse, bac et plateau. Les trois écarts moyens avec `SAFE_IDLE_PARK` sont
compris entre `0,009603` et `0,010838`. La revue visuelle confirme seulement le
même état sûr visible : tête haute, plateau descendu et aucune activité. Le
pilote conserve `semantic_state_confirmed=false` et ne possède aucune commande
capable d'ouvrir une gate.

La bibliothèque contient toujours une seule référence réellement acquise :
`SAFE_IDLE_PARK`. Les cinq autres états restent absents et ne sont ni simulés
ni promus depuis une ressemblance d'image.

La validation statique R3 est verte. Les deux phases caméra bloquent avant la
référence Z précise et avant le modèle. Seules `PAUSE_BASE` et `RESUME_BASE`
sont appelées ; aucun `PAUSE`, `RESUME` ou nettoyage CFS stock n'est présent.
Le timeout appelle `TURN_OFF_HEATERS` avant de fermer l'état et ne confirme
jamais une image. Les `16` blocs G-code ont aussi été parsés par le Jinja2 du
Python déjà présent sur la K1, via stdin seulement :
`REMOTE_R3_JINJA_PARSE_OK sections=16`.

Vérifications : `19/19` tests ciblés caméra, R3 et registre Goal 3, plus `5/5`
contrôles de passation et d'autorité ; suite
complète `797` tests, dont `794` verts et `3` ignorés connus ; parse PowerShell
vert, auto-comparaison de
la référence verte, capture live verte et parse Jinja distant vert. Aucune
écriture distante, G-code, chauffe, extrusion, mouvement, commande CFS,
service ou modification de configuration n'a eu lieu.

R3 reste hors imprimante : `deployment_candidate=false` et
`physical_run_authorized=false`. Avant toute future gate chaude, Thomas devra
réellement nettoyer la buse, nettoyer et libérer le plateau, puis réengager
`T1A` avec la fonction officielle. Ces gestes n'ont pas été effectués dans
cette tranche.
