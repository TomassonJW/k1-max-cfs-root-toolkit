# 94 — Essai V2 arrêté par le surveillant pendant le chargement

## Résultat et cause immédiate

L'essai supervisé a été explicitement autorisé après un refus du contrôle
d'approbation. Buse nettoyée et plateau libre confirmés ; caméra examinée,
version V2 et 22 empreintes vérifiées. Un nouveau fichier a été utilisé,
avec une seule confirmation de départ et le mapping logique T1A vers T1B.

Le départ atteint les références avant insertion, puis le bac à 200 °C.
À 23:59:51 le 21 septembre 2026, le surveillant externe appelle l'arrêt
d'urgence après huit messages `full` sur 28,848 s. Il ne s'agit pas d'une
erreur du retrait : ni la pause prévue ni END_PRINT ne sont atteints.

Au dernier échantillon, la tête voit le filament depuis 33,449 s. Klipper
commande E à 3 mm/s ; la position E interpolée vaut 77,635 mm pour 95 mm mis
en file. La buse vaut 199,84 °C pour une cible de 200. La console ne contient
aucune erreur avant l'arrêt. Les key94/key294 apparaissent après l'arrêt et
ne doivent pas être présentés comme sa cause initiale.

Ces grandeurs décrivent les ordres moteur, pas le débit réel. Thomas signale
un plantage à l'insertion, puis précise ne pas avoir été assez attentif et
penser que rien n'est sorti. Ce constat reste incertain : ni purge réussie
ni absence de blocage mécanique ne sont confirmées. Il demande un nouvel essai.

## Défaut du surveillant réutilisé

`GripGuard` compte les indications `full` sans connaître le capteur de tête
ni la phase du chargeur. Dans le script d'essai, `first_grip` ne devient faux
qu'à la pause, donc ce critère reste actif après l'arrivée du filament, pendant
les poussées suivantes. Il assimile huit messages à un blocage et appelle M112.
La réutilisation sans distinguer ces phases était une erreur de préparation.
Cela ne démontre pas pour autant que ce chargement aurait réussi sans arrêt.

Le libellé `buffer_still_full_before_stock_retry` ne prouve pas que l'arrêt
précède toutes les relances internes : la trace stage8 contient déjà plusieurs
requêtes EXTRUDE_PROCESS acquittées. Ne pas qualifier le matériel sur ce nom.

La correction suivante doit distinguer arrivée à la tête, suite du chargement
et purge. `full` seul après détection de tête ne peut justifier le diagnostic
de blocage. Conserver un arrêt sur erreur réelle et une durée bornée, ainsi
que la preuve physique de purge ; ne pas simplement supprimer le surveillant
ou augmenter son compteur. Rejouer hors imprimante les captures de réussite
et d'échec avant toute nouvelle mise en service. Aucun nouveau garde n'a été
installé pendant ce diagnostic et aucun retry physique n'a été exécuté.

## Comparaison et successeur local

Dans les deux chargements réussis précédents, les premiers ordres E et le
courant extrudeur ressemblent à ceux de cet essai, mais la route devient B
et l'avance passe à 6 mm/s pour la purge. Ici, la route reste absente et les
poussées d'insertion à 3 mm/s se répètent. Le premier essai réussi ne présentait
qu'un `full` avant `middle`, le second aucun. Le cas actuel en présente huit.
Conclusion corrigée : notre surveillant est la cause immédiate de l'arrêt,
mais un déroulement anormal du chargement est déjà observable avant cet arrêt.
Il serait injustifié de simplement supprimer la limite et laisser insister.

Le module externe `startup-grip-observer-v2` distingue tête vide, tête présente
avec route non confirmée, et tête présente avec route cible acceptée. Il garde
la limite de huit avant acceptation ; après acceptation, elle ne traite plus
la purge comme une première insertion. Les erreurs firmware restent gardées.
Il ne confond pas ces états logiciels avec un débit physiquement prouvé.
89 tests ciblés passent. Le rejeu des trois captures, alignées par les
horodatages HEART_PROCESS (dispersion inférieure à 11 ms), conserve les deux
chargements réussis et refuse encore le cas actuel avec la raison exacte
`loading_unconfirmed_buffer_full`. La dernière console, lue après le dernier
échantillon moteur par le pilote réel, est prise en compte dans cet ordre.
Ce successeur est local uniquement ; aucun nouveau cycle n'est lancé.

Pour refaire le début, un seul retrait officiel surveillé puis nettoyage
manuel ont été demandés. Arrêt demandé si la séquence saute chauffe/coupe
avec filament toujours engagé ou si le moteur force ; aucune répétition.
La réussite de cette récupération manuelle reste à confirmer avant reprise.

## Récupération vérifiée

Les quatre cartes accusent l'arrêt demandé dans le journal. Moonraker renvoie
ensuite 503, car Klipper n'est plus connecté. Un arrêt de service retourne non
zéro ; une lecture séparée prouve que le PID n'existe plus. L'arrêt n'est pas
répété. Un démarrage seul rend le service joignable, mais key298 signale la
carte principale encore verrouillée. Une seule requête FIRMWARE_RESTART lève
ce verrou. Aucun G-code de mouvement, chauffage ou filament pendant cette
récupération ; aucune extinction/rallumage demandée à Thomas.

État final : ready/standby, cibles zéro, buse environ 40 °C et plateau 44 °C
au contrôle, axes non référencés, V2 actif/idle, tête détectée chargée, T1/T2
connectés mais sans route déclarée. La position physique reste au bac sur la
caméra. La tête n'est donc pas vide malgré les tables CFS réinitialisées.
Les 22 fichiers protégés correspondent toujours aux empreintes installées.

75 tests ciblés du surveillant historique, des échantillons et du retrait V2
passaient avant le départ : ils ne couvraient pas la validité de la décision
`full` dans toutes les phases physiques. Aucun succès physique n'en est déduit.
Le retrait V2 reste installé mais non qualifié. La récupération filament et
un nouveau nettoyage doivent précéder toute prochaine référence par contact.

Preuve nettoyée : `inventory/redacted/20260921-cfs-overlap-end-trial-v2/result.json`.
Captures, images et scripts locaux dans le répertoire raw de même nom, privé.
