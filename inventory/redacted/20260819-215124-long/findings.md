# Impression longue de production — constats nettoyés

Date : 2026-08-19 au 2026-08-20

Capture : `20260819-215124-long`

Firmware : `2.3.5.34`

Statut : **capture terminée, chaîne CFS et valeur active de pression observées**

## Périmètre et sécurité

Thomas a lancé et surveillé une impression de production normale. Codex a uniquement observé l'état Klipper et les nouvelles lignes du journal par une connexion persistante en lecture seule. Aucune commande de chauffe, mouvement, calibration, impression, annulation, configuration ou écriture distante n'a été envoyée par Codex.

La trace brute, le nom du fichier imprimé, les données réseau et les identifiants matériels des CFS restent sous `inventory/raw/` et ne sont pas publiés.

## Résultat mesuré

- Lancement de la chauffe vers `22:15:58`.
- État d'impression actif à `22:19:29`.
- Fin de chauffe d'impression à `01:37:14`, puis état terminé à `01:37:24`.
- Retour complet au repos à `01:43:38`.
- Aucune variation de la correction Z visible : `+0,27 mm` pendant toute la capture.
- Aucun réglage Z en direct n'a été signalé par Thomas.

## Pression du filament : propriétaire désormais identifiable

Le démarrage stock applique explicitement `0,044` à `22:19:25`. Le fichier d'impression reprend ensuite la main à la première couche et fixe `0,03` à `22:22:53`. La valeur active reste à `0,03` jusqu'à la fin, y compris avant, pendant et après le remplacement automatique de bobine.

Cette session ferme donc l'inconnue laissée par A1/B/A2 : la valeur finale réellement utilisée est bien `0,03`. Le CFS ne l'a pas écrasée pendant ce remplacement. En revanche, aucun réglage de pression associé au nouveau logement CFS n'est appliqué dans la trace. Les défauts de bord observés par Thomas ne peuvent donc pas être attribués, pour cette impression, à un retour caché vers `0,044` lors du changement de bobine.

Il reste deux producteurs inutiles et difficiles à comprendre au démarrage. L'installation future devra rendre l'ordre explicite et n'appliquer qu'une valeur finale connue après toutes les macros de préparation.

## Remplacement automatique : température incorrectement reprise

La bobine active est déclarée vide à `22:38:14`. La machine se met en pause, reconnaît un filament PLA équivalent dans un autre logement du même CFS, effectue le remplacement, puis reprend à `22:41:08`. L'opération dure environ `2 min 54 s`.

La cible de buse suit cette séquence :

1. `195 °C` avant la détection ;
2. `140 °C` pendant la pause ;
3. `220 °C` pendant le chargement ;
4. bref retour à `195 °C` avant la reprise ;
5. nouveau passage à `220 °C` immédiatement après la reprise.

La cible reste ensuite à `220 °C` jusqu'à ce que Thomas la remette manuellement à `190 °C` à `23:04:00`. La machine atteint environ `190 °C` trente secondes plus tard.

Le défaut est donc établi : même quand le système classe les deux bobines comme le même matériau PLA, la reprise ne restaure pas durablement la température d'impression précédente. Elle applique la valeur CFS stock de `220 °C`. La couleur et le type de matériau servent à choisir la bobine de remplacement, mais la température personnalisée du filament n'est pas respectée dans cette chaîne.

## Fin d'impression et nettoyage

La chauffe d'impression est coupée à `01:37:14`. Après l'état terminé puis le retour au repos, la machine redemande brièvement `150 °C` entre `01:43:42` et `01:44:23`, puis remet la cible à zéro.

Cette capture confirme qu'une action thermique tardive existe déjà. Elle ne prouve pas à elle seule que la buse a été nettoyée correctement sur la brosse. Le mouvement, la vitesse, le trajet et le résultat physique devront être rapprochés du journal avant de concevoir le nettoyage de fin demandé.

## Conséquences pour G3

Cette session apporte une preuve qualifiée pour deux sujets :

- la valeur finale de pression et sa stabilité pendant un changement CFS ;
- l'écrasement de la température d'impression par la reprise CFS.

Elle ne suffit pas à expliquer les grands écarts Z historiques : aucune correction Z et aucune variation de l'origine Z visible ne se sont produites pendant ce travail. Le prochain travail réellement différent ou composé de plusieurs objets doit être observé dans une session séparée, sans impression sacrificielle.

Gate G3 reste ouverte pour la question Z globale. En revanche, un correctif indépendant de propriété de température après CFS peut désormais être préparé avec une règle mesurable : après un remplacement automatique, restaurer la température active avant la pause, sauf changement explicite de matériau.

## Prochaine action sûre

Préparer une seconde capture passive autour du prochain fichier réellement différent ou multi-objet. En parallèle, documenter sans déployer un premier correctif CFS minimal et réversible : mémoriser la température avant pause, distinguer remplacement équivalent et changement réel de matériau, puis restaurer la température correcte avant reprise.
