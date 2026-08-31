# Qualification physique du propriétaire CFS direct — T1A

Statut : **close KO avant tout effet filament — ne jamais rejouer V1**.

La gate devait essayer un chargement et un retrait directs sans mouvement
d'axe, sans cutter et sans purge. Cette découpe contredit le cycle physique
réel rappelé par Thomas :

- tout retrait doit d'abord placer la tête au cutter et couper le filament ;
- tout chargement doit être immédiatement suivi d'une purge dans le bac ;
- la purge doit être décrochée par `3 à 4` allers-retours francs du petit
  mécanisme du bac, puis contrôlée par caméra.

La tentative réelle s'est arrêtée pendant l'activation : après le restart,
`auto_refill` était revenu à `1`, donc le préflight actif a refusé de lier le
transport. Aucune chauffe, trame CFS, avance, retrait, coupe, purge ou mouvement
d'axe n'a eu lieu. Le rollback a restauré `enabled=false`, le meilleur
`11 × 11`, les cibles zéro et les axes libérés. Les deux capteurs sont restés
actifs : le filament initial est toujours engagé.

`run_gate.ps1` est maintenant fermé avant toute connexion. Un successeur devra
être conçu comme une chorégraphie intégrée cutter → retrait et chargement →
purge bac → décrochage → preuve caméra ; aucune nouvelle qualification isolée
sans ces étapes n'est acceptable.
