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

La validation physique du premier bouton n'appartient pas à cette pose. Elle
commence ensuite par la présence humaine, la caméra et un nettoyage frais de la
buse et du plateau, avant toute géométrie et avant toute insertion de filament.
