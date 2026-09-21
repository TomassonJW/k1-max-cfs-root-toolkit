# ADR-069 — Fin CFS après relève : route fraîche, coupe confirmée, arrêt sûr

- Date : 2026-09-21.
- Statut : **proposée**, non implémentée, non déployée.
- Périmètre : fin normale et annulation après un travail CFS, en continuité d'ADR-067.
- Preuves : [document 83](../83-fin-apres-releve-t1a-t1b-v1.md).

## Problème

Après la relève stock T1A → T1B du 18 septembre, notre fin conserve T1A. Le firmware refuse également la coupe en contexte de reprise. La macro ignore ce refus, demande le retrait d'A et appelle la fin stock malgré une tête encore chargée. La validation de la fin multicolore du 15 septembre ne couvrait pas ce cas.

## Proposition

Garder les primitives existantes qualifiées et ajouter un contrôle explicite de la fin dans le paquet `owned-start-print-v2`, sans nouveau service ni dépendance.

### 1. Identifier le filament réel

- Conserver séparément l'outil logique du fichier, la case physique confirmée et l'identité du travail. Invalider toute information issue d'un travail précédent au nouveau départ et après restart.
- Lire la route engagée depuis les données CFS fraîches **avant** `BOX_ERROR_CLEAR` ou `BOX_END`. Recouper l'outil logique et sa correspondance actualisée quand ils sont disponibles ; ne jamais appliquer la table une deuxième fois à une case déjà physique.
- Ne pas promouvoir `start`, `empty` ou `paused_by_firmware` en preuve d'engagement. `last` reste un historique, pas une autorité sur la bobine actuelle.
- Tête vide : aucun retrait. Tête chargée et route absente, plusieurs routes ou preuves contradictoires : arrêt de la partie filament, chauffes coupées, motif lisible. Aucun repli sur T1A ou sur une bobine simplement déclarée présente.
- Cette lecture doit couvrir les changements internes du stock qui ne passent pas dans l'enveloppe `T0..T15` ; s'appuyer seulement sur cette enveloppe reproduirait le défaut.

### 2. Sortir correctement de la reprise et confirmer la coupe

- Lire/qualifier le prédicat exact `if_in_resume` du module installé. La source stock indique que `do_resume_status` vit jusqu'à la sortie du traitement du fichier ; ce lien est une piste, pas une autorisation à remettre le champ à zéro.
- Préférer une finalisation après la sortie réelle de ce contexte, si l'étude confirme ce besoin. Prévoir une attente bornée, un seul propriétaire et une annulation prioritaire. Ne pas lancer `RESUME` pour débloquer une fin.
- Placer la tête au cutter et obtenir un résultat de coupe explicite du composant qualifié. Ni l'absence d'exception, ni un HTTP OK, ni `M400` ne prouvent la coupe. Si le résultat fiable n'est pas exposé, cette partie reste fermée jusqu'à qualification ; ne pas inventer un contrôle à partir du seul capteur de présence de filament.
- Relever ensuite l'état frais, puis autoriser un seul rembobinage de la case physique retenue, à la température approuvée applicable. Aucun homing, mesh ou palpage ajouté.

### 3. Finir sans cascade d'effets

- Vérifier tête vide et route libérée après retrait. Si c'est acquis, exécuter uniquement la finalisation prévue et couper les chauffes.
- Si coupe, retrait, transport ou lecture échoue : arrêt des chauffes garanti, fin incomplète explicitée, preuve d'erreur conservée ; ni deuxième tentative automatique ni `BOX_END` tête chargée.
- L'arrêt thermique doit s'exécuter même si une commande lève : du G-code de coupure placé après une commande susceptible d'échouer ne suffit pas. Utiliser une finalisation protégée et un délai d'arrêt indépendant du succès de la séquence.
- Séparer le nettoyage des états et la fin du travail des opérations stock sur le filament. Vérifier les effets exacts des commandes conservées. Ne pas déclarer un retrait réussi parce que le G-code s'est terminé.

## Options écartées

| Option | Motif |
| --- | --- |
| Forcer T1B dans la macro | Corrige ce nom uniquement ; casse une autre bobine et laisse la coupe refusée. |
| Mettre à jour seulement `last` dans l'enveloppe T | La relève observée contourne cette enveloppe. |
| Relire uniquement `tnn_map` après la fin stock | La fin remet la table à l'identité ; information perdue. |
| Désactiver la relève automatique | Supprime une fonction demandée et n'assure pas la coupe après une reprise manuelle. |
| Ignorer `if_in_resume` ou écrire arbitrairement un attribut du firmware | Effets internes non établis ; pourrait couper pendant une vraie reprise. |
| Laisser `BOX_END` rattraper tout échec | Retour non borné et effets incontrôlés déjà observés, document 81. |
| Réécrire maintenant tout le propriétaire CFS | Périmètre et risque disproportionnés ; les défauts de fin sont isolables. |

## Validation requise

Hors imprimante : T1A → T1B en interne stock, relève entre les deux CFS, départ directement sur B après un travail sur A, changement refusé/vide, plusieurs routes, route perdue, tête déjà vide, reprise encore active, coupe refusée sans exception, coupe en erreur, retrait incomplet, erreur pendant arrêt, timeout et double appel de fin/annulation. Prouver l'absence de retrait sans coupe, de retrait sur un ancien slot, de relance et de `BOX_END` tête chargée.

Puis revue du diff et du résultat de coupe sur le firmware exact ; paquet de pose avec empreintes, sauvegarde et retour arrière. Validation physique distincte et bornée après autorisation, preuve caméra et présence humaine utile, sur une impression sans valeur. Critères : relève réellement effectuée, coupe acceptée, bon slot rembobiné, tête vide, chauffes coupées, aucune alerte CFS ni intervention pour terminer.

## Conséquences

Une fin ambiguë devient un arrêt sûr explicite au lieu d'un retrait deviné. Il faudra traiter l'affichage d'une finalisation différée si elle est retenue, pour ne pas afficher « terminé » avant la fin des opérations sur le filament. Aucun changement à la relève stock, au mesh, au Z ou à la garde du bus n'est proposé ici.
