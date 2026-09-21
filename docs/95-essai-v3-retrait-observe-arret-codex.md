# 95 — Chargement et retrait observés ; arrêt demandé par Codex

Le 22 septembre 2026, Thomas confirme redémarrage, retrait, nettoyage de la
buse et plateau libre. La lecture et la caméra concordent : tête vide, cibles
zéro, deux CFS connectés ; les 22 empreintes installées sont inchangées.
Un nouveau fichier V3 emploie le même départ 200/55 et le retrait coordonné
end-overlap-v2 déjà posé, avec l'observateur de chargement distinguant les phases.
Aucun nouveau fichier de configuration ou module n'est installé sur la K1.

## Chargement et pause

Les références précèdent l'insertion. Le chargement prend T1B, obtient `middle`
sans accumulation de `full`, puis atteint la pause. Thomas confirme le filament
sorti au bac et la boule décrochée. Le défaut intermittent de prise ne survient
pas sur cet essai ; il n'est pas déclaré résolu pour autant.

Pendant l'attente humaine, une commande TURN_OFF_HEATERS est vérifiée. Le
surveillant local est ensuite arrêté volontairement avant sa limite de pause
afin d'éviter un M112 sans raison physique. Son PID 39964 et sa ligne de
commande ont été vérifiés avant cet arrêt local ; le code de sortie -1 du
wrapper ne signifie pas un plantage de l'imprimante. Aucun arrêt d'urgence
n'est envoyé à cette étape. Un second surveillant est armé avant la chauffe
200/55 et une seule reprise RESUME_BASE après confirmation de purge.

## Retrait et responsabilité de l'arrêt

| Événement | Heure locale |
|---|---|
| Coupe confirmée | 00:42:02,191 |
| Demande CFS de retrait B | 00:42:03,719 |
| Premier échantillon tête libre | environ 00:42:04,585 |
| Arrêt d'urgence envoyé par Codex | 00:42:15,068 |
| Second arrêt envoyé par le surveillant | 00:42:16,173 |

La tête se dégage localement du levier vers X38 Y291,5, sans trajet au bac.
La caméra montre une main masquant la zone pendant la reprise. Codex déclenche
l'arrêt, ne pouvant exclure sa présence dans la zone de mouvement. Thomas
précise ensuite avoir enlevé un résidu sur la buse et confirme que le retrait
a fonctionné. L'arrêt n'est pas présenté comme une nouvelle panne de chargement
ou une faute CFS. Le second M112 est un défaut du surveillant : `shutdown`
devient à tort une nouvelle erreur nécessitant encore un arrêt.

Le capteur de tête libre et le retrait constaté par Thomas sont acquis pour
cet essai. La réponse finale de retrait et le stationnement automatique ne sont
pas qualifiés, car Codex a interrompu leur observation. `print_stats=complete`
ne prouve pas la fin physique : le fichier est fini avant le travail asynchrone
de kctrl_end. Ne pas déclarer le cycle entier validé.

## Durée de l'extrudeur

Thomas signale une activité trop longue de l'extrudeur pendant le rembobinage
et attend une ou deux secondes. V2 programme 15 mm à 2 mm/s, soit 7,5 secondes,
après 20 mm rapides. La lecture isolée du binaire constructeur exact confirme
ces distances/vitesses ; elles n'ont pas été introduites pour cet essai.
Les échantillons confirment le chevauchement à -2 mm/s, alors que la tête se
libère environ 0,9 seconde après la demande CFS. Cela justifie d'étudier une
rétraction plus courte, pas de considérer arbitrairement deux secondes comme
une durée déjà qualifiée. Aucun paramètre moteur n'est changé sur hypothèse.

## Récupération et correction locale

Klipper quitte après l'arrêt. Son PID 1470 est prouvé absent ; un démarrage
seul, puis un unique firmware_restart conditionné à key298, rétablissent
l'accès en environ 52 secondes. Aucun mouvement, chauffage ni retrait de
récupération. État final ready/standby, cibles zéro, tête libre, deux CFS
connectés sans route, axes non référencés. La buse n'est pas réputée propre pour
une nouvelle palpation après les effets filament de cet essai.

`startup-grip-observer-v2/stop_policy.py` prépare hors imprimante la distinction
entre arrêt déjà constaté, échec déjà immobile et froid, attente humaine et
danger nécessitant un arrêt. Un reçu créé exclusivement partage l'unique envoi
entre observateurs ; une réponse réseau incertaine ne déclenche pas de retry.
106 tests ciblés passent, dont l'exécution via les adaptateurs de lecture,
coupure thermique et arrêt. Cette politique n'est pas encore intégrée dans un
nouveau pilote physique ; les scripts V2/V3 archivés ne doivent pas être rejoués.
Les alertes physiques caméra restent actives : il ne s'agit pas de les masquer.

Suite : intégrer cette politique à un seul pilote testé avant tout nouvel
essai, puis préparer la qualification de fin sans interruption. Le diagnostic
du chargement intermittent et la durée minimale de retrait restent ouverts.
Preuve nettoyée : `inventory/redacted/20260922-cfs-overlap-end-trial-v3/result.json`.

La lecture finale indépendante confirme les 22 empreintes inchangées, ready,
standby, tête libre et cibles zéro. Les deux seuls fichiers d'essai V2/V3 sont
retirés de la K1 après vérification de leurs hashes exacts. Les preuves locales
restent archivées ; aucun autre G-code n'est supprimé.
