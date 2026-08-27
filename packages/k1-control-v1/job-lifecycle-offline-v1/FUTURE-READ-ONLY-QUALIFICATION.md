# Future qualification K1 en lecture seule

Ce document prépare la reprise après le Goal 1. Il n'autorise aucune connexion
dans la session hors imprimante actuelle.

Le Goal 2 devra relire, sans commande :

1. la forme exacte de la réponse K1 et son éventuelle dérive ;
2. les états d'impression, CFS, capteurs et températures nécessaires ;
3. les délais de lecture et les changements spontanés observables ;
4. le mapping des deux CFS et l'invalidation après reconnexion ;
5. les empreintes des composants et configurations déjà installés ;
6. les points d'intégration Moonraker possibles sans les activer.

Il devra ensuite comparer ces faits au contrat hors ligne. Toute donnée
nouvelle, champ ambigu, délai non borné ou identité non nettoyée ferme la gate.

Le Goal 2 ne devra envoyer ni `BOX_QUIT_MATERIAL`, ni `TURN_OFF_HEATERS`, ni
autre G-code. Il ne devra créer aucun fichier distant, redémarrer aucun service
ou importer le chemin d'effet du garde.
