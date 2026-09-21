# 92 — Échec du retrait séparé et correction du chevauchement des moteurs

Le 21 septembre, l'essai court autorisé a chargé T1B sans blocage initial
observé. Thomas confirme la purge. Les références avaient été effectuées avant
insertion, avec buse fraîchement nettoyée. Les 22 empreintes installées et les
deux backups avaient été vérifiés. Une pause volontaire a coupé les chauffes
pendant l'attente humaine ; une seule reprise a suivi à 200/55.

La coupe et le relâchement du levier réussissent. La tête reste X38 Y291,5,
Z physique 7,19257 : aucun retour au bac pendant le retrait. Les ACK IDLE et
STOP sont OK. La commande MATERIAL adressée au CFS 1, case B reçoit après
12,63 s RETRUDE_ERR6/0x19 et key849 « failed to exit connections ».
Thomas observe le CFS rouge et aucun rembobinage visible. Le capteur de tête
reste occupé. L'état final est failed, pending=false, Klipper ready, cibles zéro,
aucun parc final et aucun M112. Le voyant rouge n'est pas une fin réussie.
Le champ constructeur t_command=T1A est obsolète : la trame de retrait vise B.

## Erreur introduite par V1

Le contrôle des seules distances/vitesses était insuffisant. La primitive
Tn_Extrude termine E-20 F5000 avec M400 ; la macro programme ensuite E-15 F120
sans attendre et appelle immédiatement les primitives CFS. V1 avait regroupé
les deux déplacements puis ajouté M400, qui attendait leur fin à tous deux.

La comparaison des captures, alignées par les horodatages HEART_PROCESS,
confirme -2 mm/s côté extrudeur pendant le lancement CFS de R2, contre 0 mm/s
avec V1. R2 avait vidé la tête, sans toutefois qualifier toute la fin du cycle.
La rétraction nécessite une coordination des moteurs ; avoir recopié les
valeurs ne prouvait pas cette coordination. L'utilisateur a explicitement
signalé ce point après l'échec. Il ne faut pas attribuer ce défaut à sa bobine.

## Correction hors imprimante

Le nouveau fichier end-overlap-v2/kctrl_end.py place l'attente après les 20 mm
rapides ; il laisse les 15 mm lents se dérouler pendant le lancement CFS.
Une attente après l'ACK évite aussi de garer la tête si le CFS répond avant la
fin du mouvement extrudeur. Aucun nouvel axe, température ou trajet au bac.

La validation ciblée obtient 170 tests verts. La simulation distingue une
commande mise en file de son exécution physique et couvre les ACK courts/longs.
Trois témoins négatifs rejouent le code V1 et détectent la perte de chevauchement.
L'erreur key849 réelle reste un refus : pas de parc, pas de retry, chauffes zéro.
Les tests historiques seuls passaient car leur faux G-code ne simulait pas
l'écoulement des mouvements. Les nouveaux tests ferment cette lacune précise.

## État de reprise

V1 est toujours installé, actif mais verrouillé en échec ; ne pas le rejouer ni
redémarrer pour masquer la faute. V2 est seulement local, sans déploiement ni
qualification physique. Le retrait officiel T1B, une seule fois depuis l'écran,
a été demandé pour récupérer le filament ; résultat humain encore attendu.
Ne pas augmenter arbitrairement la distance, forcer le CFS ou palper avec le
filament engagé. Après récupération : état et caméra frais, paquet de pose et
rollback épinglés, installation contrôlée puis nouveau cycle intégré supervisé.
Le problème intermittent de premier chargement reste distinct et non résolu.

Preuve nettoyée : ../inventory/redacted/20260921-cfs-separated-end-trial-v1/result.json.
Les captures brutes restent privées. Aucun firmware/configuration installé n'a
été remplacé pendant cet essai ni pendant la correction hors imprimante.
