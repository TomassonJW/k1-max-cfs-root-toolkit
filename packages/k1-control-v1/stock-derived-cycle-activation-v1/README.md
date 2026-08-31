# Stock-derived cycle activation V1

Ce paquet active au repos les propriétaires déjà installés en mode désactivé.
La pose ne sélectionne aucun G-code, ne crée aucun état de run, ne chauffe, ne
bouge, n'extrude, ne palpe et n'envoie aucune trame CFS.

Le roulement de bobine repose sur le vrai événement constructeur de
`filament_sensor_2`. Le simple état d'un capteur ne déclenche rien. Une bobine
réellement vide est libérée logiquement sans cutter ; l'unique bobine de secours
strictement identique est ensuite chargée et purgée à la température sauvegardée
du G-code. Un changement volontaire conserve le cutter et le retrait normal.

La pose remplace exactement trois includes Klipper désactivés par leurs versions
actives, remplace la section Moonraker désactivée et installe les cinq nouveaux
modules nécessaires. Les composants historiques de transport, de cycle et de
géométrie ne sont pas réécrits.

Vérification hors imprimante :

```powershell
python packages\k1-control-v1\stock-derived-cycle-activation-v1\verify_candidate.py
```

L'installation active au repos et sa validation indépendante sont closes sous
la capture `20260831-205322-g4-k1-control-stock-derived-cycle-activation-v1`.
Le restart hôte recharge explicitement le mesh `11 × 11` et le Z accepté
`-0,04` avec `MOVE=0` avant de valider l'état `idle`.

La validation physique du premier bouton n'appartient pas à cette pose. Elle
commence ensuite par la présence humaine, la caméra et un nettoyage frais de la
buse et du plateau, avant toute géométrie et avant toute insertion de filament.

## Récupération d'une route perdue au redémarrage

Si les deux capteurs physiques voient le filament mais que le CFS et le
propriétaire direct n'exposent plus de route logique, le départ utilise
uniquement la route initiale explicitement choisie pour le travail. Le ticket
effectue d'abord la réassociation directe. Si le redémarrage a aussi libéré les
axes, il référence seulement X/Y et marque Z sans mouvement à une hauteur sûre :
aucune palpation Z n'a lieu avec le filament. Il enchaîne ensuite cutter,
retrait, arrêt des chauffes et libération des moteurs. La vraie géométrie de
contact X/Y/Z reste obligatoire après retrait et nettoyage frais. Toute autre
combinaison de capteurs reste refusée, sans nouvel essai automatique.
