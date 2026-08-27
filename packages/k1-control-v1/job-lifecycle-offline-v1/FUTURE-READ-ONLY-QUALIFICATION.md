# Qualification K1 en lecture seule — résultat du Goal 2

Le Goal 2 a été exécuté le 27 août 2026 sous une autorité strictement en lecture
seule. Deux états nettoyés ont été lus sans G-code, écriture distante, restart,
chauffe, mouvement ou appel du garde.

La qualification a vérifié :

1. la forme exacte de la réponse K1 et son absence de dérive entre deux lectures ;
2. les états d'impression, CFS, capteurs et températures nécessaires ;
3. les délais de lecture et les changements spontanés observables ;
4. le mapping observable des deux CFS et la règle d'invalidation après reconnexion ;
5. les empreintes des composants et configurations déjà installés ;
6. les points d'intégration Moonraker possibles sans les activer.

Les deux lectures d'état ont pris `199,212 ms` et `235,525 ms`, sous le plafond
fermé de `5 s`. Les deux CFS sont connectés, aucune route n'est engagée, la
commande CFS est vide, les chauffes sont à zéro et le Z accepté reste à
`−0,04 mm`. Toutes les empreintes relues sont restées identiques avant/après et
correspondent aux versions déjà revues.

Le résultat n'autorise pourtant pas la suite physique : le profil actif est
`default`, dont la matrice `6 × 6` ne correspond pas au profil robuste requis
`k1_p001_t055_r001_n06x06`. Le profil robuste existe encore avec son empreinte
attendue, mais il n'est pas chargé. Le statut est donc
`CLOSED_READ_ONLY_BLOCKED_MESH_DRIFT`.

La règle de mapping est maintenant fermée côté logiciel : tout changement de
l'état des unités, de la route observable ou de l'époque de connexion invalide
le cache. Une reconnexion très courte qui retrouverait exactement le même état
entre deux sondages resterait invisible ; le futur composant Moonraker devra
donc fournir une époque issue des notifications. Aucune reconnexion n'a été
provoquée pendant cette mission.

Le Goal 2 n'a envoyé ni `BOX_QUIT_MATERIAL`, ni `TURN_OFF_HEATERS`, ni autre
G-code. Il n'a créé aucun fichier distant, redémarré aucun service et n'a pas
importé le chemin d'effet du garde. Charger le profil robuste demandera une
future gate distincte avec Thomas devant la K1.
